import time

from ears.pcm_stream import FRAME, PcmStream


def test_mono_is_duplicated_into_both_channels() -> None:
    s = PcmStream(channels=1)
    s.feed(b"\x01\x02" * (FRAME // 4))
    s.end()
    assert s.read() == b"\x01\x02\x01\x02" * (FRAME // 4)
    assert s.read() == b""


def test_late_audio_is_bridged_with_silence_and_the_tail_is_padded() -> None:
    s = PcmStream(channels=2)
    assert s.read() == bytes(FRAME) and s.underruns == 1
    s.feed(b"\x05" * 100)
    s.end()
    assert s.read() == b"\x05" * 100 + bytes(FRAME - 100)
    assert s.read() == b""


def test_a_stalled_stream_ends_itself() -> None:
    s = PcmStream(channels=2, stall_seconds=0.01)
    time.sleep(0.02)
    assert s.read() == b""
