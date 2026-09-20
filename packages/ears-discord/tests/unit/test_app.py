"""The whole pipeline minus Discord: voice callbacks in, frames out over the WebSocket."""

from __future__ import annotations

import asyncio
import base64
import dataclasses
import time
from typing import Any

from fastapi.testclient import TestClient

from ears.app import Ears
from ears.bus import Bus
from ears.db.store import Store
from ears.frames import Participant
from ears.settings import Settings
from ears.stt import SttResult
from ears.wire import create_api

ANA = Participant(discord_id="2", name="Ana")


class FakeStt:
    def __init__(self) -> None:
        self.keyterms: list[str] | None = None

    async def transcribe(self, pcm: bytes, keyterms: list[str] | None = None) -> SttResult:
        self.keyterms = keyterms
        return SttResult(text="QA needs two weeks", confidence=0.97, latency_ms=5)


class FakeVoice:
    def __init__(self) -> None:
        self.played: list[bytes] = []
        self.sources: list[Any] = []
        self.priorities: list[bool] = []
        self.done: Any = None
        self.mutes: list[tuple[str, bool]] = []
        self.fail_mute: str | None = None

    def play(self, audio: bytes, done: Any, priority: bool = False) -> bool:
        self.played.append(audio)
        self.priorities.append(priority)
        self.done = done
        return True

    def play_source(self, source: Any, done: Any, priority: bool = False) -> bool:
        self.sources.append(source)
        self.priorities.append(priority)
        self.done = done
        return True

    def stop_playback(self) -> None:
        self.done(None)

    async def set_mute(self, discord_id: str, muted: bool, reason: str | None = None) -> None:
        if self.fail_mute:
            raise RuntimeError(self.fail_mute)
        self.mutes.append((discord_id, muted))


def make_ears(stt: Any = None) -> Ears:
    settings = Settings(_env_file=None, slng_api_key="k", stt_mode="http")  # type: ignore[call-arg]
    return Ears(settings, Store(None), Bus(None, "t", 10), stt)


def test_hello_then_speaking_and_turn_frames() -> None:
    ears = make_ears()
    ears.on_joined("g", "c1", [ANA])
    with TestClient(create_api(ears)).websocket_connect("/") as ws:
        assert ws.receive_json()["type"] == "voice"  # the chair's voice, before anything else
        assert ws.receive_json()["type"] == "ready"
        assert ws.receive_json()["participants"] == [{"discordId": "2", "name": "Ana"}]
        assert ws.receive_json()["type"] == "session.started"  # joining voice opened one
        ears.on_speaking("2", True, 100.0)
        assert ws.receive_json()["type"] == "speaking.start"
        turn = ws.receive_json()
        assert turn["type"] == "turn.start" and turn["discordId"] == "2"


async def test_transcript_frame_carries_name_turn_and_keyterms() -> None:
    stt = FakeStt()
    ears = make_ears(stt)
    ears.on_joined("g", "c1", [ANA])
    sent: list[dict[str, Any]] = []
    ears.hub.broadcast = sent.append  # type: ignore[method-assign]
    ears.on_speaking("2", True, 100.0)
    loud = (b"\x00\x10" * 2) * 960  # 20 ms, well above the silence floor
    for i in range(50):  # 1 s
        ears.on_pcm("2", loud, 100.0 + i * 0.02)
    for chunk in ears.segmenter.tick(105.0):
        ears._transcribe(chunk)
    await ears.shutdown()
    [transcript] = [f for f in sent if f["type"] == "transcript"]
    assert transcript["name"] == "Ana"
    assert transcript["text"] == "QA needs two weeks"
    assert transcript["final"] is True
    assert transcript["turnId"] is not None
    assert stt.keyterms == ["Ana"]


def test_silence_is_never_sent_to_stt() -> None:
    stt = FakeStt()
    ears = make_ears(stt)
    ears.on_pcm("2", b"\x00\x00" * 2 * 960 * 50, 0.0)
    assert stt.keyterms is None


def test_speak_plays_and_reports_spoken() -> None:
    ears = make_ears()
    voice = FakeVoice()
    ears.voice = voice  # type: ignore[assignment]
    sent: list[dict[str, Any]] = []
    debug: list[dict[str, Any]] = []
    ears.hub.broadcast = sent.append  # type: ignore[method-assign]
    ears.console.broadcast = debug.append  # type: ignore[method-assign]
    audio = base64.b64encode(b"RIFF....").decode()
    ears.command(
        f'{{"type":"speak","utteranceId":"u1","audio":"{audio}","text":"Karen says hello"}}'
    )
    ears.command(f'{{"type":"speak","utteranceId":"u2","audio":"{audio}"}}')
    assert len(voice.played) == 1  # queued, not overlapped
    queued = next(f for f in debug if f.get("kind") == "speak.queued")
    assert queued["text"] == "Karen says hello"
    voice.done(None)
    assert sent[-1] == sent[-1] | {"type": "spoken", "utteranceId": "u1", "interrupted": False}
    assert len(voice.played) == 2
    ears.command('{"type":"stop"}')
    assert sent[-1]["utteranceId"] == "u2" and sent[-1]["interrupted"] is True


