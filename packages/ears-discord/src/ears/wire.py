"""HTTP + WebSocket surface.

    WS   /                          the brain: ears→brain frames out, `speak` / `stop` in
    WS   /live                      the console: every frame + debug events, read-only
    GET  /console                   the console page (no auth — localhost tool)

    GET  /health                    what is connected
    GET  /api/status                session, meeting, participants, open turns, playback
    GET  /api/meetings              ...and POST, PUT /{id}, DELETE /{id}
    POST /api/sessions              {"meetingId": ...|null} → end the current session, start a new one
    POST /api/sessions/end
    GET  /api/sessions              recent sessions
    GET  /api/sessions/{id|current}/transcript
    POST /api/say                   {"text": ...} → SLNG TTS → played into the call
    POST /api/stop                  stop playback, drop the queue

    The brain's store — ears is the one database:
    POST  /api/memories             a parked point / note about a person → the row
    GET   /api/memories             ?discordId=…(repeatable)&status=open&sessionId=…
    PATCH /api/memories/{id}        {"status": "resolved" | "open"}
    POST  /api/interventions        what the chair said and why
    POST  /api/llm-calls            tokens + cost of one model call → running session totals
    GET   /api/sessions/{id|current}/usage

Each connection gets its own send queue, so a slow client never stalls the call
loop or reorders frames.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field

from .frames import Frame
from .logging import get_logger
from .meetings import Meeting, MeetingIn
from .tts import TtsError

if TYPE_CHECKING:
    from .app import Ears

logger = get_logger(__name__)

CLIENT_QUEUE_LIMIT = 2_000
CONSOLE_HTML = Path(__file__).with_name("console.html")


class Hub:
    def __init__(self) -> None:
        self._clients: dict[WebSocket, asyncio.Queue[str]] = {}

    def __len__(self) -> int:
        return len(self._clients)

    def broadcast(self, frame: dict[str, Any]) -> None:
        text = json.dumps(frame, separators=(",", ":"))
        for ws, queue in list(self._clients.items()):
            try:
                queue.put_nowait(text)
            except asyncio.QueueFull:
                logger.warning("wire.client_too_slow", client=_peer(ws))
                self._clients.pop(ws, None)

    async def serve(self, ws: WebSocket, hello: list[dict[str, Any]], on_message: Any) -> None:
        queue: asyncio.Queue[str] = asyncio.Queue(CLIENT_QUEUE_LIMIT)
        for frame in hello:
            queue.put_nowait(json.dumps(frame, separators=(",", ":")))
        self._clients[ws] = queue
        logger.info(
            "wire.connected", path=ws.url.path, client=_peer(ws), clients=len(self._clients)
        )
        sender = asyncio.create_task(self._send_loop(ws, queue))
        try:
            while True:
                on_message(await ws.receive_text())
        except WebSocketDisconnect:
            pass
        finally:
            self._clients.pop(ws, None)
            sender.cancel()
            logger.info("wire.disconnected", path=ws.url.path, client=_peer(ws))

    @staticmethod
    async def _send_loop(ws: WebSocket, queue: asyncio.Queue[str]) -> None:
        with contextlib.suppress(Exception):
            while True:
                await ws.send_text(await queue.get())


def _peer(ws: WebSocket) -> str:
    return f"{ws.client.host}:{ws.client.port}" if ws.client else "?"


class StartSession(BaseModel):
    meeting_id: str | None = Field(default=None, alias="meetingId")


class Say(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class MemoryIn(Frame):
    discord_id: str
    name: str | None = None
    kind: Literal["parked", "note"] = "parked"
    summary: str = Field(min_length=1, max_length=500)
    quote: str | None = Field(default=None, max_length=2000)
    topic_id: str | None = None
    session_id: str | None = None


class MemoryStatus(Frame):
    status: Literal["open", "resolved"]


class InterventionIn(Frame):
    session_id: str | None = None
    kind: str = Field(min_length=1, max_length=32)
    target_id: str | None = None
    addressee_id: str | None = None
    topic_id: str | None = None
    line: str
    source: Literal["llm", "template", "cache"]
    actions: list[str] = Field(default_factory=list)
    compose_ms: int | None = None
    tts_ms: int | None = None


class LlmCallIn(Frame):
    session_id: str | None = None
    agent: str = Field(min_length=1, max_length=32)
    model: str = Field(min_length=1, max_length=128)
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    cache_hit: bool = False


def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(422, "expected a UUID") from exc


def create_api(ears: Ears) -> FastAPI:
    api = FastAPI(title="gavel ears-discord", docs_url="/docs")

    # --- sockets ------------------------------------------------------------------

    @api.websocket("/")
    async def brain(ws: WebSocket) -> None:
        await ws.accept()
        await ears.hub.serve(ws, ears.hello(), ears.command)

    @api.websocket("/live")
    async def live(ws: WebSocket) -> None:
        await ws.accept()
        hello = [{"type": "console.hello", "status": ears.status(), "recent": list(ears.recent)}]
        await ears.console.serve(ws, hello, lambda _msg: None)

    # --- pages & health -------------------------------------------------------------

    @api.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse("/console")

    @api.get("/console", include_in_schema=False)
    async def console() -> FileResponse:
        return FileResponse(CONSOLE_HTML, headers={"cache-control": "no-store"})

    @api.get("/health")
    async def health() -> dict[str, Any]:
        s = ears.status()
        return {
            "status": "ok",
            **{
                k: s[k]
                for k in ("voice", "channelId", "sessionId", "postgres", "redis", "stt", "tts")
            },
            "participants": len(s["participants"]),
            "wireClients": s["brains"],
        }

    @api.get("/api/status")
    async def status() -> dict[str, Any]:
        return ears.status()

    # --- meetings ---------------------------------------------------------------------

    @api.get("/api/meetings")
    async def list_meetings() -> list[dict[str, Any]]:
        return [m.model_dump(by_alias=True) for m in await ears.store.list_meetings()]

    @api.post("/api/meetings")
    async def create_meeting(body: MeetingIn) -> dict[str, Any]:
        meeting = await ears.store.save_meeting(body)
        assert meeting is not None
        return meeting.model_dump(by_alias=True)

    @api.put("/api/meetings/{meeting_id}")
    async def update_meeting(meeting_id: str, body: MeetingIn) -> dict[str, Any]:
        _uuid(meeting_id)
        meeting = await ears.store.save_meeting(body, meeting_id)
        if meeting is None:
            raise HTTPException(404, "no such meeting")
        return meeting.model_dump(by_alias=True)

    @api.delete("/api/meetings/{meeting_id}")
    async def delete_meeting(meeting_id: str) -> dict[str, bool]:
        _uuid(meeting_id)
        await ears.store.delete_meeting(meeting_id)
        return {"ok": True}

    # --- sessions ------------------------------------------------------------------------

    @api.post("/api/sessions")
    async def start_session(body: StartSession) -> dict[str, Any]:
        meeting: Meeting | None = None
        if body.meeting_id:
            _uuid(body.meeting_id)
            meeting = await ears.store.get_meeting(body.meeting_id)
            if meeting is None:
                raise HTTPException(404, "no such meeting")
        return {"sessionId": ears.start_session(meeting)}

    @api.post("/api/sessions/end")
    async def end_session() -> dict[str, bool]:
        ears.end_session()
        return {"ok": True}

    @api.get("/api/sessions")
    async def sessions() -> list[dict[str, Any]]:
        return await ears.store.recent_sessions()

    @api.get("/api/sessions/{session_id}/transcript")
    async def transcript(session_id: str) -> list[dict[str, Any]]:
        if session_id == "current":
            if ears.session_id is None:
                raise HTTPException(404, "no active session")
            session_id = ears.session_id
        names = {p.discord_id: p.name for p in ears.participants.values()}
        return [
            {
                "discordId": r.discord_id,
                "name": names.get(r.discord_id, r.discord_id),
                "text": r.text,
                "startedAt": r.started_at.isoformat(),
                "endedAt": r.ended_at.isoformat(),
                "utteranceId": str(r.utterance_id),
                "seq": r.seq,
            }
            for r in await ears.store.transcript_for(_uuid(session_id))
        ]

    # --- speaking into the call ---------------------------------------------------------

    @api.post("/api/say")
    async def say(body: Say) -> dict[str, Any]:
        try:
            return await ears.say(body.text)
        except TtsError as exc:
            raise HTTPException(502, str(exc)) from exc

    @api.post("/api/stop")
    async def stop() -> dict[str, bool]:
        ears.stop_playback()
        return {"ok": True}

    # --- the brain's store ------------------------------------------------------------------

    @api.post("/api/memories")
    async def add_memory(body: MemoryIn) -> dict[str, Any]:
        return await ears.add_memory(body.model_dump())

    @api.get("/api/memories")
    async def list_memories(
        discord_id: Annotated[list[str] | None, Query(alias="discordId")] = None,
        status: Literal["open", "resolved"] | None = None,
        session_id: Annotated[str | None, Query(alias="sessionId")] = None,
    ) -> list[dict[str, Any]]:
        return await ears.store.list_memories(discord_id, status, session_id)

    @api.patch("/api/memories/{memory_id}")
    async def set_memory_status(memory_id: str, body: MemoryStatus) -> dict[str, Any]:
        _uuid(memory_id)
        memory = await ears.set_memory_status(memory_id, body.status)
        if memory is None:
            raise HTTPException(404, "no such memory")
        return memory

    @api.post("/api/interventions")
    async def add_intervention(body: InterventionIn) -> dict[str, bool]:
        ears.record_intervention(body.model_dump())
        return {"ok": True}

    @api.post("/api/llm-calls")
    async def add_llm_call(body: LlmCallIn) -> dict[str, float]:
        return ears.record_llm_call(body.model_dump())

    @api.get("/api/sessions/{session_id}/usage")
    async def usage(session_id: str) -> dict[str, float]:
        if session_id == "current":
            if ears.session_id is None:
                raise HTTPException(404, "no active session")
            session_id = ears.session_id
        return await ears.store.usage(session_id)

    return api
