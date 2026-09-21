"""Who said a stretch of mixed audio: the DOM speaking timeline decides.

Meet hands us one mixed track, so SLNG's diarization labels ("0", "1") are stable
within a stream but tell us nothing about *which participant* a label is. The tiles do:
the debounced speaking timeline says who was talking when. A finalized STT segment
`[started_at, ended_at]` is attributed to the participant whose announced speech
overlaps it the most; failing any overlap, to whoever spoke last before it ended; failing
that, to `UNATTRIBUTED`, which keeps the words on the wire without inventing a person.

The timeline is pruned to `keep_s` so a long meeting does not grow it without bound.

Pure; every input is epoch seconds.
"""

from __future__ import annotations

from dataclasses import dataclass, field

UNATTRIBUTED = "meet:unattributed"


@dataclass
class _Interval:
    participant_id: str
    start: float
    end: float | None = None  # None: still speaking


@dataclass
class Attributor:
    keep_s: float = 600.0
    _intervals: list[_Interval] = field(default_factory=list)

    def speaking_start(self, participant_id: str, at: float) -> None:
        for iv in self._intervals:
            if iv.participant_id == participant_id and iv.end is None:
                return
        self._intervals.append(_Interval(participant_id, at))

    def speaking_end(self, participant_id: str, at: float) -> None:
        for iv in reversed(self._intervals):
            if iv.participant_id == participant_id and iv.end is None:
                iv.end = max(at, iv.start)
                return

    def attribute(self, started_at: float, ended_at: float) -> str:
        self._prune(ended_at)
        overlap: dict[str, float] = {}
        for iv in self._intervals:
            end = iv.end if iv.end is not None else max(ended_at, iv.start)
            lo, hi = max(iv.start, started_at), min(end, ended_at)
            if hi > lo:
                overlap[iv.participant_id] = overlap.get(iv.participant_id, 0.0) + (hi - lo)
        if overlap:
            return max(overlap.items(), key=lambda kv: kv[1])[0]
        before = [iv for iv in self._intervals if iv.start <= ended_at]
        if before:
            return max(before, key=lambda iv: iv.start).participant_id
        return UNATTRIBUTED

    def _prune(self, now: float) -> None:
        cutoff = now - self.keep_s
        self._intervals = [iv for iv in self._intervals if iv.end is None or iv.end >= cutoff]
