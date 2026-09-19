"""SLNG text-to-speech over HTTP — for the console's say-box, not the chair.

The chair's voice is the brain's job (it sends finished audio in `speak`). This
exists so a human at the console can talk into the call through the same
playback path.

Each model names its voice differently: Fish takes `reference_id`, Deepgram
Aura takes `model`. Everything else returns audio bytes FFmpeg can play.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from .settings import Settings


class TtsError(Exception):
    pass


@dataclass(frozen=True)
class TtsResult:
    audio: bytes
    content_type: str
    latency_ms: int


class SlngTts:
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self.model = settings.slng_tts_model
        self._voice = settings.slng_tts_voice
        self._url = f"{settings.slng_base_url.rstrip('/')}/v1/tts/{settings.slng_tts_model}"
        self._headers = {"Authorization": f"Bearer {settings.slng_api_key}"}
        self._timeout = settings.slng_timeout_seconds
        self._client = client

    def _body(self, text: str) -> dict[str, str]:
        if "fish" in self.model:
            return {"text": text, "reference_id": self._voice}
        if "aura" in self.model:
            return {"text": text, "model": self._voice}
        return {"text": text, "voice_id": self._voice}

    async def synthesize(self, text: str) -> TtsResult:
        started = time.perf_counter()
        try:
            response = await self._client.post(
                self._url, headers=self._headers, json=self._body(text), timeout=self._timeout
            )
        except httpx.HTTPError as exc:
            raise TtsError(f"{type(exc).__name__}: {exc}") from exc
        latency_ms = int((time.perf_counter() - started) * 1000)
        content_type = response.headers.get("content-type", "")
        if response.status_code != 200 or not content_type.startswith("audio/"):
            raise TtsError(f"HTTP {response.status_code}: {response.text[:300]}")
        return TtsResult(audio=response.content, content_type=content_type, latency_ms=latency_ms)
