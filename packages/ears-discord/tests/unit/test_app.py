"""The whole pipeline minus Discord: voice callbacks in, frames out over the WebSocket."""

from __future__ import annotations

import base64
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
        self.done: Any = None

    def play(self, audio: bytes, done: Any) -> bool:
        self.played.append(audio)
        self.done = done
        return True

    def stop_playback(self) -> None:
        self.done(None)


def make_ears(stt: Any = None) -> Ears:
    settings = Settings(_env_file=None, slng_api_key="k")  # type: ignore[call-arg]
    return Ears(settings, Store(None), Bus(None, "t", 10), stt)


def test_hello_then_speaking_and_turn_frames() -> None:
    ears = make_ears()
    ears.on_joined("g", "c1", [ANA])
    with TestClient(create_api(ears)).websocket_connect("/") as ws:
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
    ears.hub.broadcast = sent.append  # type: ignore[method-assign]
    audio = base64.b64encode(b"RIFF....").decode()
    ears.command(f'{{"type":"speak","utteranceId":"u1","audio":"{audio}"}}')
    ears.command(f'{{"type":"speak","utteranceId":"u2","audio":"{audio}"}}')
    assert len(voice.played) == 1  # queued, not overlapped
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
