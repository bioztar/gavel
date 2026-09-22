"""The composition root with the browser mocked: observer events in, contract frames out,
brain commands in, `spoken` out. No network, no Google, no PulseAudio."""

from __future__ import annotations

import asyncio
import base64
import json

import pytest

from conftest import Harness, make_settings
from ears_meet import selectors as sel
from ears_meet.attribution import UNATTRIBUTED
from ears_meet.settings import MissingSetting
from ears_meet.stt_stream import Segment

# --- join / roster ----------------------------------------------------------------


def test_join_emits_ready_with_the_roster_and_a_session(harness: Harness) -> None:
    harness.tiles(("spaces/x/devices/1", "Vitaly"), ("spaces/x/devices/2", "Ana"))
    assert harness.frames == []  # nothing on the wire before we are in the call
    harness.ears.on_joined("abc-defg-hij")
    types = [f["type"] for f in harness.frames]
    assert types == ["session.started", "ready"]
    ready = harness.frames[1]
    assert ready["channelId"] == "abc-defg-hij"
    assert ready["participants"] == [
        {"discordId": "spaces/x/devices/1", "name": "Vitaly"},
        {"discordId": "spaces/x/devices/2", "name": "Ana"},
    ]
    assert "Karen" not in json.dumps(ready)  # the chair is not a participant
    assert ready["atMs"] == harness.ms() and ready["at"].endswith("Z")


def test_participants_on_join_and_leave(joined: Harness) -> None:
    joined.advance(1)
    joined.tiles(("p1", "Vitaly"), ("p2", "Ana"), ("p3", "Marc"))
    (frame,) = joined.of_type("participants")
    assert [p["name"] for p in frame["participants"]] == ["Vitaly", "Ana", "Marc"]
    joined.frames.clear()
    joined.tiles(("p1", "Vitaly"), ("p3", "Marc"))
    (frame,) = joined.of_type("participants")
    assert [p["discordId"] for p in frame["participants"]] == ["p1", "p3"]
    joined.frames.clear()
    joined.tiles(("p1", "Vitaly"), ("p3", "Marc"))  # unchanged: silence
    assert joined.frames == []


def test_hello_replays_ready_participants_and_session(joined: Harness) -> None:
    hello = joined.ears.hello()
    assert [f["type"] for f in hello] == ["voice", "ready", "participants", "session.started"]
    assert all("atMs" in f for f in hello)


# --- speaking -------------------------------------------------------------------


def test_indicator_flicker_becomes_debounced_speaking_frames(joined: Harness) -> None:
    t0 = joined.clock.now
    joined.indicator("p1", True)
    joined.advance(0.1)
    assert joined.of_type("speaking.start") == []
    joined.advance(0.1)
    (start,) = joined.of_type("speaking.start")
    assert start["discordId"] == "p1" and start["atMs"] == int(t0 * 1000)
    (turn,) = joined.of_type("turn.start")
    assert turn["discordId"] == "p1" and turn["previousDiscordId"] is None

    joined.indicator("p1", False)  # a gap between words...
    joined.advance(0.2)
    joined.indicator("p1", True)  # ...that closes before off_ms
    joined.advance(1.0)
    assert joined.of_type("speaking.end") == []

    t_off = joined.clock.now
    joined.indicator("p1", False)
    joined.advance(0.5)
    (end,) = joined.of_type("speaking.end")
    assert end["discordId"] == "p1" and end["atMs"] == int(t_off * 1000)


def test_a_blink_never_reaches_the_wire(joined: Harness) -> None:
    joined.indicator("p2", True)
    joined.advance(0.05)
    joined.indicator("p2", False)
    joined.advance(3)
    assert joined.of_type("speaking.start", "speaking.end", "turn.start") == []