def test_speak_without_voice_reports_error() -> None:
    ears = make_ears()
    sent: list[dict[str, Any]] = []
    ears.hub.broadcast = sent.append  # type: ignore[method-assign]
    ears.command('{"type":"speak","utteranceId":"u1","audio":"AAAA"}')
    assert sent[-1]["type"] == "spoken" and sent[-1]["error"] == "not in a voice channel"


def _wired() -> tuple[Ears, FakeVoice, list[dict[str, Any]]]:
    ears = make_ears()
    voice = FakeVoice()
    ears.voice = voice  # type: ignore[assignment]
    sent: list[dict[str, Any]] = []
    ears.hub.broadcast = sent.append  # type: ignore[method-assign]
    return ears, voice, sent


AUDIO = base64.b64encode(b"RIFF....").decode()


def test_priority_speak_preempts_and_jumps_the_queue() -> None:
    ears, voice, sent = _wired()
    ears.command(f'{{"type":"speak","utteranceId":"u1","audio":"{AUDIO}"}}')
    ears.command(f'{{"type":"speak","utteranceId":"u2","audio":"{AUDIO}"}}')
    ears.command(f'{{"type":"speak","utteranceId":"p1","audio":"{AUDIO}","priority":true}}')
    spoken = [f for f in sent if f["type"] == "spoken"]
    assert spoken == [spoken[0] | {"utteranceId": "u1", "interrupted": True}]
    assert voice.priorities == [False, True]  # p1 played next, as priority speaker
    voice.done(None)
    assert voice.priorities == [False, True, False]  # then u2, still queued


def test_priority_speak_does_not_cut_another_priority_line() -> None:
    ears, voice, sent = _wired()
    ears.command(f'{{"type":"speak","utteranceId":"p1","audio":"{AUDIO}","priority":true}}')
    ears.command(f'{{"type":"speak","utteranceId":"p2","audio":"{AUDIO}","priority":true}}')
    assert not [f for f in sent if f["type"] == "spoken"]
    assert len(voice.played) == 1


def test_gated_speak_waits_for_a_pause() -> None:
    ears, voice, _ = _wired()
    now = time.time()
    ears.on_pcm("2", b"\x00\x10" * 1920, now)  # someone is mid-sentence
    ears.command(
        f'{{"type":"speak","utteranceId":"g1","audio":"{AUDIO}","quietMs":600,"maxWaitMs":8000}}'
    )
    assert voice.played == []  # held while they talk
    ears._last_voice_at = now - 1.0  # a second of quiet
    ears._play_next()  # what the clock does each tick
    assert len(voice.played) == 1


def test_room_noise_is_not_someone_talking() -> None:
    ears, voice, _ = _wired()
    ears.on_pcm("2", b"\x01\x00" * 1920, time.time())  # an open mic, nobody speaking
    ears.command(
        f'{{"type":"speak","utteranceId":"g1","audio":"{AUDIO}","quietMs":600,"maxWaitMs":8000}}'
    )
    assert len(voice.played) == 1


def test_gated_speak_plays_anyway_after_max_wait() -> None:
    ears, voice, _ = _wired()
    ears._last_voice_at = time.time()  # nobody ever pauses
    ears.command(
        f'{{"type":"speak","utteranceId":"g1","audio":"{AUDIO}","quietMs":600,"maxWaitMs":3000}}'
    )
    assert voice.played == []
    ears._playback[0] = dataclasses.replace(ears._playback[0], queued_at=time.time() - 4)
    ears._play_next()
    assert len(voice.played) == 1


def test_gated_priority_line_does_not_cut_karen_before_the_pause() -> None:
    ears, _, sent = _wired()
    ears.command(f'{{"type":"speak","utteranceId":"u1","audio":"{AUDIO}"}}')
    ears.on_pcm("2", b"\x00\x10" * 1920, time.time())
    ears.command(
        f'{{"type":"speak","utteranceId":"p1","audio":"{AUDIO}","priority":true,'
        f'"quietMs":600,"maxWaitMs":3000}}'
    )
    assert not [f for f in sent if f["type"] == "spoken"]  # u1 keeps playing
    assert ears._playback[0].utterance_id == "p1"  # but p1 is next in line


async def test_mute_emits_moderation_and_lifts_itself() -> None:
    ears, voice, sent = _wired()
    ears.command('{"type":"mute","discordId":"2","seconds":0.05,"reason":"off agenda"}')
    await asyncio.sleep(0.01)
    muted = [f for f in sent if f["type"] == "moderation"]
    assert muted[0]["action"] == "muted" and muted[0]["discordId"] == "2"
    assert muted[0]["until"] > 0
    await asyncio.sleep(0.1)
    assert voice.mutes == [("2", True), ("2", False)]
    assert [f["action"] for f in sent if f["type"] == "moderation"] == ["muted", "unmuted"]


