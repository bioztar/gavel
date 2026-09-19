"""Per-speaker PCM → utterance chunks ready for STT.

Each speaker's decoded audio accumulates until they go quiet for `gap_ms`
(the utterance ends, `final=True`) or the buffer reaches `max_ms` (a monologue:
cut a chunk, keep the same utterance, `seq` increments). Pure: every method
takes `now` and returns the chunks to transcribe.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from .audio import BYTES_PER_MS_48K_STEREO


@dataclass(frozen=True)
class Chunk:
    discord_id: str
    utterance_id: str
    seq: int
    final: bool
    started_at: float
    ended_at: float
    pcm: bytes  # 48 kHz stereo s16le, as Discord decodes it

    @property
    def audio_ms(self) -> int:
        return len(self.pcm) // BYTES_PER_MS_48K_STEREO


@dataclass
class _Speaker:
    utterance_id: str
    seq: int = 0
    buf: bytearray = field(default_factory=bytearray)
    chunk_started_at: float = 0.0
    last_packet_at: float = 0.0


class Segmenter:
    def __init__(self, gap_ms: int, max_ms: int, min_ms: int) -> None:
        self.gap = gap_ms / 1000
        self.max_bytes = max_ms * BYTES_PER_MS_48K_STEREO
        self.min_bytes = min_ms * BYTES_PER_MS_48K_STEREO
        self._speakers: dict[str, _Speaker] = {}

    def push(self, discord_id: str, pcm: bytes, now: float) -> list[Chunk]:
        sp = self._speakers.get(discord_id)
        if sp is None:
            sp = self._speakers[discord_id] = _Speaker(utterance_id=str(uuid.uuid4()))
        if not sp.buf:
            sp.chunk_started_at = now
        sp.buf += pcm
        sp.last_packet_at = now
        if len(sp.buf) >= self.max_bytes:
            return self._cut(discord_id, sp, final=False)
        return []

    def tick(self, now: float) -> list[Chunk]:
        out: list[Chunk] = []
        for discord_id, sp in list(self._speakers.items()):
            if now - sp.last_packet_at >= self.gap:
                out.extend(self._cut(discord_id, sp, final=True))
                del self._speakers[discord_id]
        return out

    def flush_all(self) -> list[Chunk]:
        out: list[Chunk] = []
        for discord_id, sp in self._speakers.items():
            out.extend(self._cut(discord_id, sp, final=True))
        self._speakers.clear()
        return out

    def _cut(self, discord_id: str, sp: _Speaker, *, final: bool) -> list[Chunk]:
        pcm, sp.buf = bytes(sp.buf), bytearray()
        if len(pcm) < self.min_bytes:
            return []
        chunk = Chunk(
            discord_id=discord_id,
            utterance_id=sp.utterance_id,
            seq=sp.seq,
            final=final,
            started_at=sp.chunk_started_at,
            ended_at=sp.last_packet_at,
            pcm=pcm,
        )
        sp.seq += 1
        return [chunk]