def test_turn_closes_after_the_gap(joined: Harness) -> None:
    joined.indicator("p1", True)
    joined.advance(0.3)
    joined.indicator("p1", False)
    joined.advance(0.5)
    assert joined.of_type("turn.end") == []
    joined.advance(joined.settings.turn_gap_ms / 1000 + 0.2)
    (end,) = joined.of_type("turn.end")
    assert end["discordId"] == "p1" and end["speakingMs"] == pytest.approx(300, abs=1)


def test_the_bots_own_indicator_is_not_a_participant_speaking(joined: Harness) -> None:
    joined.indicator("self", True)
    joined.advance(1)
    assert joined.of_type("speaking.start") == []
    assert joined.ears.status()["egressSeen"] is True


def test_leaving_mid_sentence_ends_the_speech(joined: Harness) -> None:
    joined.indicator("p2", True)
    joined.advance(0.3)
    joined.tiles(("p1", "Vitaly"))
    ends = joined.of_type("speaking.end")
    assert [e["discordId"] for e in ends] == ["p2"]
    assert joined.of_type("participants")[-1]["participants"] == [
        {"discordId": "p1", "name": "Vitaly"}
    ]


def test_unknown_or_empty_observer_events_are_ignored(joined: Harness) -> None:
    joined.ears.on_observer_event({"kind": "indicator", "t": joined.ms(), "id": "", "on": True})
    joined.ears.on_observer_event({"kind": "weird", "t": joined.ms()})
    joined.ears.on_observer_event(
        {"kind": "indicator", "id": "p1", "on": True}
    )  # no `t`: app clock
    joined.advance(0.3)
    (start,) = joined.of_type("speaking.start")
    assert start["discordId"] == "p1"


# --- captions -> transcript ------------------------------------------------------


def test_captions_become_attributed_transcripts(joined: Harness) -> None:
    joined.captions_visible(True)
    assert joined.ears.transcript_source() == "captions"
    joined.caption(1, "Ana", "We ship on")
    joined.caption(1, "Ana", "We ship on Friday.")
    joined.advance(0.6)
    frames = joined.of_type("transcript")
    assert [f["final"] for f in frames] == [False, False, True]
    assert {f["discordId"] for f in frames} == {"p2"}
    assert frames[-1]["text"] == "We ship on Friday." and frames[-1]["name"] == "Ana"
    assert len({f["utteranceId"] for f in frames}) == 1
    assert [f["seq"] for f in frames] == [0, 1, 2]


def test_caption_from_an_unknown_name_is_unattributed_and_own_lines_dropped(
    joined: Harness,
) -> None:
    joined.captions_visible(True)
    joined.caption(1, "Someone Else", "hello")
    joined.caption(2, "You", "the chair's own line")
    joined.caption(3, "Karen (gavel)", "also the chair")
    joined.advance(0.6)
    frames = joined.of_type("transcript")
    assert all(f["discordId"] == UNATTRIBUTED and f["name"] == "Someone Else" for f in frames)
    assert "chair" not in json.dumps(frames)


def test_captions_are_ignored_when_source_is_stt_or_none(joined: Harness) -> None:
    joined.ears.settings.transcript_source = "none"
    joined.captions_visible(True)
    joined.caption(1, "Ana", "hello")
    joined.advance(1)
    assert joined.of_type("transcript") == []


# --- STT on the mix -> transcript, attributed by the speaking timeline ------------


def test_stt_segments_are_attributed_by_the_speaking_timeline(joined: Harness) -> None:
    t0 = joined.clock.now
    joined.indicator("p2", True)
    joined.advance(3)
    joined.indicator("p2", False)
    joined.advance(1)
    joined.indicator("p1", True)
    joined.advance(3)
    joined.frames.clear()
    joined.ears._on_segments(
        "meet:mix",
        [
            Segment("meet:mix", "first words", t0 + 0.5, t0 + 2.5, "0", 0.9, False),
            Segment("meet:mix", "more words", t0 + 2.6, t0 + 3.0, "0", 0.9, True),
            Segment("meet:mix", "then me", t0 + 4.5, t0 + 6.0, "1", 0.8, True),
        ],
    )
    frames = joined.of_type("transcript")
    assert [(f["discordId"], f["name"], f["final"]) for f in frames] == [
        ("p2", "Ana", False),
        ("p2", "Ana", True),
        ("p1", "Vitaly", True),
    ]
    assert frames[0]["utteranceId"] == frames[1]["utteranceId"]
    assert frames[2]["utteranceId"] != frames[1]["utteranceId"]
    assert frames[0]["turnId"] is None  # p2's turn had closed by the time the segment arrived
    assert frames[2]["turnId"] is not None


