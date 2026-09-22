"""Streaming speech-to-text: one SLNG WebSocket per audio source.

Kept in step with ears-discord/src/ears/stt_stream.py. On Meet there is one source, the
mixed room (`MIX_ID`): Meet hands us one already-mixed track, so diarization labels here
are the model's guess and speaker identity comes from the DOM (attribution.py). The
"Discord" below is where the code came from; read "source" for "user".

Why streaming over the HTTP chunk path: the model keeps context across a whole
turn instead of seeing 1-2 s clips, finals land within ~0.3 s of a pause, and
diarization labels stay stable within the stream — which is what separates
several people sharing one account (a meeting room on one mic).

Discord sends no packets while someone is silent, so the model never *hears*
the pause it needs to finalize. When a speaker's audio stops for `flush_ms`,
we send `flush_silence_ms` of zeros; endpointing does the rest. Between
utterances the socket idles on keepalives and closes after `idle_close_s`.

Stream time only advances with audio we send, not wall time, so each stream
keeps a timeline of (stream offset → wall clock) anchors, one per burst.

Providers (bake-off on a two-voice clip, Barcelona → eu-west): Deepgram Nova 3
0% WER and 2/2 speakers; Soniox v5 same speakers, numerals as digits.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import websockets

from .audio import to_mono_16k
from .logging import get_logger
from .settings import Settings

logger = get_logger(__name__)

RATE = 16_000
BYTES_PER_MS = RATE * 2 // 1000  # 16 kHz mono s16le
FRAME = 20 * BYTES_PER_MS
# SLNG closes a socket past 2000 messages a minute; one per 20 ms frame is 3000. Audio goes
# out in 60 ms batches (1000 a minute), which costs at most 60 ms of latency.
BATCH = 60 * BYTES_PER_MS
BUFFER_LIMIT = 10_000 * BYTES_PER_MS  # audio held while the socket connects (10 s)


@dataclass(frozen=True)
class Word:
    text: str
    start: float  # seconds of stream audio
    end: float
    speaker: str | None
    confidence: float | None
    # Soniox tokens carry their own leading space; Deepgram words need one.
    joined: bool = False


@dataclass
class Parsed:
    finals: list[Word] = field(default_factory=list)
    partial: str = ""
    endpoint: bool = False
    error: str | None = None


class Provider(Protocol):
    path: str
    # SLNG passes each provider's own spelling through (probed): anything else closes the socket.
    keepalive: str

    def init(self, *, keyterms: list[str], context: str) -> dict[str, Any]: ...
    def parse(self, msg: dict[str, Any]) -> Parsed: ...


class NovaProvider:
    """Deepgram Nova 3 via SLNG. `{"type":"init","config":{...}}`; Deepgram `Results` back."""

    path = "/v1/stt/deepgram/nova:3"
    keepalive = json.dumps({"type": "KeepAlive"})  # Deepgram's; SLNG rejects "keepalive"

    def __init__(self, language: str) -> None:
        self.language = language

    def init(self, *, keyterms: list[str], context: str) -> dict[str, Any]:
        config: dict[str, Any] = {
            "language": self.language,
            "sample_rate": RATE,
            "encoding": "linear16",
            "enable_partials": True,
            "punctuate": True,
            "smart_format": True,
            "diarize": True,
            # SLNG's default is 10 ms, which finalizes at every breath and chops sentences.
            "endpointing": 300,
        }
        if keyterms:
            config["keyterm"] = keyterms
        return {"type": "init", "config": config}

    def parse(self, msg: dict[str, Any]) -> Parsed:
        if msg.get("type") == "error" or msg.get("type") == "Error":
            return Parsed(error=str(msg.get("message") or msg)[:300])
        if msg.get("type") != "Results":
            return Parsed()
        alt = (msg.get("channel", {}).get("alternatives") or [{}])[0]
        if not msg.get("is_final"):
            return Parsed(partial=alt.get("transcript", ""))
        words = [
            Word(
                text=w.get("punctuated_word") or w.get("word", ""),
                start=float(w.get("start", 0)),
                end=float(w.get("end", 0)),
                speaker=str(w["speaker"]) if w.get("speaker") is not None else None,
                confidence=w.get("confidence"),
            )
            for w in alt.get("words", [])
        ]
        return Parsed(finals=words, endpoint=bool(msg.get("speech_final")))


class SonioxProvider:
    """Soniox v5 via SLNG. Native config with NO `type` field (SLNG rejects the documented
    `"type": "config"`); native `tokens` frames back, `<end>` marks an endpoint."""

    path = "/v1/stt/soniox/speech-ai:rt-v5"
    keepalive = json.dumps({"type": "keepalive"})  # Soniox rejects "KeepAlive"

    def __init__(self, language: str) -> None:
        self.language = language

    def init(self, *, keyterms: list[str], context: str) -> dict[str, Any]:
        config: dict[str, Any] = {
            "model": "stt-rt-v5",
            "audio_format": "pcm_s16le",
            "sample_rate": RATE,
            "num_channels": 1,
            "enable_speaker_diarization": True,
            "enable_endpoint_detection": True,
            "language_hints": [self.language],
        }
        ctx: dict[str, Any] = {}
        if keyterms:
            ctx["terms"] = keyterms
        if context:
            ctx["text"] = context[:2000]
        if ctx:
            config["context"] = ctx
        return config

    def parse(self, msg: dict[str, Any]) -> Parsed:
        if msg.get("type") == "error" or "error_code" in msg:
            return Parsed(error=str(msg.get("message") or msg)[:300])
        out = Parsed()
        partial: list[str] = []
        for t in msg.get("tokens", []):
            text = t.get("text", "")
            if text in ("<end>", "<fin>"):
                out.endpoint = True
                continue
            if not t.get("is_final"):
                partial.append(text)
                continue
            out.finals.append(
                Word(
                    text=text,
                    start=t.get("start_ms", 0) / 1000,
                    end=t.get("end_ms", 0) / 1000,
                    speaker=t.get("speaker"),
                    confidence=t.get("confidence"),
                    joined=True,
                )
            )
        out.partial = "".join(partial).strip()
        return out


def make_provider(settings: Settings) -> Provider:
    if "soniox" in settings.slng_stt_model:
        return SonioxProvider(settings.slng_stt_language)
    return NovaProvider(settings.slng_stt_language)


@dataclass(frozen=True)
class Segment:
    """One speaker's stretch of finalized words — becomes one `transcript` frame."""

    discord_id: str
    text: str
    started_at: float  # wall clock
    ended_at: float
    speaker: str | None
    confidence: float | None
    utterance_end: bool


