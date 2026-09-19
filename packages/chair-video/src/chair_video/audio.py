"""Small helpers for the audio half of a `/speak-video` request."""

from __future__ import annotations

import base64
import contextlib
import wave
from io import BytesIO

import httpx


def decode_base64_audio(audio_base64: str) -> bytes:
    return base64.b64decode(audio_base64)


def fetch_audio(url: str, client: httpx.Client) -> bytes:
    response = client.get(url, timeout=30.0)
    response.raise_for_status()
    return response.content


def wav_duration_ms(audio_bytes: bytes) -> int | None:
    """Best-effort duration from a WAV header. Returns None for anything else
    (mp3, ogg, ...) rather than pulling in a decoder for a demo endpoint."""
    with contextlib.suppress(Exception), wave.open(BytesIO(audio_bytes), "rb") as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
        if rate:
            return int(frames / rate * 1000)
    return None
