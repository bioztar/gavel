from __future__ import annotations

from ears.frames import TurnEnd, TurnStart, TurnTick
from ears.turns import TurnTracker


def tracker() -> TurnTracker:
    return TurnTracker(gap_ms=1500, tick_ms=10_000)


def test_short_pauses_stay_one_turn() -> None:
    t = tracker()
    [start] = t.speaking_start("a", 0.0)
    assert isinstance(start, TurnStart) and start.previous_discord_id is None
    t.speaking_end("a", 2.0)
    assert t.tick(3.0) == []  # 1s pause < gap
    assert t.speaking_start("a", 3.0) == []  # same turn resumes
    t.speaking_end("a", 5.0)
    [end] = t.tick(6.6)
    assert isinstance(end, TurnEnd)
    assert end.turn_id == start.turn_id
    assert end.speaking_ms == 4000
    assert end.duration_ms == 5000  # ends when they went quiet, not when we noticed


def test_ticks_every_interval_while_holding_the_floor() -> None:
    t = tracker()
    t.speaking_start("a", 0.0)
    assert t.tick(9.9) == []
    [tick] = t.tick(10.0)
    assert isinstance(tick, TurnTick)
    assert tick.duration_ms == 10_000 and tick.speaking_ms == 10_000
    assert t.tick(15.0) == []
    [tick2] = t.tick(20.0)
    assert isinstance(tick2, TurnTick) and tick2.duration_ms == 20_000


def test_new_speaker_carries_previous() -> None:
    t = tracker()
    t.speaking_start("a", 0.0)
    t.speaking_end("a", 1.0)
    t.tick(3.0)
    [start] = t.speaking_start("b", 4.0)
    assert isinstance(start, TurnStart) and start.previous_discord_id == "a"


def test_crosstalk_is_two_turns() -> None:
    t = tracker()
    t.speaking_start("a", 0.0)
    t.speaking_start("b", 0.5)
    assert {x["discordId"] for x in t.active()} == {"a", "b"}


def test_close_all_ends_open_turns() -> None:
    t = tracker()
    t.speaking_start("a", 0.0)
    [end] = t.close_all(3.0)
    assert isinstance(end, TurnEnd) and end.speaking_ms == 3000
    assert t.active() == []
