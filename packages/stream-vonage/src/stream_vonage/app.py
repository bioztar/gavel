"""stream-vonage: puts the gavel stage on Vonage Video as an HLS broadcast,
alongside the Discord call — never instead of it. This service makes no
moderation decisions and never touches the ears<->brain wire; it only reads
brain's read-only `/state` and drives the official Vonage SDKs (see
`vonage.py`) — never a hand-rolled JWT.

    POST /stream/start   mint a session, start archive + broadcast -> hlsUrl,
                          and start a background thread that relays brain's
                          `/state` into the session via session.signal()
                          (depth addition #1 — see `_signal_relay_loop`)
    POST /stream/stop    stop the relay thread, then broadcast + archive
                          -> archiveUrl (if ready by then)
    GET  /stream/status  current in-memory stream state, for /watch
    GET  /publisher       the one browser tab: joins, publishes screen capture
    GET  /watch            hls.js player pointed at the last hlsUrl
    GET  /brain-state      same-origin proxy of brain's GET /state, for the
                            publisher page's own on-screen agenda overlay
    GET  /healthz
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from stream_vonage.settings import Settings, get_settings
from stream_vonage.vonage import (
    VonageClient,
    VonageError,
    VonageNotConfigured,
    detect_auth_style,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"


class StreamStartResponse(BaseModel):
    hls_url: str = Field(alias="hlsUrl")
    session_id: str = Field(alias="sessionId")
    archive_id: str = Field(alias="archiveId")
    broadcast_id: str = Field(alias="broadcastId")
    application_id: str | None = Field(default=None, alias="applicationId")
    api_key: str | None = Field(default=None, alias="apiKey")
    token: str
    watch_url: str = Field(alias="watchUrl")
    broadcast_started_at: float = Field(alias="broadcastStartedAt")

    model_config = {"populate_by_name": True}


class StreamStopResponse(BaseModel):
    archive_id: str = Field(alias="archiveId")
    archive_url: str | None = Field(default=None, alias="archiveUrl")
    hls_url: str | None = Field(default=None, alias="hlsUrl")

    model_config = {"populate_by_name": True}


class StreamState:
    """One stream at a time — this is a single-laptop demo tool, not a
    multi-tenant service. Held in memory; a restart just means "start again"."""

    def __init__(self) -> None:
        self.session_id: str | None = None
        self.broadcast_id: str | None = None
        self.archive_id: str | None = None
        self.hls_url: str | None = None
        self.archive_url: str | None = None
        self.broadcast_started_at: float | None = None

    @property
    def active(self) -> bool:
        return self.session_id is not None

    def clear(self) -> None:
        self.session_id = None
        self.broadcast_id = None
        self.archive_id = None
        self.hls_url = None
        self.archive_url = None
        self.broadcast_started_at = None


def _signal_relay_loop(
    settings: Settings,
    http_client: httpx.Client,
    session_id: str,
    stop_event: threading.Event,
) -> None:
    """Depth addition #1: polls brain's read-only `GET /state` and relays it
    into the Vonage session via `session.signal()`, so every connected Vonage
    client (viewers, the archive) sees the live agenda/intervention state —
    not just the browser tab doing the screen capture. One `VonageClient`
    (and, for the jwt style, one underlying SDK client) is reused for the
    whole loop rather than rebuilt per tick.

    Best-effort: a brain-unreachable or signal-rejected tick is swallowed and
    retried next interval — a stalled agenda overlay must never take the
    broadcast down.
    """
    with VonageClient(settings) as vonage:
        last_payload: str | None = None
        while not stop_event.wait(settings.brain_state_poll_seconds):
            try:
                resp = http_client.get(settings.brain_state_url)
                resp.raise_for_status()
                payload = json.dumps(resp.json(), separators=(",", ":"))
            except (httpx.HTTPError, ValueError):
                continue
            if payload == last_payload:
                continue
            try:
                vonage.send_signal(session_id, "brainState", payload)
            except VonageError:
                continue
            last_payload = payload


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="gavel stream-vonage")
    app.state.settings = settings
    app.state.stream = StreamState()
    app.state.http_client = httpx.Client(timeout=10.0)
    app.state.signal_thread = None  # threading.Thread | None, set by /stream/start
    app.state.signal_stop_event = None  # threading.Event | None

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        style = detect_auth_style(settings)
        return {
            "credentials": "present" if style else "absent",
            "authStyle": style,
        }

    @app.post("/stream/start")
    def stream_start() -> StreamStartResponse:
        stream: StreamState = app.state.stream
        if stream.active:
            raise HTTPException(409, "a stream is already active — POST /stream/stop first")

        try:
            with VonageClient(settings) as vonage:
                session_id = vonage.create_session()
                token = vonage.generate_token(session_id, role="publisher")
                archive = vonage.start_archive(session_id)
                try:
                    broadcast = vonage.start_broadcast(session_id)
                except VonageError:
                    vonage.stop_archive(archive.archive_id)
                    raise
        except VonageNotConfigured as exc:
            raise HTTPException(503, str(exc)) from exc
        except VonageError as exc:
            raise HTTPException(502, f"vonage rejected the stream start: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise HTTPException(502, f"vonage REST call failed: {exc}") from exc

        stream.session_id = session_id
        stream.broadcast_id = broadcast.broadcast_id
        stream.archive_id = archive.archive_id
        stream.hls_url = broadcast.hls_url
        stream.broadcast_started_at = time.monotonic()

        stop_event = threading.Event()
        app.state.signal_stop_event = stop_event
        app.state.signal_thread = threading.Thread(
            target=_signal_relay_loop,
            args=(settings, app.state.http_client, session_id, stop_event),
            daemon=True,
            name="stream-vonage-signal-relay",
        )
        app.state.signal_thread.start()

        return StreamStartResponse(
            hlsUrl=broadcast.hls_url,
            sessionId=session_id,
            archiveId=archive.archive_id,
            broadcastId=broadcast.broadcast_id,
            applicationId=settings.vonage_application_id or None,
            apiKey=settings.vonage_api_key or None,
            token=token,
            watchUrl="/watch",
            broadcastStartedAt=stream.broadcast_started_at,
        )

    @app.post("/stream/stop")
    def stream_stop() -> StreamStopResponse:
        stream: StreamState = app.state.stream
        if not stream.active:
            raise HTTPException(409, "no active stream")
        assert stream.broadcast_id is not None
        assert stream.archive_id is not None
        assert stream.hls_url is not None

        stop_event: threading.Event | None = app.state.signal_stop_event
        if stop_event is not None:
            stop_event.set()
            thread: threading.Thread | None = app.state.signal_thread
            if thread is not None:
                thread.join(timeout=5.0)
        app.state.signal_stop_event = None
        app.state.signal_thread = None

        try:
            with VonageClient(settings) as vonage:
                vonage.stop_broadcast(stream.broadcast_id)
                archive = vonage.stop_archive(stream.archive_id)
        except VonageNotConfigured as exc:
            raise HTTPException(503, str(exc)) from exc
        except VonageError as exc:
            raise HTTPException(502, f"vonage rejected the stream stop: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise HTTPException(502, f"vonage REST call failed: {exc}") from exc

        response = StreamStopResponse(
            archiveId=archive.archive_id, archiveUrl=archive.url, hlsUrl=stream.hls_url
        )
        stream.clear()
        return response

    @app.get("/stream/status")
    def stream_status() -> dict[str, Any]:
        stream: StreamState = app.state.stream
        return {
            "active": stream.active,
            "sessionId": stream.session_id,
            "hlsUrl": stream.hls_url,
            "archiveId": stream.archive_id,
        }

    @app.get("/brain-state")
    def brain_state() -> Response:
        """Same-origin proxy of brain's read-only GET /state, so the publisher
        page's fetch() never has to cross origins (brain sets no CORS
        headers — see docs/CONTRACT.md §"Additive — ears is the one store")."""
        http_client: httpx.Client = app.state.http_client
        try:
            resp = http_client.get(settings.brain_state_url)
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"brain unreachable: {exc}") from exc
        return JSONResponse(resp.json(), status_code=resp.status_code)

    @app.get("/publisher", response_class=HTMLResponse)
    def publisher_page() -> str:
        html = (STATIC_DIR / "publisher.html").read_text()
        return html.replace("__BRAIN_POLL_MS__", str(int(settings.brain_state_poll_seconds * 1000)))

    @app.get("/watch", response_class=HTMLResponse)
    def watch_page() -> str:
        return (STATIC_DIR / "watch.html").read_text()

    return app


app = create_app()
