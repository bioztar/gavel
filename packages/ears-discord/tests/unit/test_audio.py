from __future__ import annotations

import io
import wave

import numpy as np

from ears.audio import rms, to_mono_16k, wav_bytes


def test_downmix_and_decimate() -> None:
    # 48 kHz stereo: left 300, right 100 → mono 200, one third the samples.
    stereo = np.tile(np.array([300, 100], dtype="<i2"), 4800).tobytes()
    mono = np.frombuffer(to_mono_16k(stereo), dtype="<i2")
    assert len(mono) == 1600
    assert set(mono.tolist()) == {200}


def test_rms_of_silence_is_zero() -> None:
    assert rms(b"\x00\x00" * 100) == 0.0
    assert rms(b"") == 0.0


def test_wav_header() -> None:
    with wave.open(io.BytesIO(wav_bytes(b"\x00\x00" * 16_000))) as w:
        assert (w.getframerate(), w.getnchannels(), w.getnframes()) == (16_000, 1, 16_000)
