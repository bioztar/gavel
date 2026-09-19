"""Send speech through the same path a Discord chunk takes and print the transcript.

    just stt-check                       # synthesizes a sentence with macOS `say`
    just stt-check path/to/audio.wav     # any 16-bit WAV

Checks the SLNG key, the route and the round-trip latency in one go.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import httpx

from ears.audio import to_mono_16k
from ears.settings import get_settings
from ears.stt import SlngStt

SENTENCE = "Vitaly, you have had eight of the last ten minutes. Ana, you had a point on this."


def load_pcm(path: Path) -> bytes:
    """Return 16 kHz mono PCM, converting from 48 kHz stereo (Discord's format) if needed."""
    with wave.open(str(path)) as w:
        rate, channels, pcm = w.getframerate(), w.getnchannels(), w.readframes(w.getnframes())
    if (rate, channels) == (48_000, 2):
        return to_mono_16k(pcm)
    if (rate, channels) == (16_000, 1):
        return pcm
    sys.exit(f"{path}: {rate} Hz x{channels} — pass 48k stereo or 16k mono")


def synthesize() -> Path:
    out = Path(tempfile.mkdtemp()) / "say.wav"
    # 48k stereo so the check also exercises the Discord downmix path.
    subprocess.run(
        ["say", "-o", str(out), "--data-format=LEI16@48000", "--channels=2", SENTENCE],
        check=True,
    )
    return out


async def main() -> None:
    settings = get_settings()
    if not settings.stt_enabled:
        sys.exit("SLNG_API_KEY is not set")
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else synthesize()
    pcm = load_pcm(path)
    print(f"{path}  {len(pcm) / 32_000:.1f}s  → {settings.slng_base_url} {settings.slng_stt_model}")
    async with httpx.AsyncClient() as client:
        stt = SlngStt(settings, client)
        for _ in range(2):  # the second run shows warm-connection latency
            result = await stt.transcribe(pcm)
            print(f"{result.latency_ms:>5} ms  conf={result.confidence}  {result.text!r}")


if __name__ == "__main__":
    asyncio.run(main())
