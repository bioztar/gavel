"""chair-video: turns the chair's spoken audio into a lip-synced talking-head
clip through fal. A service the brain calls — it makes no decisions."""

from __future__ import annotations

import asyncio
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from chair_video.audio import decode_base64_audio, fetch_audio, wav_duration_ms
from chair_video.cache import SpeakVideoCache, audio_key
from chair_video.director import DirectorManager
from chair_video.fal import FalClient, FalError
from chair_video.settings import Settings, get_settings

log = structlog.get_logger()

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"

# The stage page never gets FAL_KEY — only a per-session token, and only this
# one host may be reached through the proxy. Forwarding an inbound
# Authorization would let a client set its own fal credential; forwarding
# arbitrary headers would let it smuggle things fal's CORS wouldn't otherwise
# see. Both are refused outright, not sanitized.
PROXY_REQUEST_HEADER_ALLOWLIST = {"content-type", "accept"}
PROXY_TARGET_HEADER = "x-fal-target-url"
PROXY_TOKEN_HEADER = "x-director-token"


class SpeakVideoRequest(BaseModel):
    audio_url: str | None = Field(default=None, alias="audioUrl")
    audio_base64: str | None = Field(default=None, alias="audioBase64")
    format: str = "wav"
    # Unknown/omitted -> "formal" (see Settings.normalize_persona). Not an
    # enum on purpose: a bad value must fall back, never 422.
    persona: str | None = None

    model_config = {"populate_by_name": True}


class SpeakVideoResponse(BaseModel):
    video_url: str = Field(alias="videoUrl")
    duration_ms: int = Field(alias="durationMs")
    latency_ms: int = Field(alias="latencyMs")

    model_config = {"populate_by_name": True}


class DirectorSessionRequest(BaseModel):
    persona: str | None = None

    model_config = {"populate_by_name": True}


class DirectorSpeakRequest(BaseModel):
    audio_base64: str = Field(alias="audioBase64")
    format: str = "wav"
    persona: str | None = None

    model_config = {"populate_by_name": True}


class DirectorHeartbeatRequest(BaseModel):
    token: str
    state: str = "live"

    model_config = {"populate_by_name": True}


