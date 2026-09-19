"""Check SLNG speech-to-text through the same path Discord audio takes.

    just stt-check                  # HTTP: one synthesized sentence, twice (cold, warm)
    just stt-check --stream         # streaming: two voices on one "mic", real time,
                                    # via StreamingStt exactly as the app drives it
    just stt-check path/to/a.wav    # HTTP on your own 16-bit WAV (48k stereo or 16k mono)

Checks the SLNG key, the route, latency, and (with --stream) diarization.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

import httpx

from ears.audio import to_mono_16k
from ears.settings import get_settings
from ears.stt import SlngStt
from ears.stt_stream import Segment, StreamingStt, make_provider

SENTENCE = "Vitaly, you have had eight of the last ten minutes. Ana, you had a point on this."
ROOM = [
    ("Samantha", "Okay, let's start. Where are we on the payments integration?"),
    ("Daniel", "Still blocked on their side. QA needs two more weeks, not one."),
    ("Samantha", "Then the fifteenth is not realistic. Vitaly, can you own that blocker?"),
]


def say(text: str, voice: str | None = None) -> bytes:
    """48 kHz stereo s16le — Discord's decoded format."""
    out = Path(tempfile.mkdtemp()) / "say.wav"
    cmd = ["say", "-o", str(out), "--data-format=LEI16@48000", "--channels=2", text]
    if voice:
        cmd[1:1] = ["-v", voice]
    subprocess.run(cmd, check=True)
    with wave.open(str(out)) as w:
        return w.readframes(w.getnframes())


def load_pcm(path: Path) -> bytes:
    with wave.open(str(path)) as w:
        rate, channels, pcm = w.getframerate(), w.getnchannels(), w.readframes(w.getnframes())
    if (rate, channels) == (48_000, 2):
        return to_mono_16k(pcm)
    if (rate, channels) == (16_000, 1):
        return pcm
    sys.exit(f"{path}: {rate} Hz x{channels} — pass 48k stereo or 16k mono")


async def check_http(path: Path | None) -> None:
    settings = get_settings()
    pcm = load_pcm(path) if path else to_mono_16k(say(SENTENCE))
    print(f"HTTP {len(pcm) / 32_000:.1f}s → {settings.slng_base_url} {settings.slng_stt_model}")
    async with httpx.AsyncClient() as client:
        stt = SlngStt(settings, client)
        for _ in range(2):  # the second run shows warm-connection latency
            result = await stt.transcribe(pcm, keyterms=["Vitaly", "Ana"])
            print(f"{result.latency_ms:>5} ms  conf={result.confidence}  {result.text!r}")


async def check_stream() -> None:
    settings = get_settings()
    # Two people sharing one account: one Discord user, one audio stream.
    clips = [say(text, voice) for voice, text in ROOM]
    print(
        f"stream → {settings.slng_base_url} {settings.slng_stt_model} · {len(clips)} lines, 2 voices, 1 account\n"
    )
    segments: list[Segment] = []
    started = time.time()

    def on_segments(_discord_id: str, segs: list[Segment]) -> None:
        for s in segs:
            segments.append(s)
            print(
                f"  +{s.ended_at - started:5.1f}s  voice {s.speaker}  (final {int((time.time() - s.ended_at) * 1000)}ms after words)  {s.text}"
            )

    def debug(kind: str, **data: object) -> None:
        if kind in ("stt.stream.open", "stt.stream.error"):
            print(f"  [{kind}] {data}")

    stt = StreamingStt(
        settings,
        make_provider(settings),
        on_segments=on_segments,
        debug=debug,
        keyterms=lambda: ["Vitaly", "Ana"],
        context=lambda: "Launch sync: payments integration, QA, launch date, blockers.",
    )
    frame = 3840  # 20 ms of 48 kHz stereo, like one Discord packet
    for clip in clips:
        t0 = time.time()
        for i in range(0, len(clip) - frame + 1, frame):
            stt.feed("room", clip[i : i + frame], time.time())
            stt.tick(time.time())
            await asyncio.sleep(max(0.0, t0 + (i // frame + 1) * 0.02 - time.time()))
        # a real pause: Discord sends nothing, the clock keeps ticking
        pause_end = time.time() + 1.5
        while time.time() < pause_end:
            stt.tick(time.time())
            await asyncio.sleep(0.1)
    await asyncio.sleep(1.5)
    await stt.close()
    voices = sorted({s.speaker for s in segments if s.speaker is not None})
    print(f"\n{len(segments)} segments, voices {voices}")


if __name__ == "__main__":
    if "--stream" in sys.argv:
        asyncio.run(check_stream())
    else:
        args = [a for a in sys.argv[1:] if not a.startswith("-")]
        asyncio.run(check_http(Path(args[0]) if args else None))
