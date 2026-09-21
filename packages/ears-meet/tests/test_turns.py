"""Turn logic: pauses shorter than the gap are one turn; ticks while it lasts; crosstalk."""

from __future__ import annotations

from ears_meet.frames import TurnEnd, TurnStart, TurnTick
from ears_meet.turns import TurnTracker

T = 1_700_000_000.0


def test_a_turn_opens_once_and_survives_short_pauses() -> None:
    turns = TurnTracker(gap_ms=1500, tick_ms=5000)
    (start,) = turns.speaking_start("a", T)
    assert isinstance(start, TurnStart) and start.previous_discord_id is None
    assert turns.speaking_start("a", T + 1) == []  # already holding
    assert turns.speaking_end("a", T + 2) == []
    assert turns.tick(T + 3) == []  # 1 s quiet < gap
    turns.speaking_start("a", T + 3.2)
    assert turns.current_turn_id("a") == start.turn_id


def test_a_turn_closes_after_the_gap_with_speaking_ms() -> None:
    turns = TurnTracker(gap_ms=1500, tick_ms=60_000)
    (start,) = turns.speaking_start("a", T)
    turns.speaking_end("a", T + 4)
    assert turns.tick(T + 5) == []
    (end,) = turns.tick(T + 5.5)
    assert isinstance(end, TurnEnd)
    assert end.turn_id == start.turn_id
    assert end.speaking_ms == 4000
    assert end.ended_at.startswith("2023-11-14T22:13:24.000")
    assert turns.current_turn_id("a") is None


def test_ticks_while_the_turn_lasts() -> None:
    turns = TurnTracker(gap_ms=1500, tick_ms=1000)
    turns.speaking_start("a", T)
    assert turns.tick(T + 0.5) == []
    (tick,) = turns.tick(T + 1.0)
    assert isinstance(tick, TurnTick) and tick.duration_ms == 1000 and tick.speaking_ms == 1000
    turns.speaking_end("a", T + 1.2)
    (tick2,) = turns.tick(T + 2.0)
    assert isinstance(tick2, TurnTick) and tick2.speaking_ms == 1200


def test_next_speaker_sees_the_previous_owner() -> None:
    turns = TurnTracker(gap_ms=1500, tick_ms=5000)
    turns.speaking_start("a", T)
    turns.speaking_end("a", T + 1)
    turns.tick(T + 3)
    (start,) = turns.speaking_start("b", T + 3)
    assert isinstance(start, TurnStart) and start.previous_discord_id == "a"


def test_crosstalk_is_two_turns() -> None:
    turns = TurnTracker(gap_ms=1500, tick_ms=5000)
    turns.speaking_start("a", T)
    turns.speaking_start("b", T + 0.5)
    assert {t["discordId"] for t in turns.active()} == {"a", "b"}
    turns.speaking_end("a", T + 1)
    (end,) = turns.tick(T + 3)
    assert isinstance(end, TurnEnd) and end.discord_id == "a"
    assert turns.current_turn_id("b") is not None


def test_close_all_ends_everything_now() -> None:
    turns = TurnTracker(gap_ms=1500, tick_ms=5000)
    turns.speaking_start("a", T)
    turns.speaking_start("b", T)
    out = turns.close_all(T + 2)
    assert sorted(f.discord_id for f in out) == ["a", "b"]
    assert all(isinstance(f, TurnEnd) and f.speaking_ms == 2000 for f in out)
    assert turns.active() == []
