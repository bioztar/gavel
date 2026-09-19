"""A line the brain is still synthesizing, played as it arrives.

`speak.start` opens one of these, `speak.chunk` feeds it raw PCM, `speak.end` closes it.
Discord's player thread pulls 20 ms frames from `read()` the whole time: while the next
chunk is late it gets silence and keeps playing; once the line is closed and drained it
gets `b""`, which ends playback exactly like a finished file.
"""

from __future__ import annotations

import threading
import time

import discord

RATE = 48_000  # Discord's only rate
FRAME = 3_840  # 20 ms of 48 kHz stereo s16le — what py-cord expects from read()


class PcmStream(discord.AudioSource):
    def __init__(self, channels: int = 1, stall_seconds: float = 10.0) -> None:
        if channels not in (1, 2):
            raise ValueError("channels must be 1 or 2")
        self._channels = channels
        self._buf = bytearray()
        self._lock = threading.Lock()
        self._ended = False
        self._stall = stall_seconds
        self._last_feed = time.monotonic()
        self.fed_bytes = 0
        self.underruns = 0

    def feed(self, pcm: bytes) -> None:
        """Append 48 kHz s16le PCM in the stream's channel count."""
        if self._channels == 1:
            pcm = _mono_to_stereo(pcm)
        with self._lock:
            if self._ended:
                return
            self._buf += pcm
            self._last_feed = time.monotonic()
            self.fed_bytes += len(pcm)

    def end(self) -> None:
        with self._lock:
            self._ended = True

    @property
    def ended(self) -> bool:
        return self._ended

    def read(self) -> bytes:
        with self._lock:
            if len(self._buf) >= FRAME:
                frame = bytes(self._buf[:FRAME])
                del self._buf[:FRAME]
                return frame
            if self._ended or time.monotonic() - self._last_feed > self._stall:
                # The tail, padded to a whole frame; then nothing, which ends playback.
                if not self._buf:
                    return b""
                frame = bytes(self._buf) + bytes(FRAME - len(self._buf))
                self._buf.clear()
                return frame
            self.underruns += 1
            return bytes(FRAME)

    def is_opus(self) -> bool:
        return False


def _mono_to_stereo(pcm: bytes) -> bytes:
    if len(pcm) % 2:
        pcm = pcm[:-1]
    out = bytearray(len(pcm) * 2)
    out[0::4] = pcm[0::2]
    out[1::4] = pcm[1::2]
    out[2::4] = pcm[0::2]
    out[3::4] = pcm[1::2]
    return bytes(out)
