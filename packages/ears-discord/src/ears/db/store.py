"""Postgres persistence, off the hot path.

Writes go onto a queue drained by one writer task, so they commit in the order
they happened (a session row before its events) and the call loop never waits on
the database. A slow or dead database costs rows, never latency. If Postgres is
unreachable at startup the store disables itself and ears runs on without it.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..frames import Participant as ParticipantFrame
from ..logging import get_logger
from ..meetings import Agenda, Meeting, MeetingIn
from .models import CallSession, Event, Participant, TranscriptChunk, Turn
from .models import Meeting as MeetingRow

logger = get_logger(__name__)

Write = Callable[[AsyncSession], Awaitable[None]]
QUEUE_LIMIT = 10_000


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class Store:
    def __init__(self, engine: AsyncEngine | None) -> None:
        self._engine = engine
        self._factory = async_sessionmaker(engine, expire_on_commit=False) if engine else None
        self._session_id: uuid.UUID | None = None
        self._queue: asyncio.Queue[Write] = asyncio.Queue(QUEUE_LIMIT)
        self._writer: asyncio.Task[None] | None = None
        self._dropped = 0
        # Meetings survive without Postgres too, just not a restart.
        self._memory_meetings: dict[str, Meeting] = {}

    @classmethod
    async def connect(cls, dsn: str) -> Store:
        engine = create_async_engine(dsn, pool_pre_ping=True, pool_size=4, max_overflow=4)
        try:
            async with engine.connect() as conn:
                await conn.execute(select(1))
        except Exception as exc:  # noqa: BLE001 - any failure means "run without a database"
            logger.warning("store.disabled", reason=str(exc)[:200])
            await engine.dispose()
            return cls(None)
        logger.info("store.connected")
        store = cls(engine)
        store._writer = asyncio.get_running_loop().create_task(store._drain())
        return store

    @property
    def enabled(self) -> bool:
        return self._engine is not None

    @property
    def session_id(self) -> uuid.UUID | None:
        return self._session_id

    # --- writes (queued) ------------------------------------------------------

    def start_session(
        self,
        session_id: uuid.UUID,
        *,
        meeting_id: str | None,
        guild_id: str | None,
        channel_id: str | None,
    ) -> None:
        self._session_id = session_id
        mid = uuid.UUID(meeting_id) if meeting_id else None

        async def write(s: AsyncSession) -> None:
            s.add(
                CallSession(id=session_id, meeting_id=mid, guild_id=guild_id, channel_id=channel_id)
            )

        self._put(write)

    def set_session_channel(self, guild_id: str, channel_id: str) -> None:
        session_id = self._session_id
        if session_id is None:
            return

        async def write(s: AsyncSession) -> None:
            await s.execute(
                update(CallSession)
                .where(CallSession.id == session_id)
                .values(guild_id=guild_id, channel_id=channel_id)
            )

        self._put(write)

    def end_session(self) -> None:
        session_id, self._session_id = self._session_id, None
        if session_id is None:
            return

        async def write(s: AsyncSession) -> None:
            await s.execute(
                update(CallSession).where(CallSession.id == session_id).values(ended_at=func.now())
            )

        self._put(write)

    def event(self, frame: dict[str, Any]) -> None:
        session_id = self._session_id
        if session_id is None:
            return

        async def write(s: AsyncSession) -> None:
            s.add(
                Event(
                    session_id=session_id,
                    type=frame["type"],
                    at=parse_iso(frame["at"]),
                    frame=frame,
                )
            )

        self._put(write)

    def participants(self, people: list[ParticipantFrame]) -> None:
        session_id = self._session_id
        if session_id is None or not people:
            return

        async def write(s: AsyncSession) -> None:
            stmt = pg_insert(Participant).values(
                [
                    {"session_id": session_id, "discord_id": p.discord_id, "name": p.name}
                    for p in people
                ]
            )
            await s.execute(
                stmt.on_conflict_do_update(
                    index_elements=["session_id", "discord_id"],
                    set_={"name": stmt.excluded.name, "last_seen": func.now()},
                )
            )

        self._put(write)

    def add(self, row: Turn | TranscriptChunk) -> None:
        """Insert a row belonging to the current session."""
        if self._session_id is None:
            return
        row.session_id = self._session_id

        async def write(s: AsyncSession) -> None:
            s.add(row)

        self._put(write)

    # --- meetings (awaited: they are console requests, not the call loop) -------

    async def list_meetings(self) -> list[Meeting]:
        if self._factory is None:
            return sorted(self._memory_meetings.values(), key=lambda m: m.updated_at, reverse=True)
        async with self._factory() as s:
            rows = await s.execute(select(MeetingRow).order_by(MeetingRow.updated_at.desc()))
            return [_meeting(r) for r in rows.scalars()]

    async def get_meeting(self, meeting_id: str) -> Meeting | None:
        if self._factory is None:
            return self._memory_meetings.get(meeting_id)
        async with self._factory() as s:
            row = await s.get(MeetingRow, uuid.UUID(meeting_id))
            return _meeting(row) if row else None

    async def save_meeting(self, body: MeetingIn, meeting_id: str | None = None) -> Meeting | None:
        """Create (no id) or replace. None if the id does not exist."""
        agenda = body.agenda.model_dump(by_alias=True)
        if self._factory is None:
            now = _now()
            if meeting_id is not None and meeting_id not in self._memory_meetings:
                return None
            created = self._memory_meetings[meeting_id].created_at if meeting_id else now
            meeting = Meeting(
                id=meeting_id or str(uuid.uuid4()),
                title=body.title,
                context=body.context,
                agenda=body.agenda,
                created_at=created,
                updated_at=now,
            )
            self._memory_meetings[meeting.id] = meeting
            return meeting
        async with self._factory() as s, s.begin():
            if meeting_id is None:
                row = MeetingRow(
                    id=uuid.uuid4(), title=body.title, context=body.context, agenda=agenda
                )
                s.add(row)
            else:
                found = await s.get(MeetingRow, uuid.UUID(meeting_id))
                if found is None:
                    return None
                row = found
                row.title, row.context, row.agenda = body.title, body.context, agenda
                row.updated_at = datetime.now(UTC)
            await s.flush()
            await s.refresh(row)
            return _meeting(row)

    async def delete_meeting(self, meeting_id: str) -> None:
        if self._factory is None:
            self._memory_meetings.pop(meeting_id, None)
            return
        async with self._factory() as s, s.begin():
            await s.execute(delete(MeetingRow).where(MeetingRow.id == uuid.UUID(meeting_id)))

    # --- reads ------------------------------------------------------------------

    async def recent_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        if self._factory is None:
            return []
        async with self._factory() as s:
            counts = (
                select(TranscriptChunk.session_id, func.count().label("n"))
                .group_by(TranscriptChunk.session_id)
                .subquery()
            )
            rows = await s.execute(
                select(CallSession, MeetingRow.title, counts.c.n)
                .outerjoin(MeetingRow, MeetingRow.id == CallSession.meeting_id)
                .outerjoin(counts, counts.c.session_id == CallSession.id)
                .order_by(CallSession.started_at.desc())
                .limit(limit)
            )
            return [
                {
                    "id": str(sess.id),
                    "meetingId": str(sess.meeting_id) if sess.meeting_id else None,
                    "title": title,
                    "channelId": sess.channel_id,
                    "startedAt": sess.started_at.isoformat(),
                    "endedAt": sess.ended_at.isoformat() if sess.ended_at else None,
                    "transcripts": n or 0,
                }
                for sess, title, n in rows
            ]

    async def transcript_for(self, session_id: uuid.UUID) -> list[TranscriptChunk]:
        if self._factory is None:
            return []
        async with self._factory() as s:
            rows = await s.execute(
                select(TranscriptChunk)
                .where(TranscriptChunk.session_id == session_id)
                .order_by(TranscriptChunk.started_at, TranscriptChunk.seq)
            )
            return list(rows.scalars())

    # --- lifecycle ----------------------------------------------------------------

    async def close(self) -> None:
        if self._engine is None:
            return
        self.end_session()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._queue.join(), timeout=5)
        if self._writer:
            self._writer.cancel()
        await self._engine.dispose()

    def _put(self, write: Write) -> None:
        if self._factory is None:
            return
        try:
            self._queue.put_nowait(write)
        except asyncio.QueueFull:
            self._dropped += 1
            if self._dropped % 100 == 1:
                logger.warning("store.queue_full", dropped=self._dropped)

    async def _drain(self) -> None:
        assert self._factory is not None
        while True:
            write = await self._queue.get()
            try:
                async with self._factory() as s, s.begin():
                    await write(s)
            except Exception as exc:  # noqa: BLE001 - a lost row must never break the call
                logger.warning("store.write_failed", error=str(exc)[:200])
            finally:
                self._queue.task_done()


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _meeting(row: MeetingRow) -> Meeting:
    return Meeting(
        id=str(row.id),
        title=row.title,
        context=row.context,
        agenda=Agenda.model_validate(row.agenda),
        created_at=row.created_at.isoformat(timespec="seconds"),
        updated_at=row.updated_at.isoformat(timespec="seconds"),
    )
