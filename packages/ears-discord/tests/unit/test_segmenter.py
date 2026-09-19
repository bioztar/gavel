from __future__ import annotations

from ears.audio import BYTES_PER_MS_48K_STEREO
from ears.segmenter import Segmenter

FRAME = b"\x01\x00" * 2 * 960  # 20 ms of 48 kHz stereo


def seg() -> Segmenter:
    return Segmenter(gap_ms=800, max_ms=1000, min_ms=100)


def test_gap_closes_utterance_as_final() -> None:
    s = seg()
    for i in range(10):  # 200 ms
        assert s.push("a", FRAME, i * 0.02) == []
    assert s.tick(0.5) == []
    [chunk] = s.tick(0.18 + 0.8)
    assert chunk.final and chunk.seq == 0 and chunk.audio_ms == 200


def test_monologue_is_chunked_within_one_utterance() -> None:
    s = seg()
    chunks = []
    for i in range(120):  # 2.4 s, max 1 s per chunk
        chunks += s.push("a", FRAME, i * 0.02)
    chunks += s.tick(2.4 + 1.0)
    assert [c.seq for c in chunks] == [0, 1, 2]
    assert [c.final for c in chunks] == [False, False, True]
    assert len({c.utterance_id for c in chunks}) == 1
    assert sum(len(c.pcm) for c in chunks) == 120 * len(FRAME)


def test_tiny_blips_are_dropped() -> None:
    s = seg()
    s.push("a", FRAME, 0.0)  # 20 ms < min 100 ms
    assert s.tick(1.0) == []


def test_speakers_are_independent() -> None:
    s = seg()
    for i in range(10):
        s.push("a", FRAME, i * 0.02)
        s.push("b", FRAME, i * 0.02)
    out = s.tick(2.0)
    assert {c.discord_id for c in out} == {"a", "b"}
    assert out[0].utterance_id != out[1].utterance_id
    assert BYTES_PER_MS_48K_STEREO == 192