SegmentSink = Callable[[str, list[Segment]], None]  # (discord_id, segments)
DebugSink = Callable[..., None]

# The one stream key on Meet: the room's mixed audio, from the PulseAudio monitor.
MIX_ID = "meet:mix"


class _Stream:
    """One Discord user's socket, its outbound queue and its clock.

    Everything outbound — audio, flush silence, keepalives — goes through one queue
    drained by one sender, so frames reach the model in order, including the audio
    that arrives while the socket is still connecting.
    """

    def __init__(self, owner: StreamingStt, discord_id: str) -> None:
        self.owner = owner
        self.discord_id = discord_id
        self.out: asyncio.Queue[bytes | str] = asyncio.Queue()
        self.open = False
        self.running = False
        self.queued_bytes = 0  # stream clock = audio bytes queued so far
        self.timeline: list[tuple[float, float]] = []  # (stream seconds, wall clock)
        self.last_audio = 0.0
        self.flushed = True  # silence already sent since the last audio
        self.last_keepalive = 0.0
        self.pending: list[Word] = []
        self.batch = bytearray()  # audio not yet queued as a message
        self.task: asyncio.Task[None] | None = None
        self.ws: Any = None
        self.closing = False

    # --- clock ---------------------------------------------------------------------------

    def stream_seconds(self) -> float:
        return self.queued_bytes / BYTES_PER_MS / 1000

    def wall(self, t: float) -> float:
        if not self.timeline:
            return time.time()
        anchor = self.timeline[0]
        for offset, at in self.timeline:
            if offset > t:
                break
            anchor = (offset, at)
        return anchor[1] + (t - anchor[0])

    # --- outbound ------------------------------------------------------------------------

    def feed(self, pcm16: bytes, now: float) -> None:
        if self.flushed:  # a new burst: anchor stream time to the wall clock
            self.timeline.append((self.stream_seconds(), now))
            self.flushed = False
        self.last_audio = now
        if not self.open and self.queued_bytes_waiting() > BUFFER_LIMIT:
            return  # connecting is taking too long; do not grow without bound
        self.push(pcm16)
        if not self.running:
            self.start()

    def queued_bytes_waiting(self) -> int:
        return self.out.qsize() * BATCH + len(self.batch)

    def push(self, data: bytes) -> None:
        self.queued_bytes += len(data)
        self.batch += data
        if len(self.batch) >= BATCH:
            self.send_batch()

    def send_batch(self) -> None:
        if self.batch:
            self.out.put_nowait(bytes(self.batch))
            self.batch.clear()

    def flush_silence(self) -> None:
        """Let the model hear the pause Discord does not send."""
        self.flushed = True
        if self.running:
            self.push(b"\x00" * self.owner.flush_silence_bytes)
        self.send_batch()

    def keepalive(self, now: float) -> None:
        self.last_keepalive = now
        self.out.put_nowait(self.owner.provider.keepalive)

    # --- socket ----------------------------------------------------------------------------

    def start(self) -> None:
        self.running = True
        self.task = self.owner.spawn(self._run())

    async def _run(self) -> None:
        owner, started = self.owner, time.perf_counter()
        init = owner.provider.init(keyterms=owner.keyterms(), context=owner.context())
        sender: asyncio.Task[None] | None = None
        try:
            async with websockets.connect(
                owner.url, additional_headers=owner.headers, max_size=None, open_timeout=5
            ) as ws:
                await ws.send(json.dumps(init))
                self.ws, self.open, self.last_keepalive = ws, True, time.time()
                owner.debug(
                    "stt.stream.open",
                    discordId=self.discord_id,
                    connectMs=int((time.perf_counter() - started) * 1000),
                    backlogMs=self.queued_bytes_waiting() // BYTES_PER_MS,
                )
                sender = asyncio.create_task(self._send_loop(ws))
                async for raw in ws:
                    if isinstance(raw, str):
                        self.on_message(json.loads(raw))
        except Exception as exc:  # noqa: BLE001 - any socket failure: report, reopen on next audio
            if self.closing:
                return  # our own close; the finally block still runs
            error = f"{type(exc).__name__}: {exc}"[:300]
            owner.debug("stt.stream.error", discordId=self.discord_id, error=error)
            logger.warning("stt.stream.error", discord_id=self.discord_id, error=error)
        finally:
            if sender is not None:
                sender.cancel()
            self.flush_pending(utterance_end=True)
            self.ws, self.open, self.running = None, False, False
            owner.forget(self)
            owner.debug(
                "stt.stream.close",
                discordId=self.discord_id,
                audioMs=self.queued_bytes // BYTES_PER_MS,
            )

    async def _send_loop(self, ws: Any) -> None:
        while True:
            await ws.send(await self.out.get())

    def on_message(self, msg: dict[str, Any]) -> None:
        parsed = self.owner.provider.parse(msg)
        if parsed.error:
            self.owner.debug("stt.stream.error", discordId=self.discord_id, error=parsed.error)
        if parsed.partial:
            self.owner.debug("stt.partial", discordId=self.discord_id, text=parsed.partial)
        self.pending += parsed.finals
        if parsed.endpoint or self._pending_seconds() * 1000 >= self.owner.chunk_max_ms:
            self.flush_pending(utterance_end=parsed.endpoint)

    def _pending_seconds(self) -> float:
        return self.pending[-1].end - self.pending[0].start if self.pending else 0.0

    def flush_pending(self, *, utterance_end: bool) -> None:
        words, self.pending = self.pending, []
        if not words:
            return
        runs: list[list[Word]] = []
        for w in words:
            if runs and runs[-1][-1].speaker == w.speaker:
                runs[-1].append(w)
            else:
                runs.append([w])
        out: list[Segment] = []
        for i, run in enumerate(runs):
            text = "".join(w.text if w.joined else " " + w.text for w in run).strip()
            if not text:
                continue
            confs = [w.confidence for w in run if w.confidence is not None]
            out.append(
                Segment(
                    discord_id=self.discord_id,
                    text=text,
                    started_at=self.wall(run[0].start),
                    ended_at=self.wall(run[-1].end),
                    speaker=run[0].speaker,
                    confidence=sum(confs) / len(confs) if confs else None,
                    utterance_end=utterance_end and i == len(runs) - 1,
                )
            )
        if out:
            self.owner.on_segments(self.discord_id, out)

    async def close(self) -> None:
        self.closing = True
        if self.ws is not None:
            with contextlib.suppress(Exception):
                await self.ws.close()


