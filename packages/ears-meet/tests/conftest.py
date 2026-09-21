"""Test plumbing. No network, no Google account, no browser: the surface is faked."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from ears_meet import selectors as sel
from ears_meet.app import Ears
from ears_meet.pulse import FakePlayer
from ears_meet.settings import Settings

ROOT = Path(__file__).resolve().parents[3]
CONTRACT_FIXTURES = ROOT / "packages" / "contract" / "fixtures"
T0 = 1_700_000_000.0  # a fixed epoch second; fixtures are stable across runs


def make_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "meet_url": "https://meet.google.com/abc-defg-hij",
        "meet_profile_dir": "/nonexistent/profile",
        "slng_api_key": "",  # no STT / TTS in tests
        "speaking_on_ms": 150,
        "speaking_off_ms": 400,
        "caption_settle_ms": 300,
        "frames_file": "",
    }
    base.update(overrides)
    base["_env_file"] = None  # never read a developer's .env in tests
    return Settings(**base)


class Clock:
    def __init__(self, start: float = T0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> float:
        self.now += seconds
        return self.now


@dataclass
class FakeSurface:
    """Answers what the app asks of the browser, and remembers being asked."""

    unmuted: bool = True
    in_call: bool = True
    observer_ok: bool = True
    stage_ok: bool = True
    check: sel.SelfCheckResult = field(default_factory=sel.SelfCheckResult)
    calls: list[str] = field(default_factory=list)

    async def ensure_unmuted(self) -> bool:
        self.calls.append("ensure_unmuted")
        return self.unmuted

    async def self_check(self) -> sel.SelfCheckResult:
        self.calls.append("self_check")
        return self.check

    async def present_stage(self) -> bool:
        self.calls.append("present_stage")
        return self.stage_ok

    async def observer_alive(self) -> bool:
        self.calls.append("observer_alive")
        return self.observer_ok

    async def install_observer(self) -> None:
        self.calls.append("install_observer")

    async def is_in_call(self) -> bool:
        self.calls.append("is_in_call")
        return self.in_call

    async def leave(self) -> None:
        self.calls.append("leave")
        self.in_call = False


class Harness:
    """An `Ears` on a fake clock with the wire replaced by a list of frames."""

    def __init__(self, settings: Settings | None = None, clock: Clock | None = None) -> None:
        self.clock = clock or Clock()
        self.settings = settings or make_settings()
        self.player = FakePlayer()
        self.surface = FakeSurface()
        self.ears = Ears(self.settings, player=self.player, surface=self.surface, clock=self.clock)
        self.frames: list[dict[str, Any]] = []
        self.ears.hub.broadcast = self._capture  # type: ignore[method-assign]

    def _capture(self, frame: dict[str, Any]) -> None:
        self.frames.append(json.loads(json.dumps(frame)))

    # observer events, as observer.js posts them (t in epoch ms)
    def tiles(self, *people: tuple[str, str], self_tile: bool = True) -> None:
        participants = [{"id": i, "name": n, "self": False, "muted": False} for i, n in people]
        if self_tile:
            participants.append(
                {"id": "self", "name": "Karen (gavel)", "self": True, "muted": False}
            )
        self.ears.on_observer_event({"kind": "tiles", "t": self.ms(), "participants": participants})

    def indicator(self, pid: str, on: bool) -> None:
        self.ears.on_observer_event({"kind": "indicator", "t": self.ms(), "id": pid, "on": on})

    def caption(self, key: int, speaker: str, text: str) -> None:
        self.ears.on_observer_event(
            {"kind": "caption", "t": self.ms(), "key": key, "speaker": speaker, "text": text}
        )

    def captions_visible(self, visible: bool) -> None:
        self.ears.on_observer_event({"kind": "captions", "t": self.ms(), "visible": visible})

    def ms(self) -> int:
        return int(self.clock.now * 1000)

    def advance(self, seconds: float, step: float = 0.1) -> None:
        """Move the clock forward, beating the app clock every `step`."""
        end = self.clock.now + seconds
        while self.clock.now + step <= end + 1e-9:
            self.clock.advance(step)
            self.ears.tick(self.clock.now)
        if self.clock.now < end:
            self.clock.now = end
            self.ears.tick(self.clock.now)

    def advance_to(self, when: float) -> None:
        if when > self.clock.now:
            self.advance(when - self.clock.now)

    def of_type(self, *types: str) -> list[dict[str, Any]]:
        return [f for f in self.frames if f["type"] in types]


@pytest.fixture
def harness() -> Harness:
    return Harness()


@pytest.fixture
def joined(harness: Harness) -> Harness:
    harness.tiles(("p1", "Vitaly"), ("p2", "Ana"))
    harness.ears.on_joined("abc-defg-hij")
    harness.frames.clear()
    return harness
