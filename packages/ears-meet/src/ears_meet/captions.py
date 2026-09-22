"""Meet's live captions, mined into attributed `transcript` frames.

When captions are on, Meet renders a few lines: a speaker name, then text that it keeps
editing in place as recognition settles, then a new line when the speaker changes or the
line gets long. The observer posts every edit as `{key, speaker, text, t}`; this module
turns that into utterances:

  * a line is one utterance (`utteranceId`), keyed by the observer's line key;
  * every edit is a non-final transcript with the words added since the last one
    (`seq` counts up) — so the brain sees text as it lands, like the streaming STT path;
  * a line that has not been edited for `settle_ms`, or whose key disappears, is final —
    the whole line, so the brain's last `final` chunk is the sentence it should keep.

Timing: `startedAt` is when the line first appeared, `endedAt` the last edit. Both are
DOM times, so they line up with the speaking events from the same page.

Pure: `observe()` and `tick()` take `now` and return `Caption`s to emit.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Caption:
    utterance_id: str
    speaker: str  # Meet's display name for the speaker, as captioned
    text: str  # what to put on the wire: the delta, or the whole line when final
    seq: int
    final: bool
    started_at: float
    ended_at: float


@dataclass
class _Line:
    utterance_id: str
    speaker: str
    text: str
    started_at: float
    updated_at: float
    seq: int = 0
    sent_upto: int = 0  # characters already emitted as non-final deltas


@dataclass
class CaptionMiner:
    settle_ms: int
    _lines: dict[int, _Line] = field(default_factory=dict)

    def observe(self, key: int, speaker: str, text: str, at: float) -> list[Caption]:
        text, speaker = text.strip(), speaker.strip()
        if not text:
            return []
        line = self._lines.get(key)
        if line is None:
            line = self._lines[key] = _Line(str(uuid.uuid4()), speaker, text, at, at)
            return [self._delta(line)]
        if line.speaker != speaker and speaker:
            # Meet re-attributed the line: finalize what we had under the old name, start over.
            out = self._finalize(key, line)
            line = self._lines[key] = _Line(str(uuid.uuid4()), speaker, text, at, at)
            return [*out, self._delta(line)]
        if text == line.text:
            return []
        if not text.startswith(line.text[: line.sent_upto]):
            # Meet rewrote already-sent words. Say so with a fresh delta of the whole line.
            line.sent_upto = 0
        line.text, line.updated_at = text, at
        return [self._delta(line)]

    def tick(self, now: float) -> list[Caption]:
        out: list[Caption] = []
        for key, line in list(self._lines.items()):
            if (now - line.updated_at) * 1000 >= self.settle_ms:
                out += self._finalize(key, line)
        return out

    def forget(self, key: int) -> list[Caption]:
        """The line scrolled out of the region: final now."""
        line = self._lines.get(key)
        return self._finalize(key, line) if line is not None else []

    def close_all(self) -> list[Caption]:
        out: list[Caption] = []
        for key, line in list(self._lines.items()):
            out += self._finalize(key, line)
        return out

    def _delta(self, line: _Line) -> Caption:
        delta = line.text[line.sent_upto :].strip()
        line.sent_upto = len(line.text)
        cap = Caption(
            line.utterance_id,
            line.speaker,
            delta or line.text,
            line.seq,
            False,
            line.started_at,
            line.updated_at,
        )
        line.seq += 1
        return cap

    def _finalize(self, key: int, line: _Line) -> list[Caption]:
        self._lines.pop(key, None)
        return [
            Caption(
                line.utterance_id,
                line.speaker,
                line.text,
                line.seq,
                True,
                line.started_at,
                line.updated_at,
            )
        ]
