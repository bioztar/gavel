"""SLNG speech-to-text over HTTP, one request per utterance chunk.

HTTP rather than a streaming socket per speaker: Discord already hands us
utterance boundaries, and a monologue is chunked every CHUNK_MAX_MS, so a
request per chunk keeps transcripts flowing with far less machinery.

Route: POST {base}/v1/stt/{model}, multipart `audio` + options, Bearer auth.
Response is Deepgram-shaped: results.channels[0].alternatives[0].

Verbatim from ears-discord/src/ears/stt.py.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from .audio import wav_bytes
from .settings import Settings


class SttError(Exception):
    pass


@dataclass(frozen=True)
class SttResult:
    text: str
    confidence: float | None
    latency_ms: int


class SlngStt:
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._url = f"{settings.slng_base_url.rstrip('/')}/v1/stt/{settings.slng_stt_model}"
        self._headers = {"Authorization": f"Bearer {settings.slng_api_key}"}
        self._language = settings.slng_stt_language
        self._timeout = settings.slng_timeout_seconds
        self._client = client

    async def transcribe(self, pcm_16k_mono: bytes, keyterms: list[str] | None = None) -> SttResult:
        """`keyterms` boosts words the model would otherwise miss — participants' names.

        Nova 3 rejects `keywords`; `keyterm` is its replacement.
        """
        started = time.perf_counter()
        form: dict[str, str | list[str]] = {
            "language": self._language,
            "punctuate": "true",
            "smart_format": "true",
        }
        if keyterms:
            form["keyterm"] = keyterms
        try:
            response = await self._client.post(
                self._url,
                headers=self._headers,
                files={"audio": ("chunk.wav", wav_bytes(pcm_16k_mono), "audio/wav")},
                data=form,
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise SttError(f"{type(exc).__name__}: {exc}") from exc
        latency_ms = int((time.perf_counter() - started) * 1000)
        if response.status_code != 200:
            raise SttError(f"HTTP {response.status_code}: {response.text[:300]}")
        try:
            alt = response.json()["results"]["channels"][0]["alternatives"][0]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise SttError(f"unexpected response: {response.text[:300]}") from exc
        return SttResult(
            text=(alt.get("transcript") or "").strip(),
            confidence=alt.get("confidence"),
            latency_ms=latency_ms,
        )
