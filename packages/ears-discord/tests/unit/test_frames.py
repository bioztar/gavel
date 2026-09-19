from __future__ import annotations

from ears.frames import Speak, SpeakingStart, Stop, parse_brain_frame, stamp


def test_stamp_is_camel_case_with_timestamps() -> None:
    body = stamp(SpeakingStart(discord_id="42"), at=1_758_000_000.25)
    assert body == {
        "type": "speaking.start",
        "discordId": "42",
        "at": "2025-09-16T05:20:00.250Z",
        "atMs": 1_758_000_000_250,
    }


def test_parse_brain_frames() -> None:
    speak = parse_brain_frame('{"type":"speak","utteranceId":"u1","audio":"AAAA","format":"wav"}')
    assert isinstance(speak, Speak) and speak.utterance_id == "u1"
    assert isinstance(parse_brain_frame('{"type":"stop"}'), Stop)
    assert parse_brain_frame('{"type":"speak"}') is None
    assert parse_brain_frame("not json") is None
    assert parse_brain_frame("[1]") is None
