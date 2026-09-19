"""Streaming STT: provider parsing, per-speaker segments, the stream clock, and a full
round trip against a local fake of SLNG's WebSocket."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import websockets

from ears.settings import Settings
from ears.stt_stream import NovaProvider, Segment, SonioxProvider, StreamingStt, Word, _Stream


def nova_result(
    words: list[tuple[str, float, float, int]], *, final: bool, speech_final: bool
) -> dict[str, Any]:
    return {
        "type": "Results",
        "is_final": final,
        "speech_final": speech_final,
        "channel": {
            "alternatives": [
                {
                    "transcript": " ".join(w for w, *_ in words),
                    "words": [
                        {
                            "word": w.lower(),
                            "punctuated_word": w,
                            "start": s,
                            "end": e,
                            "speaker": spk,
                            "confidence": 0.9,
                        }
                        for w, s, e, spk in words
                    ],
                }
            ]
        },
    }


def test_nova_parse_partial_final_and_endpoint() -> None:
    p = NovaProvider("en")
    assert (
        p.parse(nova_result([("Hi", 0, 0.3, 0)], final=False, speech_final=False)).partial == "Hi"
    )
    parsed = p.parse(
        nova_result([("Hi", 0, 0.3, 0), ("there.", 0.3, 0.6, 1)], final=True, speech_final=True)
    )
    assert [w.text for w in parsed.finals] == ["Hi", "there."]
    assert [w.speaker for w in parsed.finals] == ["0", "1"] and parsed.endpoint
    assert p.parse({"type": "error", "message": "bad"}).error == "bad"
    init = p.init(keyterms=["Ana"], context="")
    assert (
        init["type"] == "init"
        and init["config"]["diarize"]
        and init["config"]["keyterm"] == ["Ana"]
    )


def test_soniox_parse_tokens_and_init_has_no_type() -> None:
    p = SonioxProvider("en")
    init = p.init(keyterms=["Ana"], context="launch sync")
    assert "type" not in init  # SLNG rejects the documented "type": "config"
    assert init["context"] == {"terms": ["Ana"], "text": "launch sync"}
    parsed = p.parse(
        {
            "tokens": [
                {"text": "Hel", "start_ms": 0, "end_ms": 100, "is_final": True, "speaker": "1"},
                {"text": "lo", "start_ms": 100, "end_ms": 200, "is_final": True, "speaker": "1"},
                {"text": " wor", "is_final": False},
                {"text": "<end>", "is_final": True},
            ]
        }
    )
    assert "".join(w.text for w in parsed.finals) == "Hello"
    assert parsed.partial == "wor" and parsed.endpoint


def make_stt(segments: list[Segment], base: str = "https://x") -> StreamingStt:
    settings = Settings(_env_file=None, slng_api_key="k", slng_base_url=base)  # type: ignore[call-arg]
    return StreamingStt(
        settings,
        NovaProvider("en"),
        on_segments=lambda _id, segs: segments.extend(segs),
        debug=lambda *_a, **_k: None,
        keyterms=lambda: ["Ana"],
        context=lambda: "",
    )


def test_segments_split_by_speaker_and_mapped_to_wall_clock() -> None:
    out: list[Segment] = []
    stream = _Stream(make_stt(out), "42")
    stream.timeline = [(0.0, 1000.0), (5.0, 2000.0)]  # a second burst began 995 s later
    stream.pending = [
        Word("Hi", 5.0, 5.3, "0", 0.8),
        Word("Ana.", 5.3, 5.6, "0", 1.0),
        Word("Yes?", 6.0, 6.4, "1", 0.9),
    ]
    stream.flush_pending(utterance_end=True)
    assert [(s.text, s.speaker, s.utterance_end) for s in out] == [
        ("Hi Ana.", "0", False),
        ("Yes?", "1", True),
    ]
    assert out[0].started_at == 2000.0 and abs(out[1].ended_at - 2001.4) < 1e-9
    assert abs((out[0].confidence or 0) - 0.9) < 1e-9


async def test_round_trip_against_fake_slng() -> None:
    """Audio in, silence flush after the pause, final segment out."""
    received: list[Any] = []

    async def fake_slng(ws: Any) -> None:
        init = json.loads(await ws.recv())
        received.append(init)
        audio = 0
        async for msg in ws:
            if isinstance(msg, bytes):
                audio += len(msg)
                if msg.count(0) == len(msg) and audio > 32_000:  # the silence flush arrived
                    await ws.send(
                        json.dumps(
                            nova_result([("Hello", 0.0, 0.5, 0)], final=True, speech_final=True)
                        )
                    )

    async with websockets.serve(fake_slng, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        out: list[Segment] = []
        stt = make_stt(out, base=f"http://127.0.0.1:{port}")
        loud = (b"\x00\x10" * 2) * 960  # 20 ms of 48 kHz stereo
        for i in range(60):  # 1.2 s of speech
            stt.feed("42", loud, 1000.0 + i * 0.02)
            await asyncio.sleep(0)
        for _ in range(50):
            stt.tick(1000.0 + 1.2 + 1.0)  # a second of quiet → flush
            await asyncio.sleep(0.02)
            if out:
                break
        await stt.close()

    assert received[0]["config"]["keyterm"] == ["Ana"]
    assert [s.text for s in out] == ["Hello"] and out[0].utterance_end
    assert out[0].started_at == 1000.0
