"""PulseAudio: the two null sinks that are the bot's speaker and microphone.

    Meet (Chromium) ──plays──▶ sink `gavel_out` ──monitor──▶ parec ──▶ STT      (ingress)
    brain `speak`  ──pacat──▶ sink `gavel_in`  ──monitor──▶ Chromium's mic ─▶ Meet (egress)

Chromium is pointed at them by making `gavel_out` the default sink and `gavel_in.monitor`
the default source before it launches — Chromium follows PulseAudio's defaults and Meet
picks "Default" for both devices. `egress_attached()` reads back from `pactl` whether
Chromium actually opened a recording stream on that monitor: it is the one check that
does not depend on Meet's DOM, and self_check runs it.

Everything here shells out to `pactl` / `parec` / `pacat` (pulseaudio-utils) and `ffmpeg`
for decoding; no Python audio stack, so the container stays the size of ears-discord's.
"""

from __future__ import annotations

import asyncio
import contextlib
import shutil
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from .logging import get_logger

logger = get_logger("ears_meet.pulse")

RATE = 48_000
CHANNELS = 2
BYTES_PER_MS = RATE * CHANNELS * 2 // 1000  # s16le

PcmSink = Callable[[bytes, float], None]  # (pcm 48k stereo, epoch seconds)


class PulseError(RuntimeError):
    pass


