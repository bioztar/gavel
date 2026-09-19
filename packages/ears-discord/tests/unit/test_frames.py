from __future__ import annotations

from ears.frames import (
    Moderation,
    Mute,
    Speak,
    SpeakingStart,
    Stop,
    Unmute,
    parse_brain_frame,
    stamp,
)


def test_stamp_is_camel_case_with_timestamps() -> None:
    body = stamp(SpeakingStart(discord_id="42"), at=1_758_000_000.25)
    assert body == {
        "type": "speaking.start",
        "discordId": "42",
        "at": "2025-09-16T05:20:00.250Z",
        "atMs": 1_758_000_000_250,
    }


def test_parse_brain_frames() -> None:
    speak = parse_brain_frame(
        '{"type":"speak","utteranceId":"u1","audio":"AAAA","text":"Karen says hello","format":"wav"}'
    )
    assert isinstance(speak, Speak) and speak.utterance_id == "u1"
    assert speak.text == "Karen says hello"
    assert isinstance(parse_brain_frame('{"type":"stop"}'), Stop)
    assert parse_brain_frame('{"type":"speak"}') is None
    assert parse_brain_frame("not json") is None
    assert parse_brain_frame("[1]") is None


def test_parse_moderation_frames() -> None:
    speak = parse_brain_frame('{"type":"speak","utteranceId":"u","audio":"AA","priority":true}')
    assert isinstance(speak, Speak) and speak.priority is True
    mute = parse_brain_frame('{"type":"mute","discordId":"7","seconds":15,"reason":"r"}')
    assert isinstance(mute, Mute) and mute.discord_id == "7" and mute.seconds == 15
    assert isinstance(parse_brain_frame('{"type":"unmute","discordId":"7"}'), Unmute)
    assert parse_brain_frame('{"type":"mute","discordId":"7","seconds":0}') is None
    assert parse_brain_frame('{"type":"mute"}') is None


def test_moderation_frame_on_the_wire() -> None:
    body = stamp(Moderation(action="muted", discord_id="7", until=5), at=1.0)
    assert body["type"] == "moderation" and body["discordId"] == "7" and body["until"] == 5
