"""Turns: raw speaking events smoothed into "who holds the floor".

speaking.start/end flicker on every breath. A turn survives pauses shorter than
`gap_ms`, reports itself every `tick_ms` while it lasts, and closes once the
speaker has been silent for `gap_ms`. Several people can hold turns at once —
crosstalk is real and the brain should see it.

Pure: every method takes `now` (epoch seconds) and returns the frames to emit.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from .frames import TurnEnd, TurnStart, TurnTick, iso

TurnFrame = TurnStart | TurnTick | TurnEnd


@dataclass
class _Turn:
    turn_id: str
    discord_id: str
    started_at: float
    last_tick_at: float
    # Closed speaking intervals, in ms.
    speaking_ms: int = 0
    # Set while speaking; None while paused.
    speaking_since: float | None = None
    # When the speaker last went quiet. Only meaningful while paused.
    quiet_since: float = 0.0

    def speaking_ms_at(self, now: float) -> int:
        open_ms = int((now - self.speaking_since) * 1000) if self.speaking_since is not None else 0
        return self.speaking_ms + open_ms


class TurnTracker:
    def __init__(self, gap_ms: int, tick_ms: int) -> None:
        self.gap = gap_ms / 1000
        self.tick_every = tick_ms / 1000
        self._turns: dict[str, _Turn] = {}
        self._last_turn_owner: str | None = None

    def current_turn_id(self, discord_id: str) -> str | None:
        turn = self._turns.get(discord_id)
        return turn.turn_id if turn else None

    def active(self) -> list[dict[str, object]]:
        """Snapshot for /state."""
        return [
            {"discordId": t.discord_id, "turnId": t.turn_id, "startedAt": iso(t.started_at)}
            for t in self._turns.values()
        ]

    def speaking_start(self, discord_id: str, now: float) -> list[TurnFrame]:
        turn = self._turns.get(discord_id)
        if turn is not None:
            if turn.speaking_since is None:
                turn.speaking_since = now
            return []
        turn = _Turn(
            turn_id=str(uuid.uuid4()),
            discord_id=discord_id,
            started_at=now,
            last_tick_at=now,
            speaking_since=now,
        )
        self._turns[discord_id] = turn
        previous, self._last_turn_owner = self._last_turn_owner, discord_id
        return [
            TurnStart(discord_id=discord_id, turn_id=turn.turn_id, previous_discord_id=previous)
        ]

    def speaking_end(self, discord_id: str, now: float) -> list[TurnFrame]:
        turn = self._turns.get(discord_id)
        if turn is not None and turn.speaking_since is not None:
            turn.speaking_ms += int((now - turn.speaking_since) * 1000)
            turn.speaking_since = None
            turn.quiet_since = now
        return []

    def tick(self, now: float) -> list[TurnFrame]:
        out: list[TurnFrame] = []
        for discord_id, turn in list(self._turns.items()):
            if turn.speaking_since is None and now - turn.quiet_since >= self.gap:
                out.append(self._end(turn, ended_at=turn.quiet_since))
                del self._turns[discord_id]
            elif now - turn.last_tick_at >= self.tick_every:
                turn.last_tick_at = now
                out.append(
                    TurnTick(
                        discord_id=discord_id,
                        turn_id=turn.turn_id,
                        started_at=iso(turn.started_at),
                        duration_ms=int((now - turn.started_at) * 1000),
                        speaking_ms=turn.speaking_ms_at(now),
                    )
                )
        return out

    def close_all(self, now: float) -> list[TurnFrame]:
        """End every open turn — the call is over or the connection dropped."""
        out: list[TurnFrame] = []
        for turn in self._turns.values():
            self.speaking_end(turn.discord_id, now)
            out.append(self._end(turn, ended_at=now))
        self._turns.clear()
        return out

    @staticmethod
    def _end(turn: _Turn, ended_at: float) -> TurnEnd:
        return TurnEnd(
            discord_id=turn.discord_id,
            turn_id=turn.turn_id,
            started_at=iso(turn.started_at),
            ended_at=iso(ended_at),
            duration_ms=int((ended_at - turn.started_at) * 1000),
            speaking_ms=turn.speaking_ms,
        )
