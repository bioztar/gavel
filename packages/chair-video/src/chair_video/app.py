"""chair-video: turns the chair's spoken audio into a lip-synced talking-head
clip through fal. A service the brain calls — it makes no decisions."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

import httpx
import structlog
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from chair_video.audio import decode_base64_audio, fetch_audio, wav_duration_ms
from chair_video.cache import SpeakVideoCache, audio_key
from chair_video.fal import FalClient, FalError
from chair_video.settings import Settings, get_settings

log = structlog.get_logger()

PACKAGE_ROOT = Path(__file__).resolve().parents[2]


class SpeakVideoRequest(BaseModel):
    audio_url: str | None = Field(default=None, alias="audioUrl")
    audio_base64: str | None = Field(default=None, alias="audioBase64")
    format: str = "wav"

    model_config = {"populate_by_name": True}


class SpeakVideoResponse(BaseModel):
    video_url: str = Field(alias="videoUrl")
    duration_ms: int = Field(alias="durationMs")
    latency_ms: int = Field(alias="latencyMs")

    model_config = {"populate_by_name": True}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="chair-video")
    app.state.settings = settings
    app.state.cache = SpeakVideoCache()
    app.state.http_client = httpx.Client(timeout=30.0)

    @app.post("/speak-video")
    def speak_video(req: SpeakVideoRequest) -> SpeakVideoResponse:
        settings: Settings = app.state.settings
        cache: SpeakVideoCache = app.state.cache
        http_client: httpx.Client = app.state.http_client

        if not req.audio_url and not req.audio_base64:
            raise HTTPException(422, "one of audioUrl or audioBase64 is required")

        if req.audio_base64:
            audio_bytes = decode_base64_audio(req.audio_base64)
            key = audio_key(audio_bytes)
        else:
            assert req.audio_url is not None
            try:
                audio_bytes = fetch_audio(req.audio_url, http_client)
            except httpx.HTTPError as exc:
                raise HTTPException(502, f"could not fetch audioUrl: {exc}") from exc
            key = audio_key(audio_bytes)

        cached = cache.get(key)
        if cached is not None:
            log.info("speak_video.cache_hit", key=key)
            return SpeakVideoResponse(videoUrl=cached["videoUrl"], durationMs=cached["durationMs"], latencyMs=0)

        try:
            fal = FalClient(settings, client=http_client)
        except FalError as exc:
            raise HTTPException(500, str(exc)) from exc

        try:
            audio_url = req.audio_url or fal.upload(
                audio_bytes, f"audio/{req.format}", f"speak.{req.format}"
            )
            image_url = _avatar_url(app, fal, settings)
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"fal upload failed: {exc}") from exc

        try:
            result = fal.run(
                settings.lipsync_model,
                {"image_url": image_url, "audio_url": audio_url},
            )
        except FalError as exc:
            raise HTTPException(502, str(exc)) from exc

        video = result.data.get("video")
        video_url = video.get("url") if isinstance(video, dict) else video
        if not video_url:
            raise HTTPException(502, f"fal result had no video url: {result.data}")

        duration_ms = wav_duration_ms(audio_bytes) or 0
        cache.set(key, {"videoUrl": video_url, "durationMs": duration_ms})
        return SpeakVideoResponse(videoUrl=video_url, durationMs=duration_ms, latencyMs=result.latency_ms)

    @app.get("/idle")
    def idle() -> FileResponse:
        settings: Settings = app.state.settings
        path = PACKAGE_ROOT / (settings.idle_video_path or settings.avatar_image_path)
        if not path.exists():
            raise HTTPException(404, f"no idle asset at {path}")
        media_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        return FileResponse(path, media_type=media_type)

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        settings: Settings = app.state.settings
        http_client: httpx.Client = app.state.http_client
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
        }

    return app


def _avatar_url(app: FastAPI, fal: FalClient, settings: Settings) -> str:
    """The chair's portrait doesn't change between requests — upload it once
    per process and reuse fal's CDN URL rather than re-uploading every call."""
    cached: str | None = getattr(app.state, "avatar_url", None)
    if cached is not None:
        return cached
    path = PACKAGE_ROOT / settings.avatar_image_path
    if not path.exists():
        raise HTTPException(500, f"avatar image not found at {path}")
    content_type = mimetypes.guess_type(str(path))[0] or "image/png"
    url = fal.upload(path.read_bytes(), content_type, path.name)
    app.state.avatar_url = url
    return url


app = create_app()
