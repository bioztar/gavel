"""The join-page's own record of invites, keyed by our `sessionId`.

In-memory, on purpose: this package's `sessionId` only needs to live long
enough for someone to click Join or for the event to start. It is not the
same id as the one `ears-discord` hands back from `POST /api/sessions` —
that one is recorded here once the meeting actually starts.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class InviteRecord:
    session_id: str
    title: str
    start: datetime
    end: datetime
    agenda: dict
    context: str = ""
    started: bool = False
    ears_meeting_id: str | None = None
    ears_session_id: str | None = None
    # The last brain state seen for *this* meeting's session. The brain keeps one
    # live session in memory and drops it when the next one starts, so the room
    # page banks each live poll here — that banked copy is what the report is
    # rendered from once the meeting is over. See room.py.
    last_state: dict | None = None


@dataclass
class InviteStore:
    _records: dict[str, InviteRecord] = field(default_factory=dict)
    _locks: dict[str, asyncio.Lock] = field(default_factory=lambda: defaultdict(asyncio.Lock))

    def save(self, record: InviteRecord) -> None:
        self._records[record.session_id] = record

    def get(self, session_id: str) -> InviteRecord | None:
        return self._records.get(session_id)

    def pending(self) -> list[InviteRecord]:
        return [r for r in self._records.values() if not r.started]

    def mark_started(self, session_id: str, ears_meeting_id: str, ears_session_id: str) -> None:
        record = self._records[session_id]
        record.started = True
        record.ears_meeting_id = ears_meeting_id
        record.ears_session_id = ears_session_id

    def bank_state(self, session_id: str, state: dict) -> None:
        record = self._records.get(session_id)
        if record is not None:
            record.last_state = state

    def lock_for(self, session_id: str) -> asyncio.Lock:
        return self._locks[session_id]
