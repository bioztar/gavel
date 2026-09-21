"""The speaking-indicator debounce, on its own."""

from __future__ import annotations

from ears_meet.speaking import SpeakingDebouncer, Transition

T = 1_700_000_000.0


def test_start_is_announced_after_on_ms_with_the_flip_time() -> None:
    d = SpeakingDebouncer(on_ms=150, off_ms=400)
    assert d.observe("a", True, T) == []
    assert d.tick(T + 0.1) == []
    assert d.tick(T + 0.15) == [Transition("a", True, T)]
    assert d.is_speaking("a") and d.speaking() == ["a"]


def test_a_blink_shorter_than_on_ms_never_reaches_the_wire() -> None:
    d = SpeakingDebouncer(on_ms=150, off_ms=400)
    d.observe("a", True, T)
    assert d.observe("a", False, T + 0.08) == []
    assert d.tick(T + 5) == []
    assert not d.is_speaking("a")


def test_end_is_announced_after_off_ms_with_the_flip_time() -> None:
    d = SpeakingDebouncer(on_ms=150, off_ms=400)
    d.observe("a", True, T)
    d.tick(T + 0.2)
    assert d.observe("a", False, T + 3.0) == []
    assert d.tick(T + 3.3) == []
    assert d.tick(T + 3.4) == [Transition("a", False, T + 3.0)]
    assert d.speaking() == []


def test_a_gap_between_words_does_not_end_speech() -> None:
    d = SpeakingDebouncer(on_ms=150, off_ms=400)
    d.observe("a", True, T)
    d.tick(T + 0.2)
    d.observe("a", False, T + 1.0)
    assert d.observe("a", True, T + 1.2) == []  # back on before off_ms elapsed
    assert d.tick(T + 2.0) == []
    assert d.is_speaking("a")


def test_repeated_same_state_flips_are_ignored() -> None:
    d = SpeakingDebouncer(on_ms=150, off_ms=400)
    d.observe("a", True, T)
    assert d.observe("a", True, T + 0.05) == []
    assert d.tick(T + 0.15) == [Transition("a", True, T)]  # start time is the first flip


def test_two_people_are_independent() -> None:
    d = SpeakingDebouncer(on_ms=150, off_ms=400)
    d.observe("a", True, T)
    d.observe("b", True, T + 0.05)
    out = d.tick(T + 0.2)
    assert {t.participant_id for t in out} == {"a", "b"}
    d.observe("a", False, T + 1)
    assert d.tick(T + 1.4) == [Transition("a", False, T + 1)]
    assert d.speaking() == ["b"]


def test_forget_ends_announced_speech_immediately() -> None:
    d = SpeakingDebouncer(on_ms=150, off_ms=400)
    d.observe("a", True, T)
    d.tick(T + 0.2)
    assert d.forget("a", T + 1) == [Transition("a", False, T + 1)]
    assert d.forget("a", T + 2) == []
    d.observe("b", True, T)
    assert d.forget("b", T + 0.01) == []  # never announced: nothing to end


def test_close_all() -> None:
    d = SpeakingDebouncer(on_ms=150, off_ms=400)
    d.observe("a", True, T)
    d.observe("b", True, T)
    d.tick(T + 0.2)
    out = d.close_all(T + 9)
    assert sorted(t.participant_id for t in out) == ["a", "b"]
    assert all(not t.speaking and t.at == T + 9 for t in out)
    assert d.speaking() == []