class StreamingStt:
    def __init__(
        self,
        settings: Settings,
        provider: Provider,
        *,
        on_segments: SegmentSink,
        debug: DebugSink,
        keyterms: Callable[[], list[str]],
        context: Callable[[], str],
    ) -> None:
        base = settings.slng_base_url.rstrip("/")
        base = base.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
        self.url = base + provider.path
        self.headers = {"Authorization": f"Bearer {settings.slng_api_key}"}
        self.provider = provider
        self.on_segments = on_segments
        self.debug = debug
        self.keyterms = keyterms
        self.context = context
        self.flush_after = settings.stt_flush_ms / 1000
        self.flush_silence_bytes = settings.stt_flush_silence_ms * BYTES_PER_MS
        self.idle_close = settings.stt_idle_close_s
        self.chunk_max_ms = settings.chunk_max_ms
        self.streams: dict[str, _Stream] = {}
        self._tasks: set[asyncio.Task[Any]] = set()

    def feed(self, discord_id: str, pcm_48k_stereo: bytes, now: float) -> None:
        stream = self.streams.get(discord_id)
        if stream is None:
            stream = self.streams[discord_id] = _Stream(self, discord_id)
        stream.feed(to_mono_16k(pcm_48k_stereo), now)

    def tick(self, now: float) -> None:
        """Called by the app clock: flush pauses, keep idle sockets alive, close stale ones."""
        for stream in list(self.streams.values()):
            idle = now - stream.last_audio
            if not stream.flushed and idle >= self.flush_after:
                stream.flush_silence()
            if not stream.open:
                continue
            if idle >= self.idle_close:
                self.spawn(stream.close())
            elif stream.flushed and now - stream.last_keepalive >= 5:
                stream.keepalive(now)

    def forget(self, stream: _Stream) -> None:
        if self.streams.get(stream.discord_id) is stream:
            del self.streams[stream.discord_id]

    def spawn(self, coro: Any) -> asyncio.Task[Any]:
        task = asyncio.get_running_loop().create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def close(self) -> None:
        unflushed = [s for s in self.streams.values() if not s.flushed]
        for stream in unflushed:
            stream.flush_silence()
        if unflushed:
            await asyncio.sleep(0.8)  # give endpointing a moment to return the last finals
        for stream in list(self.streams.values()):
            await stream.close()
