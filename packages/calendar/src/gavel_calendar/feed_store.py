"""Per-feed polling state: `UID` → last-seen `SEQUENCE` (dedupe) and health.

In-memory, same reasoning as `InviteStore` (store.py): only needs to survive
one process's lifetime. Callers address a feed by its index only — this
module never holds a feed URL, so nothing here can leak the credential.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FeedHealth:
    last_success: datetime | None = None
    event_count: int = 0
    last_error: str | None = None


@dataclass
class FeedRegistry:
    _sequences: dict[tuple[int, str], int] = field(default_factory=dict)
    _health: dict[int, FeedHealth] = field(default_factory=dict)

    def health_for(self, feed_index: int) -> FeedHealth:
        return self._health.setdefault(feed_index, FeedHealth())

    def record_success(self, feed_index: int, *, at: datetime, event_count: int) -> None:
        health = self.health_for(feed_index)
        health.last_success = at
        health.event_count = event_count
        health.last_error = None

    def record_error(self, feed_index: int, error: str) -> None:
        self.health_for(feed_index).last_error = error

    def seen_sequence(self, feed_index: int, uid: str) -> int | None:
        return self._sequences.get((feed_index, uid))

    def mark_seen(self, feed_index: int, uid: str, sequence: int) -> None:
        self._sequences[(feed_index, uid)] = sequence
