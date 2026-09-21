"""The brain's store, in memory — and a JSONL recorder for every frame.

ears-discord keeps memories, interventions and model usage in Postgres so there is one
database. This package does not ship Postgres yet (see docs/EARS-MEET.md, "stubbed"):
the same REST routes exist (wire.py) and answer from memory, so the brain's calls
succeed and rows last for the process. The camelCase output matches
ears-discord/src/ears/db/store.py `_memory_out`, so the brain cannot tell.

`FrameLog` appends every emitted frame as one JSON line — what `scripts/live_check.py`
prints, and what tests/fixtures/*.jsonl were recorded with for the conformance test.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _memory_out(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "discordId": row["discord_id"],
        "name": row.get("name"),
        "kind": row["kind"],
        "summary": row["summary"],
        "quote": row.get("quote"),
        "topicId": row.get("topic_id"),
        "sessionId": row.get("session_id"),
        "status": row["status"],
        "createdAt": row["created_at"],
        "resolvedAt": row.get("resolved_at"),
    }


class MemoryStore:
    def __init__(self) -> None:
        self._memories: dict[str, dict[str, Any]] = {}
        self._interventions: list[dict[str, Any]] = []
        self._usage: dict[str, dict[str, float]] = {}

    async def add_memory(self, body: dict[str, Any]) -> dict[str, Any]:
        row = {
            **body,
            "id": str(uuid.uuid4()),
            "status": "open",
            "created_at": _now(),
            "resolved_at": None,
        }
        self._memories[row["id"]] = row
        return _memory_out(row)

    async def list_memories(
        self, discord_ids: list[str] | None, status: str | None, session_id: str | None
    ) -> list[dict[str, Any]]:
        rows = [
            r
            for r in self._memories.values()
            if (not discord_ids or r["discord_id"] in discord_ids)
            and (status is None or r["status"] == status)
            and (session_id is None or r.get("session_id") == session_id)
        ]
        return [_memory_out(r) for r in sorted(rows, key=lambda r: r["created_at"])]

    async def set_memory_status(self, memory_id: str, status: str) -> dict[str, Any] | None:
        row = self._memories.get(memory_id)
        if row is None:
            return None
        row["status"] = status
        row["resolved_at"] = _now() if status == "resolved" else None
        return _memory_out(row)

    def intervention(self, body: dict[str, Any]) -> None:
        self._interventions.append({**body, "at": _now()})

    def interventions(self) -> list[dict[str, Any]]:
        return list(self._interventions)

    def llm_call(self, body: dict[str, Any]) -> dict[str, float]:
        key = body.get("session_id") or "-"
        totals = self._usage.setdefault(
            key,
            {"calls": 0, "inputTokens": 0, "outputTokens": 0, "cachedTokens": 0, "costUsd": 0.0},
        )
        totals["calls"] += 1
        totals["inputTokens"] += body.get("input_tokens", 0)
        totals["outputTokens"] += body.get("output_tokens", 0)
        totals["cachedTokens"] += body.get("cached_tokens", 0)
        totals["costUsd"] += body.get("cost_usd", 0.0)
        return dict(totals)

    async def usage(self, session_id: str) -> dict[str, float]:
        return dict(self._usage.get(session_id, {}))


class FrameLog:
    """Append-only JSONL of emitted frames. `path` empty: disabled."""

    def __init__(self, path: str) -> None:
        self.path = Path(path).expanduser() if path else None
        self._fh: Any = None
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = self.path.open("a", encoding="utf-8")

    def write(self, frame: dict[str, Any]) -> None:
        if self._fh is None:
            return
        self._fh.write(json.dumps(frame, separators=(",", ":")) + "\n")
        self._fh.flush()

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None
