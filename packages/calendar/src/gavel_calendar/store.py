"""The invites this service knows about, keyed by our `sessionId`.

Memory is the working set; Postgres is the durable record. Reads are served
from the dict — the room page polls `/m/{id}/state` every 2s per viewer and
must not put that on the database — and every write goes to the dict first,
then to Postgres. A database that is down costs durability, never an invite:
`save` swallows its failure the same way ears' own store does, so the compose
path's promise ("the meeting exists from this point on, no matter what happens
next") still holds with no Postgres at all.

With no engine this class behaves exactly as it did when it was memory-only,
which is how the tests use it. What the durable copy buys:

  * a `/m/{id}` link outlives `docker compose up -d --build calendar`, which
    the handover treats as routine and which used to 404 every invite ever
    emailed;
  * the banked report outlives the process that banked it — the brain forgets
    a session when the next one starts, so this is the only copy;
  * `started` outlives the process, so the scheduler cannot start a *second*
    ears session for a meeting it already started before a restart.

`sessionId` here is ours, not the id `ears-discord` hands back from
`POST /api/sessions` — that one is recorded alongside it once the meeting
actually starts.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .db.models import Invite

logger = logging.getLogger(__name__)


@dataclass
class InviteRecord:
    session_id: str
    title: str
    start: datetime
    end: datetime
    agenda: dict
    context: str = ""
    started: bool = False
    ears_meeting_id: str | None = None
    ears_session_id: str | None = None
    # The last brain state seen for *this* meeting's session. The brain keeps one
    # live session in memory and drops it when the next one starts, so the room
    # page banks each live poll here — that banked copy is what the report is
    # rendered from once the meeting is over. See room.py.
    last_state: dict | None = None


def _row_to_record(row: Invite) -> InviteRecord:
    return InviteRecord(
        session_id=row.session_id,
        title=row.title,
        start=_aware(row.starts_at),
        end=_aware(row.ends_at),
        agenda=row.agenda or {},
        context=row.context or "",
        started=row.started,
        ears_meeting_id=row.ears_meeting_id,
        ears_session_id=row.ears_session_id,
        last_state=row.last_state,
    )


def _aware(value: datetime) -> datetime:
    """Everything in this service compares against `datetime.now(UTC)` — the
    scheduler's due check is `r.start <= now`. A driver that hands back a naive
    datetime (SQLite in tests, and Postgres for a column that somehow lost its
    timezone) would make that comparison raise, so normalise on the way in."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


@dataclass
class InviteStore:
    _records: dict[str, InviteRecord] = field(default_factory=dict)
    _locks: dict[str, asyncio.Lock] = field(default_factory=lambda: defaultdict(asyncio.Lock))
    _engine: AsyncEngine | None = None
    _factory: async_sessionmaker[AsyncSession] | None = None

    # --- connection ---------------------------------------------------------

    async def attach(self, dsn: str) -> bool:
        """Back this store with Postgres and rehydrate it. Mutates in place
        rather than returning a new store: `app.py` holds one module-level
        instance that `compose.py` and the route handlers all close over, and
        rebinding it would leave them pointing at the memory-only original.

        Never raises. Calendar booting without a database is strictly better
        than calendar not booting, and the fallback is exactly the behaviour
        this service had before the table existed.
        """
        if not dsn:
            logger.info("store.memory_only reason=no_dsn")
            return False
        # A QueuePool is a Postgres concern; SQLite's async driver (what the
        # store's own tests run on) uses a NullPool and rejects these outright.
        pool_kw = (
            {"pool_pre_ping": True, "pool_size": 4, "max_overflow": 4}
            if dsn.startswith(("postgresql", "postgres"))
            else {}
        )
        try:
            engine = create_async_engine(dsn, **pool_kw)
            async with engine.connect() as conn:
                await conn.execute(select(1))
        except Exception as exc:  # noqa: BLE001 - any failure means "run without a database"
            # The DSN carries a password; log the exception type, never its text.
            logger.warning("store.memory_only reason=%s", type(exc).__name__)
            return False
        self._engine = engine
        self._factory = async_sessionmaker(engine, expire_on_commit=False)
        logger.info("store.connected")
        await self.load()
        return True

    @property
    def durable(self) -> bool:
        return self._factory is not None

    async def load(self) -> int:
        """Rehydrate every invite from Postgres into the working set. Called
        once at startup, before the scheduler runs — otherwise the scheduler
        would see an empty `pending()` and a restart during a meeting's start
        window would start it a second time."""
        if self._factory is None:
            return 0
        try:
            async with self._factory() as session:
                rows = (await session.execute(select(Invite))).scalars().all()
        except Exception as exc:  # noqa: BLE001 - boot without history rather than not at all
            logger.warning("store.load_failed reason=%s", type(exc).__name__)
            return 0
        for row in rows:
            self._records[row.session_id] = _row_to_record(row)
        logger.info("store.loaded count=%d", len(rows))
        return len(rows)

    async def close(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._factory = None

    # --- reads (memory) -----------------------------------------------------

    def get(self, session_id: str) -> InviteRecord | None:
        return self._records.get(session_id)

    def pending(self) -> list[InviteRecord]:
        return [r for r in self._records.values() if not r.started]

    def lock_for(self, session_id: str) -> asyncio.Lock:
        """Guards `service.start` against two concurrent Join clicks. Still the
        right primitive: calendar is a single process with an in-process
        scheduler. What it could never do is survive a restart — that is what
        the durable `started` flag is for, not this."""
        return self._locks[session_id]

    # --- writes (memory, then Postgres) -------------------------------------

    async def save(self, record: InviteRecord) -> None:
        self._records[record.session_id] = record
        await self._persist(record)

    async def mark_started(
        self, session_id: str, ears_meeting_id: str, ears_session_id: str
    ) -> None:
        record = self._records[session_id]
        record.started = True
        record.ears_meeting_id = ears_meeting_id
        record.ears_session_id = ears_session_id
        await self._persist(record)

    async def bank_state(self, session_id: str, state: dict) -> None:
        record = self._records.get(session_id)
        if record is None:
            return
        # Every viewer polls this every 2s. Identical snapshots are the common
        # case between two polls, and re-writing one buys nothing.
        if record.last_state == state:
            return
        record.last_state = state
        await self._persist(record)

    async def _persist(self, record: InviteRecord) -> None:
        """Best-effort. The in-memory copy is already updated and authoritative
        for this process; Postgres is what makes it outlive the process."""
        if self._factory is None:
            return
        try:
            async with self._factory() as session, session.begin():
                await session.merge(
                    Invite(
                        session_id=record.session_id,
                        title=record.title,
                        starts_at=record.start,
                        ends_at=record.end,
                        agenda=record.agenda,
                        context=record.context,
                        started=record.started,
                        ears_meeting_id=record.ears_meeting_id,
                        ears_session_id=record.ears_session_id,
                        last_state=record.last_state,
                    )
                )
        except Exception as exc:  # noqa: BLE001 - a lost row must never cost the invite
            logger.warning(
                "store.persist_failed session_id=%s reason=%s",
                record.session_id,
                type(exc).__name__,
            )
