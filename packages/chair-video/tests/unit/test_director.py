"""DirectorManager: pure logic, no network — clock is injected so timing
(heartbeat timeout, max-session self-restart) is deterministic."""

from __future__ import annotations

from chair_video.director import DirectorManager
from chair_video.settings import Settings


def _settings(**overrides: object) -> Settings:
    return Settings(fal_key="test-key", **overrides)  # type: ignore[arg-type]


def test_start_is_idempotent_while_a_session_is_active() -> None:
    manager = DirectorManager(_settings())
    first = manager.start("funky")
    second = manager.start("formal")
    assert second is first
    assert second.persona == "funky"


def test_stop_clears_state() -> None:
    manager = DirectorManager(_settings())
    manager.start("funky")
    manager.stop()
    assert manager.snapshot() == {"active": False}


def test_speak_increments_prompt_version_across_calls() -> None:
    manager = DirectorManager(_settings())
    first = manager.speak("https://cdn/a.wav", "funky")
    assert first.prompt_version == 2  # 1 at start(), +1 for this speak()
    second = manager.speak("https://cdn/b.wav", "funky")
    assert second.prompt_version == 3
    assert second.session_id == first.session_id


def test_heartbeat_rejects_wrong_token() -> None:
    manager = DirectorManager(_settings())
    session = manager.start("funky")
    assert manager.heartbeat("not-the-token", "live") is False
    assert manager.heartbeat(session.token, "live") is True


def test_verify_token_false_with_no_active_session() -> None:
    manager = DirectorManager(_settings())
    assert manager.verify_token("anything") is False


def test_snapshot_degrades_after_heartbeat_timeout() -> None:
    clock = [0.0]
    manager = DirectorManager(_settings(director_heartbeat_timeout_s=15.0), now=lambda: clock[0])
    session = manager.start("funky")
    manager.heartbeat(session.token, "live")
    assert manager.snapshot()["state"] == "live"

    clock[0] += 20.0
    assert manager.snapshot()["state"] == "degraded"


def test_snapshot_before_first_heartbeat_is_starting_then_degraded() -> None:
    clock = [0.0]
    manager = DirectorManager(_settings(director_heartbeat_timeout_s=15.0), now=lambda: clock[0])
    manager.start("funky")
    assert manager.snapshot()["state"] == "starting"

    clock[0] += 20.0
    assert manager.snapshot()["state"] == "degraded"


def test_speak_past_max_session_restarts_with_a_fresh_session() -> None:
    clock = [0.0]
    manager = DirectorManager(_settings(director_max_session_s=60.0), now=lambda: clock[0])
    first = manager.speak("https://cdn/a.wav", "funky")

    clock[0] += 61.0
    second = manager.speak("https://cdn/b.wav", "funky")

    assert second.session_id != first.session_id
    assert second.prompt_version == 2


def test_unknown_persona_falls_back_to_settings_default() -> None:
    manager = DirectorManager(_settings())
    session = manager.start("not-a-real-persona")
    assert session.persona == "funky"


# --- the credit leak: nothing ever closed a session once speaking stopped -----


def _clocked(**overrides: object) -> tuple[DirectorManager, list[float]]:
    t = [0.0]
    return DirectorManager(_settings(**overrides), now=lambda: t[0]), t


def test_sweep_stops_a_session_that_stopped_speaking() -> None:
    manager, t = _clocked(director_idle_stop_s=120.0)
    manager.start("formal")
    manager.speak("https://example.com/a.wav", "formal")

    t[0] = 119.0
    assert manager.sweep() is None
    assert manager.snapshot()["active"] is True

    t[0] = 121.0
    assert manager.sweep() == "idle"
    assert manager.snapshot() == {"active": False}


def test_speaking_keeps_the_session_alive() -> None:
    manager, t = _clocked(director_idle_stop_s=120.0)
    manager.start("formal")
    for at in (100.0, 200.0, 300.0):
        t[0] = at
        manager.speak("https://example.com/a.wav", "formal")
        assert manager.sweep() is None
    assert manager.snapshot()["active"] is True


def test_sweep_stops_a_session_past_the_fal_cap_even_while_speaking() -> None:
    manager, t = _clocked(director_idle_stop_s=120.0, director_max_session_s=60.0)
    manager.start("formal")
    t[0] = 61.0
    manager.speak("https://example.com/a.wav", "formal")
    # speak() already restarts past the cap, so the fresh session survives...
    assert manager.sweep() is None
    t[0] = 130.0
    # ...and the sweeper ends it without needing another utterance.
    assert manager.sweep() in {"idle", "max_session"}
    assert manager.snapshot() == {"active": False}


def test_sweep_on_no_session_is_a_no_op() -> None:
    manager, _ = _clocked()
    assert manager.sweep() is None


def test_close_subscribers_releases_every_sse_queue() -> None:
    from chair_video.director import _SHUTDOWN

    manager, _ = _clocked()
    queues = [manager.subscribe() for _ in range(3)]
    for q in queues:
        q.get_nowait()  # the hello event

    manager.close_subscribers()

    for q in queues:
        assert q.get_nowait() == _SHUTDOWN