def test_pcm_feeds_stt_only_when_stt_is_the_source(joined: Harness) -> None:
    assert joined.ears.stream is None  # no SLNG key in tests
    joined.ears.on_pcm(b"\x00" * 3840, joined.clock.now)
    loud = b"\x00\x40" * 1920
    joined.ears.on_pcm(loud, joined.clock.now)
    ingress = joined.ears.status()["ingress"]
    assert ingress == {"frames": 2, "audible": 1}


# --- brain -> ears -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_speak_plays_and_reports_spoken(joined: Harness) -> None:
    audio = base64.b64encode(b"\x00" * 100).decode()
    joined.ears.command(json.dumps({"type": "speak", "utteranceId": "u1", "audio": audio}))
    assert joined.player.played == [b"\x00" * 100]
    await asyncio.sleep(0.01)
    (spoken,) = joined.of_type("spoken")
    assert (
        spoken["utteranceId"] == "u1" and spoken["interrupted"] is False and spoken["error"] is None
    )


@pytest.mark.asyncio
async def test_priority_speak_preempts_and_the_queue_drains_in_order(joined: Harness) -> None:
    joined.player.duration_s = 10  # nothing finishes on its own
    a = base64.b64encode(b"a").decode()
    joined.ears.command(json.dumps({"type": "speak", "utteranceId": "u1", "audio": a}))
    joined.ears.command(json.dumps({"type": "speak", "utteranceId": "u2", "audio": a}))
    joined.ears.command(
        json.dumps({"type": "speak", "utteranceId": "u3", "audio": a, "priority": True})
    )
    spoken = joined.of_type("spoken")
    assert [(s["utteranceId"], s["interrupted"]) for s in spoken] == [("u1", True)]
    assert joined.ears.status()["playing"] == "u3"
    joined.player.stop()  # u3 "finishes"
    assert joined.ears.status()["playing"] == "u2"


@pytest.mark.asyncio
async def test_stop_drops_the_queue(joined: Harness) -> None:
    joined.player.duration_s = 10
    a = base64.b64encode(b"a").decode()
    joined.ears.command(json.dumps({"type": "speak", "utteranceId": "u1", "audio": a}))
    joined.ears.command(json.dumps({"type": "speak", "utteranceId": "u2", "audio": a}))
    joined.ears.command('{"type":"stop"}')
    spoken = joined.of_type("spoken")
    assert [(s["utteranceId"], s["interrupted"]) for s in spoken] == [("u1", True)]
    assert joined.ears.status()["queued"] == 0 and joined.ears.status()["playing"] is None


@pytest.mark.asyncio
async def test_streamed_speech(joined: Harness) -> None:
    joined.ears.command('{"type":"speak.start","utteranceId":"s1","channels":1}')
    chunk = base64.b64encode(b"\x01\x02" * 10).decode()
    joined.ears.command(json.dumps({"type": "speak.chunk", "utteranceId": "s1", "audio": chunk}))
    joined.ears.command('{"type":"speak.end","utteranceId":"s1"}')
    assert joined.player.played == [b"<stream>"]
    await asyncio.sleep(0.01)
    (spoken,) = joined.of_type("spoken")
    assert spoken["utteranceId"] == "s1"


