"""HTTP + WebSocket surface — the same shape as ears-discord/src/ears/wire.py.

    WS   /                          the brain: ears→brain frames out, `speak` / `stop` in
    WS   /live                      operators: every frame + debug events, read-only

    GET  /health                    what is connected
    GET  /api/status                call, session, participants, open turns, playback, checks
    GET  /api/selfcheck             re-run the selector self-check against the live page
    POST /api/sessions              {"title", "context", "agenda"} → end the current session, start a new one
    POST /api/sessions/end
    POST /api/say                   {"text": ...} → SLNG TTS → played into the call
    POST /api/stop                  stop playback, drop the queue
    POST /api/present               present STAGE_URL now (retry after the stage came up)

    The brain's store — same routes as ears-discord, answered from memory (store.py):
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
from typing import TYPE_CHECKING, Annotated, Any, Literal

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from .frames import Frame
from .logging import get_logger
from .tts import TtsError

if TYPE_CHECKING:
    from .app import Ears

logger = get_logger(__name__)

CLIENT_QUEUE_LIMIT = 2_000


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
    title: str | None = None
    context: str | None = None
    agenda: dict[str, Any] | None = None


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
    api = FastAPI(title="gavel ears-meet", docs_url="/docs")

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

    # --- health -------------------------------------------------------------------

    @api.get("/health")
    async def health() -> dict[str, Any]:
        s = ears.status()
        if s["inCall"]:
            status = "ok"
        elif ears.standby:
            status = "standby"
        else:
            status = "joining"
        return {
            "status": status,
            **{k: s[k] for k in ("inCall", "channelId", "sessionId", "stt", "captions", "stage")},
            "participants": len(s["participants"]),
            "wireClients": s["brains"],
            "selfCheck": s["selfCheck"],
        }

    @api.get("/api/status")
    async def status() -> dict[str, Any]:
        return ears.status()

    @api.get("/api/browser")
    async def browser() -> dict[str, Any]:
        """The open tabs, by url and title. The stage tab must be titled exactly
        `settings.stage_tab_title` for Chromium's tab capture to pick it."""
        pages = await ears.browser_pages()
        title = ears.settings.stage_tab_title
        return {
            "launched": bool(pages),
            "pages": pages,
            "stageTab": next((p for p in pages if p["title"] == title), None),
        }

    @api.get("/api/selfcheck")
    async def selfcheck() -> dict[str, Any]:
        result = await ears.self_check()
        if result is None:
            raise HTTPException(503, "not in a call")
        return {
            "ok": result.ok,
            "message": result.message(),
            "matched": result.matched,
            "missingRequired": result.missing_required,
            "missingOptional": result.missing_optional,
        }

    # --- sessions -----------------------------------------------------------------

    @api.post("/api/sessions")
    async def start_session(body: StartSession) -> dict[str, Any]:
        sid = ears.start_session(title=body.title, context=body.context, agenda=body.agenda)
        return {"sessionId": sid}

    @api.post("/api/sessions/end")
    async def end_session() -> dict[str, bool]:
        ears.end_session()
        return {"ok": True}

    # --- speaking -----------------------------------------------------------------

    @api.post("/api/say")
    async def say(body: Say) -> dict[str, Any]:
        try:
            return await ears.say(body.text)
        except TtsError as exc:
            raise HTTPException(503, str(exc)) from exc

    @api.post("/api/stop")
    async def stop() -> dict[str, bool]:
        ears.stop_playback()
        return {"ok": True}

    @api.post("/api/present")
    async def present() -> dict[str, bool]:
        return {"presenting": await ears.present_stage()}

    # --- the brain's store --------------------------------------------------------

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
        memory = await ears.store.set_memory_status(memory_id, body.status)
        if memory is None:
            raise HTTPException(404, "no such memory")
        ears.debug("memory.status", memory=memory)
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
