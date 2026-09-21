"""The wire models: camelCase, `discordId` kept verbatim, `at` + `atMs` on every frame."""

from __future__ import annotations

import json

from ears_meet.frames import (
    Participant,
    Participants,
    Ready,
    Speak,
    SpeakChunk,
    SpeakEnd,
    SpeakingEnd,
    SpeakingStart,
    SpeakStart,
    Spoken,
    Stop,
    Transcript,
    parse_brain_frame,
    stamp,
)

MEET_ID = "spaces/AbCdEf/devices/12"


def test_participant_keeps_the_contracts_field_name_for_a_meet_id() -> None:
    body = Participant(discord_id=MEET_ID, name="Ana").model_dump(by_alias=True)
    assert body == {"discordId": MEET_ID, "name": "Ana"}


def test_stamp_adds_iso_and_epoch_ms() -> None:
    body = stamp(SpeakingStart(discord_id=MEET_ID), 1_700_000_000.25)
    assert body["type"] == "speaking.start"
    assert body["discordId"] == MEET_ID
    assert body["atMs"] == 1_700_000_000_250
    assert body["at"] == "2023-11-14T22:13:20.250Z"


def test_ready_and_participants_shape() -> None:
    people = [Participant(discord_id="a", name="A"), Participant(discord_id="b", name="B")]
    ready = stamp(Ready(channel_id="abc-defg-hij", participants=people), 0)
    assert ready["channelId"] == "abc-defg-hij"
    assert ready["participants"] == [
        {"discordId": "a", "name": "A"},
        {"discordId": "b", "name": "B"},
    ]
    assert set(stamp(Participants(participants=people), 0)) == {
        "type",
        "participants",
        "at",
        "atMs",
    }


def test_speaking_end_and_spoken() -> None:
    assert stamp(SpeakingEnd(discord_id="a"), 0)["type"] == "speaking.end"
    spoken = stamp(Spoken(utterance_id="u1"), 0)
    assert spoken["utteranceId"] == "u1" and spoken["interrupted"] is False
    assert spoken["error"] is None


def test_transcript_is_json_serialisable_with_camel_case() -> None:
    body = stamp(
        Transcript(
            discord_id="a",
            name="A",
            text="hello",
            started_at="2024-01-01T00:00:00+00:00",
            ended_at="2024-01-01T00:00:01+00:00",
            utterance_id="u",
            seq=0,
            final=True,
            turn_id=None,
            confidence=None,
        ),
        0,
    )
    text = json.dumps(body)
    assert '"startedAt"' in text and '"utteranceId"' in text and '"discordId"' in text
    assert "discord_id" not in text


def test_parse_brain_frames() -> None:
    speak = parse_brain_frame('{"type":"speak","utteranceId":"u","audio":"AAAA","priority":true}')
    assert isinstance(speak, Speak) and speak.priority is True
    assert isinstance(parse_brain_frame('{"type":"stop"}'), Stop)
    start = parse_brain_frame('{"type":"speak.start","utteranceId":"u","channels":1}')
    assert isinstance(start, SpeakStart)
    assert isinstance(
        parse_brain_frame('{"type":"speak.chunk","utteranceId":"u","audio":"AA=="}'), SpeakChunk
    )
    assert isinstance(parse_brain_frame('{"type":"speak.end","utteranceId":"u"}'), SpeakEnd)


def test_parse_brain_frame_rejects_garbage() -> None:
    assert parse_brain_frame("not json") is None
    assert parse_brain_frame('{"type":"dance"}') is None
    assert parse_brain_frame('{"type":"speak"}') is None