def test_speak_with_bad_audio_reports_an_error(joined: Harness) -> None:
    joined.ears.command('{"type":"speak","utteranceId":"bad","audio":"$$$"}')
    (spoken,) = joined.of_type("spoken")
    assert spoken["utteranceId"] == "bad" and "base64" in spoken["error"]
    assert joined.player.played == []


def test_speak_outside_a_call_fails_honestly(harness: Harness) -> None:
    harness.ears.command(json.dumps({"type": "speak", "utteranceId": "u", "audio": "AAAA"}))
    (spoken,) = harness.of_type("spoken")
    assert spoken["error"] == "not in a call"


@pytest.mark.asyncio
async def test_quiet_ms_holds_the_line_until_the_room_is_quiet(joined: Harness) -> None:
    joined.indicator("p1", True)
    joined.advance(0.3)
    a = base64.b64encode(b"a").decode()
    joined.ears.command(
        json.dumps(
            {"type": "speak", "utteranceId": "u", "audio": a, "quietMs": 1000, "maxWaitMs": 60000}
        )
    )
    assert joined.player.played == []  # held: p1 is talking
    joined.indicator("p1", False)
    joined.advance(0.5)
    assert joined.player.played == []
    joined.advance(1.0)
    assert joined.player.played == [b"a"]


def test_mute_is_refused_honestly(joined: Harness) -> None:
    joined.ears.command('{"type":"mute","discordId":"p1","seconds":30}')
    (mod,) = joined.of_type("moderation")
    assert mod["action"] == "failed" and mod["discordId"] == "p1" and "Meet" in mod["error"]


def test_garbage_commands_are_ignored(joined: Harness) -> None:
    joined.ears.command("nope")
    joined.ears.command('{"type":"speak.chunk","utteranceId":"never","audio":"AA=="}')
    assert joined.frames == []


# --- egress proof ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spoken_carries_an_error_when_the_call_never_heard_us(joined: Harness) -> None:
    joined.ears.verify_egress = True
    joined.indicator("self", False)  # the self tile exists (its indicator has been seen)
    joined.player.duration_s = 0
    joined.ears.command(
        json.dumps({"type": "speak", "utteranceId": "u", "audio": base64.b64encode(b"a").decode()})
    )
    joined.clock.advance(3)  # 3 s of playback, indicator never lit
    joined.player.stop()
    (spoken,) = joined.of_type("spoken")
    assert spoken["error"] and "unheard" in spoken["error"]


@pytest.mark.asyncio
async def test_spoken_is_clean_when_our_tile_lit_up(joined: Harness) -> None:
    joined.ears.verify_egress = True
    joined.indicator("self", False)
    joined.player.duration_s = 0
    joined.ears.command(
        json.dumps({"type": "speak", "utteranceId": "u", "audio": base64.b64encode(b"a").decode()})
    )
    joined.clock.advance(1)
    joined.indicator("self", True)
    joined.clock.advance(2)
    joined.player.stop()
    (spoken,) = joined.of_type("spoken")
    assert spoken["error"] is None


# --- sessions --------------------------------------------------------------------


def test_session_started_carries_the_agenda_bound_to_meet_ids(harness: Harness) -> None:
    harness.ears.saved_agenda = {
        "purpose": "Decide",
        "attendees": [{"discordId": "old-ana", "name": "Ana", "role": "host"}],
        "topics": [{"id": "t1", "title": "A", "owner": "old-ana", "mustHear": ["old-ana"]}],
    }
    harness.tiles(("m2", "Ana"), ("m3", "Marc"))
    harness.ears.on_joined("abc-defg-hij")
    (started,) = harness.of_type("session.started")
    agenda = started["agenda"]
    assert agenda["attendees"][0] == {"discordId": "m2", "name": "Ana", "role": "host"}
    assert agenda["topics"][0]["owner"] == "m2" and agenda["topics"][0]["mustHear"] == ["m2"]
    assert started["sessionId"] == agenda["sessionId"] == harness.ears.session_id
    assert started["meetingId"] is None


