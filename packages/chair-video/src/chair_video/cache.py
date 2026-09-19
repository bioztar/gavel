"""In-memory cache for `/speak-video` results, keyed by a hash of the audio.

The chair repeats lines on stage (confirmations, time warnings). A repeated
line should cost nothing — no second fal call, no second wait.
"""

from __future__ import annotations

import hashlib
from typing import Any


def audio_key(audio_bytes: bytes) -> str:
    return hashlib.sha256(audio_bytes).hexdigest()


class SpeakVideoCache:
    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        return self._store.get(key)

    def set(self, key: str, value: dict[str, Any]) -> None:
        self._store[key] = value

    def __len__(self) -> int:
        return len(self._store)
