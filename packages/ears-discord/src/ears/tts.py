"""SLNG text-to-speech over HTTP — for the console's say-box, not the chair.

The chair's voice is the brain's job (it sends finished audio in `speak`). This
exists so a human at the console can talk into the call through the same
playback path — and, since the console can now pick the voice, in the same
voice. The two synthesizers used to be configured separately and kept in step
by hand; there is one setting now, and ears is where it lives.

The voice is read per line, never snapshotted at construction: a change made in
the console has to reach the *next* thing said, not the next restart. The brain
does the same (`packages/brain/src/chair/tts.ts` takes its config as a getter
and reopens its streaming socket when the voice changes).

Each model names its voice differently: Fish takes `reference_id`, Deepgram
Aura takes `model`. Everything else returns audio bytes FFmpeg can play.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from .settings import Settings

# Deepgram Aura-2 English voices. A starting point for the console's picker, not
# a closed set: the picker also takes a typed id, and SLNG_TTS_VOICES replaces
# this list without a code change, so a voice added upstream needs neither.
DEFAULT_TTS_VOICES: tuple[str, ...] = (
    "aura-2-thalia-en",
    "aura-2-asteria-en",
    "aura-2-luna-en",
    "aura-2-athena-en",
    "aura-2-hera-en",
    "aura-2-minerva-en",
    "aura-2-theia-en",
    "aura-2-orion-en",
    "aura-2-arcas-en",
    "aura-2-perseus-en",
    "aura-2-zeus-en",
)


class TtsError(Exception):
    pass


@dataclass(frozen=True)
class TtsResult:
    audio: bytes
    content_type: str
    latency_ms: int


class SlngTts:
    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient,
        voice: Callable[[], str] | None = None,
    ) -> None:
        self.model = settings.slng_tts_model
        # A getter, not a value: see the module docstring. Defaults to the
        # environment's voice, which is what this was before it was selectable.
        self._voice: Callable[[], str] = voice or (lambda: settings.slng_tts_voice)
        self._url = f"{settings.slng_base_url.rstrip('/')}/v1/tts/{settings.slng_tts_model}"
        self._headers = {"Authorization": f"Bearer {settings.slng_api_key}"}
        self._timeout = settings.slng_timeout_seconds
        self._client = client

    @property
    def voice(self) -> str:
        return self._voice()

    def _body(self, text: str) -> dict[str, str]:
        voice = self._voice()
        if "fish" in self.model:
            return {"text": text, "reference_id": voice}
        if "aura" in self.model:
            return {"text": text, "model": voice}
        return {"text": text, "voice_id": voice}

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