def test_restarting_a_session_ends_the_old_one_and_closes_speech(joined: Harness) -> None:
    joined.indicator("p1", True)
    joined.advance(0.3)
    old = joined.ears.session_id
    new = joined.ears.start_session(title="Launch sync")
    types = [f["type"] for f in joined.frames]
    assert types[-3:] == ["turn.end", "session.ended", "session.started"] or types[-4:-1] == [
        "speaking.end",
        "turn.end",
        "session.ended",
    ]
    ended = joined.of_type("session.ended")[0]
    assert ended["sessionId"] == old and new != old
    assert joined.of_type("session.started")[-1]["title"] == "Launch sync"


# --- the surface -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_surface_health_reinstalls_the_observer_and_notices_the_call_ending(
    joined: Harness,
) -> None:
    joined.surface.observer_ok = False
    await joined.ears._surface_health(joined.clock.now)
    assert "install_observer" in joined.surface.calls
    joined.surface.in_call = False
    left: list[bool] = []

    async def on_leave() -> None:
        left.append(True)

    joined.ears.on_leave = on_leave
    await joined.ears._surface_health(joined.clock.now)
    assert left == [True] and joined.ears.channel_id is None


@pytest.mark.asyncio
async def test_alone_too_long_leaves(joined: Harness) -> None:
    joined.ears.settings.meet_leave_when_alone_s = 10
    joined.tiles()  # everybody else left
    joined.advance(11)
    await joined.ears._surface_health(joined.clock.now)
    assert "leave" in joined.surface.calls


@pytest.mark.asyncio
async def test_stage_failure_is_not_fatal(joined: Harness) -> None:
    joined.surface.stage_ok = False
    assert await joined.ears.present_stage() is False
    assert joined.ears.status()["stage"] is False and joined.ears.channel_id is not None


@pytest.mark.asyncio
async def test_self_check_names_the_missing_selector(joined: Harness) -> None:
    joined.surface.check = sel.SelfCheckResult(missing_required=["SPEAKING_INDICATOR"])
    result = await joined.ears.self_check()
    assert result is not None and not result.ok
    assert "SPEAKING_INDICATOR" in result.message() and "selectors.py" in result.message()
    assert joined.ears.status()["selfCheck"]["missing"] == ["SPEAKING_INDICATOR"]


# --- settings: auth is named, never valued --------------------------------------


def test_require_auth_names_the_missing_settings() -> None:
    s = make_settings(meet_profile_dir="", meet_bot_email="", meet_bot_password="")
    with pytest.raises(MissingSetting) as exc:
        s.require_auth()
    assert "MEET_PROFILE_DIR" in str(exc.value)
    assert "MEET_BOT_EMAIL and MEET_BOT_PASSWORD" in str(exc.value)
    with pytest.raises(MissingSetting, match="MEET_URL"):
        make_settings(meet_url="").require_auth()


def test_require_auth_never_echoes_a_value() -> None:
    secret = "hunter2-do-not-print"
    s = make_settings(meet_profile_dir="", meet_bot_email="bot@example.com", meet_bot_password="")
    with pytest.raises(MissingSetting) as exc:
        s.require_auth()
    assert "MEET_BOT_PASSWORD" in str(exc.value) and "bot@example.com" not in str(exc.value)
    ok = make_settings(
        meet_profile_dir="", meet_bot_email="bot@example.com", meet_bot_password=secret
    )
    ok.require_auth()
    assert secret not in repr(ok) and secret not in str(ok)


def test_settings_defaults_are_the_documented_ones() -> None:
    s = make_settings()
    assert (s.turn_gap_ms, s.turn_tick_ms) == (1500, 10_000)
    assert (s.pulse_sink_out, s.pulse_sink_in) == ("gavel_out", "gavel_in")
    assert s.stage_tab_title == "gavel-stage"