async def test_mute_is_capped_and_unmute_only_touches_our_mutes() -> None:
    ears, voice, sent = _wired()
    ears.command('{"type":"unmute","discordId":"9"}')
    assert sent[-1] == sent[-1] | {"action": "failed", "error": "not muted by gavel"}
    ears.command('{"type":"mute","discordId":"2","seconds":3600}')
    await asyncio.sleep(0.01)
    until_s = sent[-1]["until"] / 1000 - sent[-1]["atMs"] / 1000
    assert until_s <= 61
    ears.command('{"type":"unmute","discordId":"2"}')
    await asyncio.sleep(0.01)
    assert voice.mutes == [("2", True), ("2", False)]


async def test_failed_mute_is_reported() -> None:
    ears, voice, sent = _wired()
    voice.fail_mute = "Missing Permissions"
    ears.command('{"type":"mute","discordId":"2","seconds":5}')
    await asyncio.sleep(0.01)
    assert sent[-1] == sent[-1] | {"action": "failed", "error": "Missing Permissions"}
    assert not ears._muted


async def test_ending_the_session_unmutes_everyone() -> None:
    ears, voice, _ = _wired()
    ears.on_joined("g", "c1", [ANA])
    ears.command('{"type":"mute","discordId":"2","seconds":30}')
    await asyncio.sleep(0.01)
    ears.end_session()
    await asyncio.sleep(0.01)
    assert voice.mutes == [("2", True), ("2", False)]


def test_memories_round_trip_without_postgres() -> None:
    ears = make_ears()
    client = TestClient(create_api(ears))
    made = client.post(
        "/api/memories",
        json={"discordId": "2", "name": "Ana", "summary": "pricing page", "sessionId": "s1"},
    ).json()
    assert made["status"] == "open" and made["kind"] == "parked"
    assert [m["id"] for m in client.get("/api/memories?discordId=2&status=open").json()] == [
        made["id"]
    ]
    assert client.get("/api/memories?discordId=3").json() == []
    done = client.patch(f"/api/memories/{made['id']}", json={"status": "resolved"}).json()
    assert done["status"] == "resolved" and done["resolvedAt"]
    assert client.get("/api/memories?status=open").json() == []


def test_llm_calls_keep_running_session_totals() -> None:
    ears = make_ears()
    client = TestClient(create_api(ears))
    body = {"sessionId": "s1", "agent": "relevance", "model": "m", "inputTokens": 100}
    client.post("/api/llm-calls", json=body | {"costUsd": 0.001})
    totals = client.post("/api/llm-calls", json=body | {"costUsd": 0.002}).json()
    assert totals["calls"] == 2 and totals["inputTokens"] == 200
    assert abs(totals["costUsd"] - 0.003) < 1e-9
    ok = client.post(
        "/api/interventions",
        json={"sessionId": "s1", "kind": "silence", "line": "Ana?", "source": "template"},
    )
    assert ok.json() == {"ok": True}


def test_streamed_speak_plays_as_chunks_arrive_and_reports_spoken_once() -> None:
    ears, voice, sent = _wired()
    pcm = base64.b64encode(bytes(range(256)) * 15).decode()  # 3840 bytes of mono PCM
    ears.command('{"type":"speak.start","utteranceId":"s1","text":"Hi","priority":true}')
    assert len(voice.sources) == 1 and voice.priorities == [True]  # plays before any audio
    stream = voice.sources[0]
    assert stream.read() == bytes(3840)  # nothing yet: silence, still playing
    ears.command(f'{{"type":"speak.chunk","utteranceId":"s1","audio":"{pcm}"}}')
    ears.command('{"type":"speak.chunk","utteranceId":"nope","audio":"AAAA"}')  # unknown: ignored
    ears.command('{"type":"speak.end","utteranceId":"s1"}')
    frames = [stream.read(), stream.read(), stream.read()]
    assert [len(f) for f in frames] == [3840, 3840, 0]  # mono doubled to stereo, then done
    assert not [f for f in sent if f["type"] == "spoken"]
    voice.done(None)
    assert [f["utteranceId"] for f in sent if f["type"] == "spoken"] == ["s1"]


def test_stop_releases_queued_streams() -> None:
    ears, _, _ = _wired()
    ears.command('{"type":"speak.start","utteranceId":"s1"}')
    ears.command('{"type":"speak.start","utteranceId":"s2"}')
    ears.command('{"type":"stop"}')
    assert "s2" not in ears._streams


def test_bad_stream_format_is_rejected() -> None:
    ears, voice, _ = _wired()
    ears.command('{"type":"speak.start","utteranceId":"s1","sampleRate":24000}')
    assert voice.sources == []
