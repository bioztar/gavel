"""The speaking-indicator debounce: raw tile flicker in, contract speaking events out.

Meet's indicator follows its own VAD frame by frame: it drops between words and blinks
on a cough. `speaking.start` / `speaking.end` are what the whole floor policy runs on,
so they must mean "this person is talking" and "this person has stopped", not "a bar
lit up". Rules:

  * an indicator that turns ON is announced as `speaking.start` once it has stayed on
    for `on_ms` — a blink shorter than that never reaches the wire;
  * an indicator that turns OFF is announced as `speaking.end` once it has stayed off
    for `off_ms` — a gap between words never ends speech;
  * the announced timestamps are the DOM times the indicator actually flipped, not the
    time we noticed — the same convention as ears-discord's `_stop_speaking`.

Pure: `observe()` and `tick()` take `now` (epoch seconds) and return transitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Transition:
    participant_id: str
    speaking: bool
    at: float  # epoch seconds — when the indicator flipped, not when we announced it


@dataclass
class _Person:
    announced: bool = False  # what the wire believes
    raw: bool = False  # what the indicator shows
    since: float = 0.0  # when `raw` last changed
    first_on: float = 0.0  # when the candidate start began (for the start timestamp)


@dataclass
class SpeakingDebouncer:
    on_ms: int
    off_ms: int
    _people: dict[str, _Person] = field(default_factory=dict)

    def observe(self, participant_id: str, on: bool, at: float) -> list[Transition]:
        """A raw indicator flip at DOM time `at`. Returns transitions that are due already."""
        p = self._people.setdefault(participant_id, _Person())
        if p.raw == on:
            return []
        p.raw, p.since = on, at
        if on and not p.announced:
            p.first_on = at
        return self.tick(at)

    def tick(self, now: float) -> list[Transition]:
        """Announce every pending start/end whose hold time has elapsed by `now`."""
        out: list[Transition] = []
        for pid, p in self._people.items():
            if p.raw and not p.announced and (now - p.since) * 1000 >= self.on_ms:
                p.announced = True
                out.append(Transition(pid, True, p.first_on))
            elif not p.raw and p.announced and (now - p.since) * 1000 >= self.off_ms:
                p.announced = False
                out.append(Transition(pid, False, p.since))
        return out

    def forget(self, participant_id: str, at: float) -> list[Transition]:
        """The tile is gone (they left). Ends their speech immediately, if announced."""
        p = self._people.pop(participant_id, None)
        if p is not None and p.announced:
            return [Transition(participant_id, False, at)]
        return []

    def close_all(self, at: float) -> list[Transition]:
        out = [Transition(pid, False, at) for pid, p in self._people.items() if p.announced]
        self._people.clear()
        return out

    def speaking(self) -> list[str]:
        return [pid for pid, p in self._people.items() if p.announced]

    def is_speaking(self, participant_id: str) -> bool:
        p = self._people.get(participant_id)
        return p is not None and p.announced