@asynccontextmanager
async def _lifespan(app: FastAPI) -> Any:
    yield
    # A session left open on shutdown keeps billing per second forever —
    # stop() before the async client that would proxy its last requests goes
    # away.
    app.state.director.stop()
    await app.state.async_http_client.aclose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="chair-video", lifespan=_lifespan)
    app.state.settings = settings
    app.state.cache = SpeakVideoCache()
    app.state.http_client = httpx.Client(timeout=30.0)
    app.state.async_http_client = httpx.AsyncClient(timeout=15.0)
    app.state.director = DirectorManager(settings)

    if STATIC_DIR.exists():
        app.mount("/stage", StaticFiles(directory=STATIC_DIR, html=True), name="stage")

    @app.post("/speak-video")
    def speak_video(req: SpeakVideoRequest) -> SpeakVideoResponse:
        settings: Settings = app.state.settings
        cache: SpeakVideoCache = app.state.cache
        http_client: httpx.Client = app.state.http_client
        persona = settings.normalize_persona(req.persona)

        if not req.audio_url and not req.audio_base64:
            raise HTTPException(422, "one of audioUrl or audioBase64 is required")

        if req.audio_base64:
            audio_bytes = decode_base64_audio(req.audio_base64)
            key = audio_key(audio_bytes, persona)
        else:
            assert req.audio_url is not None
            try:
                audio_bytes = fetch_audio(req.audio_url, http_client)
            except httpx.HTTPError as exc:
                raise HTTPException(502, f"could not fetch audioUrl: {exc}") from exc
            key = audio_key(audio_bytes, persona)

        cached = cache.get(key)
        if cached is not None:
            log.info("speak_video.cache_hit", key=key, persona=persona)
            return SpeakVideoResponse(videoUrl=cached["videoUrl"], durationMs=cached["durationMs"], latencyMs=0)

        try:
            fal = FalClient(settings, client=http_client)
        except FalError as exc:
            raise HTTPException(500, str(exc)) from exc

        try:
            audio_url = req.audio_url or fal.upload(
                audio_bytes, f"audio/{req.format}", f"speak.{req.format}"
            )
            # The winning lip-sync model (see README latency table) re-syncs an
            # existing video rather than animating a still, so it's fed the
            # persona's idle loop, not the portrait.
            video_url = _persona_idle_url(app, fal, settings, persona)
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"fal upload failed: {exc}") from exc

        try:
            result = fal.run(
                settings.lipsync_model,
                {"video_url": video_url, "audio_url": audio_url},
            )
        except FalError as exc:
            raise HTTPException(502, str(exc)) from exc

        video = result.data.get("video")
        result_url = video.get("url") if isinstance(video, dict) else video
        if not result_url:
            raise HTTPException(502, f"fal result had no video url: {result.data}")

        duration_ms = wav_duration_ms(audio_bytes) or 0
        cache.set(key, {"videoUrl": result_url, "durationMs": duration_ms})
        return SpeakVideoResponse(videoUrl=result_url, durationMs=duration_ms, latencyMs=result.latency_ms)

    @app.get("/idle")
    def idle(persona: str | None = None) -> FileResponse:
        settings: Settings = app.state.settings
        resolved = settings.normalize_persona(persona)
        path = PACKAGE_ROOT / settings.idle_video_path(resolved)
        if not path.exists():
            raise HTTPException(404, f"no idle asset at {path}")
        media_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        return FileResponse(path, media_type=media_type)

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        settings: Settings = app.state.settings
        http_client: httpx.Client = app.state.http_client
        director: DirectorManager = app.state.director
        fal_reachable = False
        if settings.fal_configured:
            try:
                http_client.head(settings.fal_base_url, timeout=5.0)
                fal_reachable = True
            except httpx.HTTPError:
                fal_reachable = False
        return {
            "falConfigured": settings.fal_configured,
            "falReachable": fal_reachable,
            "lipsyncModel": settings.lipsync_model,
            "avatarModel": settings.avatar_model,
            "director": director.snapshot(),
        }

    @app.post("/director/session/start")
    def director_session_start(req: DirectorSessionRequest) -> dict[str, Any]:
        settings: Settings = app.state.settings
        director: DirectorManager = app.state.director
        if not settings.fal_configured:
            raise HTTPException(500, "FAL_KEY is not set")
        session = director.start(settings.normalize_persona(req.persona))
        return {"sessionId": session.session_id, "persona": session.persona}

    @app.post("/director/session/stop")
    def director_session_stop() -> dict[str, Any]:
        app.state.director.stop()
        return {"stopped": True}

    @app.post("/director/speak")
    def director_speak(req: DirectorSpeakRequest) -> dict[str, Any]:
        settings: Settings = app.state.settings
        http_client: httpx.Client = app.state.http_client
        director: DirectorManager = app.state.director
        if not settings.fal_configured:
            raise HTTPException(500, "FAL_KEY is not set")

        audio_bytes = decode_base64_audio(req.audio_base64)
        try:
            fal = FalClient(settings, client=http_client)
            audio_url = fal.upload(audio_bytes, f"audio/{req.format}", f"speak.{req.format}")
        except (FalError, httpx.HTTPError) as exc:
            raise HTTPException(502, f"fal upload failed: {exc}") from exc

        session = director.speak(audio_url, settings.normalize_persona(req.persona))
        return {"sessionId": session.session_id, "promptVersion": session.prompt_version}

    @app.post("/director/heartbeat")
    def director_heartbeat(req: DirectorHeartbeatRequest) -> dict[str, Any]:
        director: DirectorManager = app.state.director
        ok = director.heartbeat(req.token, req.state)
        if not ok:
            raise HTTPException(404, "no active session for this token")
        return {"ok": True}

    @app.get("/director/events")
    async def director_events() -> StreamingResponse:
        director: DirectorManager = app.state.director
        queue = director.subscribe()

        async def gen() -> Any:
            try:
                while True:
                    payload = await queue.get()
                    yield f"data: {payload}\n\n"
            except asyncio.CancelledError:
                pass
            finally:
                director.unsubscribe(queue)

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.api_route("/director/fal-proxy", methods=["GET", "POST"])
    async def director_fal_proxy(request: Request) -> Any:
        settings: Settings = app.state.settings
        director: DirectorManager = app.state.director
        async_client: httpx.AsyncClient = app.state.async_http_client

        if not director.verify_token(request.headers.get(PROXY_TOKEN_HEADER)):
            raise HTTPException(401, "missing or invalid director session token")

        target = request.headers.get(PROXY_TARGET_HEADER)
        if not target:
            raise HTTPException(400, f"missing {PROXY_TARGET_HEADER} header")
        parsed = urlsplit(target)
        # Exact host match, not a suffix check — "wma.fal.run.evil.com" or a
        # userinfo trick ("wma.fal.run@evil.com") must not pass.
        if parsed.scheme != "https" or parsed.hostname != settings.director_proxy_host or "@" in parsed.netloc:
            raise HTTPException(403, "target host not allowlisted")
        if not settings.fal_key:
            raise HTTPException(500, "FAL_KEY is not set")

        forward_headers = {
            k: v for k, v in request.headers.items() if k.lower() in PROXY_REQUEST_HEADER_ALLOWLIST
        }
        forward_headers["authorization"] = f"Key {settings.fal_key}"
        body = await request.body()

        try:
            upstream = await async_client.request(
                request.method, target, headers=forward_headers, content=body or None
            )
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"fal proxy request failed: {exc}") from exc

        return StreamingResponse(
            iter([upstream.content]),
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type"),
        )

    return app


def _persona_idle_url(app: FastAPI, fal: FalClient, settings: Settings, persona: str) -> str:
    """A persona's idle loop doesn't change between requests — upload it once
    per process per persona and reuse fal's CDN URL rather than re-uploading
    every call."""
    cache: dict[str, str] = getattr(app.state, "idle_urls", None) or {}
    if persona in cache:
        return cache[persona]
    path = PACKAGE_ROOT / settings.idle_video_path(persona)
    if not path.exists():
        raise HTTPException(500, f"idle video not found at {path}")
    url = fal.upload(path.read_bytes(), "video/mp4", path.name)
    cache[persona] = url
    app.state.idle_urls = cache
    return url


app = create_app()
