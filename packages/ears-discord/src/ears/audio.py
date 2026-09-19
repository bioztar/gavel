"""PCM helpers. Discord decodes to 48 kHz stereo s16le; STT wants 16 kHz mono."""

from __future__ import annotations

import io
import wave

import numpy as np

BYTES_PER_MS_48K_STEREO = 48 * 2 * 2


def to_mono_16k(pcm_48k_stereo: bytes) -> bytes:
    """Downmix and decimate 48k → 16k by averaging each 3 samples.

    The averaging is a crude low-pass, which is plenty for speech recognition.
    """
    samples = np.frombuffer(pcm_48k_stereo, dtype="<i2")
    samples = samples[: len(samples) - len(samples) % 6]  # whole stereo frames, multiple of 3
    mono = samples.reshape(-1, 2).astype(np.float32).mean(axis=1)
    decimated = mono.reshape(-1, 3).mean(axis=1)
    return np.clip(np.round(decimated), -32768, 32767).astype("<i2").tobytes()


def rms(pcm_mono: bytes) -> float:
    samples = np.frombuffer(pcm_mono, dtype="<i2").astype(np.float32)
    return float(np.sqrt(np.mean(samples**2))) if samples.size else 0.0


def wav_bytes(pcm: bytes, *, rate: int = 16_000, channels: int = 1) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()