async def _run(*argv: str, check: bool = True) -> str:
    proc = await asyncio.create_subprocess_exec(
        *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, err = await proc.communicate()
    if check and proc.returncode != 0:
        raise PulseError(f"{argv[0]} {argv[1] if len(argv) > 1 else ''}: {err.decode().strip()}")
    return out.decode()


def tools_missing() -> list[str]:
    return [t for t in ("pactl", "parec", "pacat", "ffmpeg") if shutil.which(t) is None]


@dataclass
class Pulse:
    sink_out: str
    sink_in: str
    manage: bool = True
    _modules: list[str] = field(default_factory=list)

    @property
    def monitor_out(self) -> str:
        return f"{self.sink_out}.monitor"

    @property
    def monitor_in(self) -> str:
        return f"{self.sink_in}.monitor"

    async def setup(self) -> None:
        """Start a server if none answers, create both sinks, make them the defaults."""
        missing = tools_missing()
        if missing:
            raise PulseError(
                f"missing tools: {', '.join(missing)} (install pulseaudio-utils, ffmpeg)"
            )
        if not await self._server_up():
            if not self.manage:
                raise PulseError("no PulseAudio server and PULSE_MANAGE=false")
            if shutil.which("pulseaudio") is None:
                raise PulseError("no PulseAudio server running and no `pulseaudio` binary to start")
            await _run(
                "pulseaudio", "--start", "--exit-idle-time=-1", "--log-target=stderr", check=False
            )
            for _ in range(20):
                if await self._server_up():
                    break
                await asyncio.sleep(0.25)
            else:
                raise PulseError("pulseaudio did not come up")
        if self.manage:
            for name, desc in ((self.sink_out, "gavel_meet_out"), (self.sink_in, "gavel_meet_in")):
                if name not in await self.sinks():
                    mid = await _run(
                        "pactl",
                        "load-module",
                        "module-null-sink",
                        f"sink_name={name}",
                        f"sink_properties=device.description={desc}",
                        f"rate={RATE}",
                        f"channels={CHANNELS}",
                    )
                    self._modules.append(mid.strip())
            await _run("pactl", "set-default-sink", self.sink_out)
            await _run("pactl", "set-default-source", self.monitor_in)
        sinks = await self.sinks()
        for name in (self.sink_out, self.sink_in):
            if name not in sinks:
                raise PulseError(f"sink {name} does not exist")
        logger.info("pulse.ready", sink_out=self.sink_out, sink_in=self.sink_in)

    async def teardown(self) -> None:
        for mid in reversed(self._modules):
            with contextlib.suppress(PulseError):
                await _run("pactl", "unload-module", mid)
        self._modules.clear()

    async def _server_up(self) -> bool:
        try:
            await _run("pactl", "info")
        except PulseError:
            return False
        return True

    async def sinks(self) -> list[str]:
        out = await _run("pactl", "list", "short", "sinks", check=False)
        return [line.split("\t")[1] for line in out.splitlines() if "\t" in line]

    async def egress_attached(self) -> bool:
        """Is some client (Chromium) recording from `gavel_in.monitor`? The egress proof
        that needs no DOM: if this is false, nothing we play can reach the call."""
        out = await _run("pactl", "list", "source-outputs", check=False)
        return _source_outputs_on(out, self.monitor_in) > 0

    async def ingress_attached(self) -> bool:
        """Is Chromium playing into `gavel_out`? False until Meet has connected media."""
        out = await _run("pactl", "list", "sink-inputs", check=False)
        return _sink_inputs_on(out, self.sink_out) > 0

    # --- ingress ---------------------------------------------------------------------------

    def record(self, on_pcm: PcmSink, frame_ms: int = 20) -> Recorder:
        return Recorder(self.monitor_out, on_pcm, frame_ms)

    # --- egress ----------------------------------------------------------------------------

    def player(self) -> PulsePlayer:
        return PulsePlayer(self.sink_in)


def _pacat_stdin(pacat: asyncio.subprocess.Process) -> asyncio.StreamWriter:
    """pacat's stdin, or a clear failure naming it.

    Deliberately not `assert`: `python -O` strips assert statements, and the next line would
    then raise `AttributeError: 'NoneType' object has no attribute 'write'` several frames
    away from the cause. This raises the same way whether or not optimisations are on.
    """
    if pacat.stdin is None:
        raise PulseError("pacat started without a stdin to write the chair's audio into")
    return pacat.stdin


def _source_outputs_on(pactl_text: str, source_name: str) -> int:
    """Count `pactl list source-outputs` entries whose Source is `source_name`.

    `pactl` prints the source by index and, in newer versions, by name in the properties;
    we match either a `Source: <name>` line or the monitor's name anywhere in the block."""
    count = 0
    for block in pactl_text.split("Source Output #")[1:]:
        if source_name in block and ("Source:" in block or "source" in block.lower()):
            count += 1
    return count


def _sink_inputs_on(pactl_text: str, sink_name: str) -> int:
    count = 0
    for block in pactl_text.split("Sink Input #")[1:]:
        if sink_name in block:
            count += 1
    return count


class Recorder:
    """`parec` on a monitor source, chunked into `frame_ms` frames of 48 kHz stereo s16le."""

    def __init__(self, source: str, on_pcm: PcmSink, frame_ms: int) -> None:
        self.source = source
        self.on_pcm = on_pcm
        self.frame_bytes = frame_ms * BYTES_PER_MS
        self._proc: asyncio.subprocess.Process | None = None
        self._task: asyncio.Task[None] | None = None
        self.frames = 0

    async def start(self) -> None:
        self._proc = await asyncio.create_subprocess_exec(
            "parec",
            f"--device={self.source}",
            "--format=s16le",
            f"--rate={RATE}",
            f"--channels={CHANNELS}",
            "--raw",
            f"--latency-msec={max(10, self.frame_bytes // BYTES_PER_MS)}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        self._task = asyncio.get_running_loop().create_task(self._pump())
        logger.info("pulse.recording", source=self.source)

    async def _pump(self) -> None:
        # Not `assert`: `python -O` strips those, and a missing pipe would then surface as an
        # AttributeError on None instead of naming what did not start.
        if self._proc is None or self._proc.stdout is None:
            raise PulseError("parec was not started (no stdout to read the room from)")
        stdout = self._proc.stdout
        while True:
            try:
                frame = await stdout.readexactly(self.frame_bytes)
            except asyncio.IncompleteReadError:
                break
            self.frames += 1
            self.on_pcm(frame, time.time())
        logger.warning("pulse.recording_ended", source=self.source, frames=self.frames)

    async def stop(self) -> None:
        if self._proc is not None and self._proc.returncode is None:
            self._proc.terminate()
            with contextlib.suppress(ProcessLookupError, asyncio.TimeoutError):
                await asyncio.wait_for(self._proc.wait(), 2)
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task


class PcmSource:
    """A line still arriving over `speak.chunk` frames (or already complete).

    `read(n)` returns up to `n` bytes of 48 kHz stereo s16le; `b""` means the line has
    ended and drained. While the producer is behind, `read` returns silence so the sink
    keeps real-time (an underrun is padded, not skipped) — same as ears-discord's
    PcmStream, without py-cord.
    """

    def __init__(self, channels: int = 1) -> None:
        self.channels = channels
        self._buf = bytearray()
        self._ended = False
        self.fed_bytes = 0
        self.underruns = 0

    def feed(self, pcm: bytes) -> None:
        if self.channels == 1:
            pcm = mono_to_stereo(pcm)
        self._buf += pcm
        self.fed_bytes += len(pcm)

    def end(self) -> None:
        self._ended = True

    @property
    def ended(self) -> bool:
        return self._ended

    def read(self, n: int) -> bytes:
        if len(self._buf) >= n:
            out = bytes(self._buf[:n])
            del self._buf[:n]
            return out
        if self._ended:
            out = bytes(self._buf)
            self._buf.clear()
            return out
        if self._buf:
            out = bytes(self._buf)
            self._buf.clear()
            return out + b"\x00" * (n - len(out))
        self.underruns += 1
        return b"\x00" * n


def mono_to_stereo(pcm: bytes) -> bytes:
    if len(pcm) % 2:
        pcm = pcm[:-1]
    out = bytearray(len(pcm) * 2)
    out[0::4] = pcm[0::2]
    out[1::4] = pcm[1::2]
    out[2::4] = pcm[0::2]
    out[3::4] = pcm[1::2]
    return bytes(out)


Done = Callable[[Exception | None], None]


class PulsePlayer:
    """Plays one thing at a time into `gavel_in`: a finished clip (anything FFmpeg reads)
    or a PcmSource still being fed. `stop()` cuts the current one; `done(error)` runs
    on the loop when playback ends, however it ends."""

    def __init__(self, sink: str) -> None:
        self.sink = sink
        self._pacat: asyncio.subprocess.Process | None = None
        self._ffmpeg: asyncio.subprocess.Process | None = None
        self._task: asyncio.Task[None] | None = None
        self._stopped = False

    @property
    def playing(self) -> bool:
        return self._task is not None and not self._task.done()

    def play(self, audio: bytes, done: Done) -> bool:
        return self._start(self._play_clip(audio), done)

    def play_source(self, source: PcmSource, done: Done) -> bool:
        return self._start(self._play_source(source), done)

    def _start(self, coro: Awaitable[None], done: Done) -> bool:
        if self.playing:
            return False
        self._stopped = False

        async def run() -> None:
            error: Exception | None = None
            try:
                await coro
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — reported to the caller as `spoken.error`
                error = exc
            finally:
                await self._kill()
            done(error)

        self._task = asyncio.get_running_loop().create_task(run())
        return True

    def stop(self) -> None:
        self._stopped = True
        for proc in (self._ffmpeg, self._pacat):
            if proc is not None and proc.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()

    async def _open_pacat(self) -> asyncio.subprocess.Process:
        self._pacat = await asyncio.create_subprocess_exec(
            "pacat",
            f"--device={self.sink}",
            "--format=s16le",
            f"--rate={RATE}",
            f"--channels={CHANNELS}",
            "--raw",
            "--latency-msec=40",
            stdin=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        return self._pacat

    async def _play_clip(self, audio: bytes) -> None:
        # Decode with ffmpeg to raw PCM and pipe that into pacat. Two processes, one write.
        self._ffmpeg = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-nostdin",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-f",
            "s16le",
            "-ar",
            str(RATE),
            "-ac",
            str(CHANNELS),
            "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        ffmpeg = self._ffmpeg
        if ffmpeg.stdin is None or ffmpeg.stdout is None:
            raise PulseError("ffmpeg started without the pipes needed to decode the clip")
        ffmpeg_in, ffmpeg_out = ffmpeg.stdin, ffmpeg.stdout

        async def feed() -> None:
            with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                ffmpeg_in.write(audio)
                await ffmpeg_in.drain()
                ffmpeg_in.close()

        feeder = asyncio.get_running_loop().create_task(feed())
        pacat = await self._open_pacat()
        pacat_in = _pacat_stdin(pacat)
        total = 0
        try:
            while True:
                chunk = await ffmpeg_out.read(BYTES_PER_MS * 100)
                if not chunk:
                    break
                total += len(chunk)
                pacat_in.write(chunk)
                await pacat_in.drain()
        except (BrokenPipeError, ConnectionResetError) as exc:
            if not self._stopped:
                raise PulseError("pacat closed the pipe") from exc
        finally:
            await feeder
        if self._stopped:
            return
        _, err = await ffmpeg.communicate()
        if ffmpeg.returncode not in (0, None) and total == 0:
            raise PulseError(f"ffmpeg could not decode the clip: {err.decode().strip()[:200]}")
        await self._drain_pacat(pacat)

    async def _play_source(self, source: PcmSource) -> None:
        pacat = await self._open_pacat()
        pacat_in = _pacat_stdin(pacat)
        frame = 20 * BYTES_PER_MS
        started = time.monotonic()
        sent = 0
        try:
            while not self._stopped:
                chunk = source.read(frame)
                if not chunk:
                    break
                pacat_in.write(chunk)
                await pacat_in.drain()
                sent += len(chunk)
                # Pace at real time so an underrun is padded with silence, not a stall.
                due = started + sent / (BYTES_PER_MS * 1000)
                delay = due - time.monotonic()
                if delay > 0:
                    await asyncio.sleep(delay)
        except (BrokenPipeError, ConnectionResetError) as exc:
            if not self._stopped:
                raise PulseError("pacat closed the pipe") from exc
        if not self._stopped:
            await self._drain_pacat(pacat)

    async def _drain_pacat(self, pacat: asyncio.subprocess.Process) -> None:
        stdin = _pacat_stdin(pacat)
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            stdin.close()
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(pacat.wait(), 5)

    async def _kill(self) -> None:
        for proc in (self._ffmpeg, self._pacat):
            if proc is not None and proc.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(proc.wait(), 2)
        self._ffmpeg = self._pacat = None


class FakePlayer:
    """For tests and for `--no-audio` runs: 'plays' by scheduling `done` after the clip's
    nominal duration (or immediately)."""

    def __init__(self, duration_s: float = 0.0) -> None:
        self.duration_s = duration_s
        self.played: list[bytes] = []
        self.stopped = 0
        self._handle: asyncio.TimerHandle | None = None
        self._done: Done | None = None

    @property
    def playing(self) -> bool:
        return self._done is not None

    def play(self, audio: bytes, done: Done) -> bool:
        if self.playing:
            return False
        self.played.append(audio)
        self._done = done
        self._handle = asyncio.get_running_loop().call_later(self.duration_s, self._finish, None)
        return True

    def play_source(self, source: PcmSource, done: Done) -> bool:
        return self.play(b"<stream>", done)

    def stop(self) -> None:
        self.stopped += 1
        if self._handle is not None:
            self._handle.cancel()
        self._finish(None)

    def _finish(self, error: Exception | None) -> None:
        done, self._done, self._handle = self._done, None, None
        if done is not None:
            done(error)


Player = PulsePlayer | FakePlayer
Snapshot = dict[str, Any]
