"""The stenographer: voice events in, frames out.

`Ears` is the composition root. It receives voice callbacks (all on the event
loop), shapes them into contract frames, and fans every frame out: the brain's
WebSocket, the console, Redis, and Postgres. It owns the session (one run of a
meeting set up in the console) and the playback queue for `speak`.

Debug events (`{"type": "debug", "kind": ...}`) go to the console only — they
explain what ears did (STT latency, skipped silence, TTS, playback) and are never
part of the contract.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .audio import rms, to_mono_16k
from .bus import Bus
from .db.models import TranscriptChunk, Turn
from .db.store import Store, parse_iso
from .frames import (
    MAX_MUTE_SECONDS,
    EarsFrame,
    Moderation,
    Mute,
    Participant,
    Participants,
    Ready,
    SessionEnded,
    SessionStarted,
    Speak,
    SpeakChunk,
    SpeakEnd,
    SpeakingEnd,
    SpeakingStart,
    SpeakStart,
    Spoken,
    Stop,
    Transcript,
    TurnEnd,
    Unmute,
    iso,
    parse_brain_frame,
    stamp,
)
from .logging import get_logger
from .meetings import Meeting
from .pcm_stream import PcmStream
from .segmenter import Chunk, Segmenter
from .settings import Settings
from .status_board import StatusConfig
from .stt import SlngStt, SttError
from .stt_stream import Segment, StreamingStt, make_provider
from .tts import SlngTts, TtsError
from .turns import TurnTracker
from .wire import Hub

if TYPE_CHECKING:
    from .voice import Voice

logger = get_logger(__name__)

CLOCK_SECONDS = 0.1
RECEIVE_STATS_EVERY = 5.0
# What a console that connects late gets replayed.
RECENT_LIMIT = 1_000


@dataclass(frozen=True)
class _Utterance:
    utterance_id: str
    audio: bytes
    source: str  # "brain" | "console"
    priority: bool = False
    text: str | None = None
    # A line still arriving over `speak.chunk` frames; `audio` is empty then.
    stream: PcmStream | None = None
    # Wait for a pause in the room: nobody heard for `quiet_ms`, or `max_wait_ms` in line.
    quiet_ms: int | None = None
    max_wait_ms: int | None = None
    queued_at: float = field(default_factory=time.time)


class Ears:
    def __init__(
        self,
        settings: Settings,
        store: Store,
        bus: Bus,
        stt: SlngStt | None,
        tts: SlngTts | None = None,
    ) -> None:
        self.settings = settings
        self.store = store
        self.bus = bus
        self.stt = stt
        self.tts = tts
        self.hub = Hub()  # brains
        self.console = Hub()  # console pages
        self.recent: deque[dict[str, Any]] = deque(maxlen=RECENT_LIMIT)
        self.voice: Voice | None = None
        self.turns = TurnTracker(settings.turn_gap_ms, settings.turn_tick_ms)
        self.segmenter = Segmenter(
            settings.utterance_gap_ms, settings.chunk_max_ms, settings.chunk_min_ms
        )
        self.guild_id: str | None = None
        self.channel_id: str | None = None
        self.participants: dict[str, Participant] = {}
        self.session_id: str | None = None
        # The meeting of the current session — or of the last one, reused on rejoin.
        self.meeting: Meeting | None = None
        # Frozen when a session starts so reconnecting brains receive the same roster.
        self._session_agenda: dict[str, Any] | None = None
        self._stt_locks: dict[str, asyncio.Lock] = {}
        self._tasks: set[asyncio.Task[Any]] = set()
        self._playback: deque[_Utterance] = deque()
        self._playing: _Utterance | None = None
        self._interrupted = False
        # Last time a human was audibly speaking. Packet arrival alone is not enough: an open
        # voice-activated mic keeps sending breath and room noise, and the room never pauses.
        self._last_voice_at = 0.0
        self._holding_since: float | None = None
        # Streamed lines still receiving chunks, queued or playing.
        self._streams: dict[str, PcmStream] = {}
        # People ears server-muted, and the timer that lifts it. ears only ever unmutes these.
        self._muted: dict[str, asyncio.TimerHandle] = {}
        # Streaming STT (default) replaces the segmenter + HTTP path.
        self.stream: StreamingStt | None = None
        if settings.stt_mode == "stream" and settings.stt_enabled:
            self.stream = StreamingStt(
                settings,
                make_provider(settings),
                on_segments=self._on_segments,
                debug=self.debug,
                keyterms=self._keyterms,
                context=self._stt_context,
            )
        self._utterance: dict[str, tuple[str, int]] = {}  # discord_id → (utterance id, next seq)
        # Each server's status-message settings (console); loaded from Postgres at startup.
        self.status_configs: dict[str, StatusConfig] = {}

    # --- fan-out ---------------------------------------------------------------------

    def emit(self, frame: EarsFrame) -> dict[str, Any]:
        body = stamp(frame)
        self.hub.broadcast(body)
        self.console.broadcast(body)
        self.recent.append(body)
        self.bus.publish(body)
        self.store.event(body)
        return body

    def debug(self, kind: str, **data: Any) -> None:
        now = time.time()
        body = {"type": "debug", "kind": kind, **data, "at": iso(now), "atMs": int(now * 1000)}
        self.console.broadcast(body)
        self.recent.append(body)

    def hello(self) -> list[dict[str, Any]]:
        """Re-announced to every brain that connects, per the contract."""
        out: list[dict[str, Any]] = []
        if self.channel_id is not None:
            people = list(self.participants.values())
            out += [
                stamp(Ready(channel_id=self.channel_id, participants=people)),
                stamp(Participants(participants=people)),
            ]
        if self.session_id is not None:
            out.append(stamp(self._session_frame(self.session_id)))
        return out

    def status(self) -> dict[str, Any]:
        return {
            "voice": self.channel_id is not None,
            "channelId": self.channel_id,
            "sessionId": self.session_id,
            "meeting": self.meeting.model_dump(by_alias=True) if self.meeting else None,
            "participants": [p.model_dump(by_alias=True) for p in self.participants.values()],
            "turns": self.turns.active(),
            "brains": len(self.hub),
            "consoles": len(self.console),
            "postgres": self.store.enabled,
            "redis": self.bus.enabled,
            "stt": (
                f"stream · {self.settings.slng_stt_model}"
                if self.stream
                else ("http" if self.stt else None)
            ),
            "tts": self.tts.model if self.tts else None,
            "playback": {"playing": self._playing is not None, "queued": len(self._playback)},
        }

    def discord_servers(self) -> dict[str, Any]:
        if self.voice is None:
            return {"connected": False, "servers": []}
        view = self.voice.discord_servers()
        for server in view["servers"]:
            server["status"] = self.status_config(server["id"]).view()
        return view

    def status_config(self, guild_id: str) -> StatusConfig:
        return self.status_configs.get(guild_id, StatusConfig())

    async def configure_status(
        self, guild_id: str, enabled: bool, channel_id: str | None
    ) -> dict[str, Any]:
        """Whether a server gets the status message, and in which text channel (None: voice chat)."""
        if self.voice is None:
            raise RuntimeError("Discord bot is not running")
        server = next((s for s in self.discord_servers()["servers"] if s["id"] == guild_id), None)
        if server is None:
            raise ValueError("Discord server is not available to this bot")
        if channel_id is not None and not any(
            c["id"] == channel_id for c in server["textChannels"]
        ):
            raise ValueError("text channel is not available on this Discord server")
        config = StatusConfig(enabled=enabled, channel_id=channel_id)
        self.status_configs[guild_id] = config
        await self.store.set_discord_status(guild_id, config)
        self.debug("status.configured", guildId=guild_id, **config.view())
        return self.discord_servers()

    async def configure_discord_channel(
        self, guild_id: str, channel_id: str | None
    ) -> dict[str, Any]:
        if self.voice is None:
            raise RuntimeError("Discord bot is not running")
        await self.voice.configure_channel(guild_id, channel_id)
        await self.store.set_discord_channel(guild_id, channel_id)
        return self.voice.discord_servers()

    # --- sessions -----------------------------------------------------------------------

    def start_session(
        self, meeting: Meeting | None, participants: list[Participant] | None = None
    ) -> str:
        """End the current session, if any, and start a new run of `meeting`."""
        self.end_session()
        sid = uuid.uuid4()
        self.session_id, self.meeting = str(sid), meeting
        people = participants if participants is not None else list(self.participants.values())
        self._session_agenda = meeting.agenda_for(self.session_id, people) if meeting else None
        self.store.start_session(
            sid,
            meeting_id=meeting.id if meeting else None,
            guild_id=self.guild_id,
            channel_id=self.channel_id,
        )
        self.store.participants(list(self.participants.values()))
        self.emit(self._session_frame(self.session_id))
        logger.info(
            "session.started", session_id=self.session_id, meeting=meeting and meeting.title
        )
        return self.session_id

    def end_session(self) -> None:
        if self.session_id is None:
            return
        self._unmute_all()
        self._close_open_speech()
        self.emit(SessionEnded(session_id=self.session_id))
        self.store.end_session()
        logger.info("session.ended", session_id=self.session_id)
        self.session_id = None
        self._session_agenda = None

    def _session_frame(self, session_id: str) -> SessionStarted:
        m = self.meeting
        return SessionStarted(
            session_id=session_id,
            meeting_id=m.id if m else None,
            title=m.title if m else None,
            context=m.context if m else None,
            agenda=self._session_agenda if m else None,
        )

    # --- VoiceEvents -----------------------------------------------------------------

    def on_joined(self, guild_id: str, channel_id: str, participants: list[Participant]) -> None:
        moved = self.channel_id is not None and channel_id != self.channel_id
        self.guild_id, self.channel_id = guild_id, channel_id
        self.debug("voice.joined", channelId=channel_id, moved=moved)
        if moved or self.session_id is None:
            self.start_session(self.meeting, participants)
        else:
            self.store.set_session_channel(guild_id, channel_id)
        self._set_participants(participants)  # after the session exists, so it is recorded
        self.emit(Ready(channel_id=channel_id, participants=participants))

    def on_left(self) -> None:
        # The session stays open: the bot may be back in a moment.
        self._unmute_all()
        self._close_open_speech()
        self.debug("voice.left", channelId=self.channel_id)
        self.channel_id = None
        self._set_participants([])
        self.emit(Participants(participants=[]))

    def on_participants(self, participants: list[Participant]) -> None:
        self._set_participants(participants)
        self.emit(Participants(participants=participants))

    def on_speaking(self, discord_id: str, speaking: bool, at: float) -> None:
        if speaking:
            self.emit(SpeakingStart(discord_id=discord_id))
            frames = self.turns.speaking_start(discord_id, at)
        else:
            self.emit(SpeakingEnd(discord_id=discord_id))
            frames = self.turns.speaking_end(discord_id, at)
        for frame in frames:
            self.emit(frame)

    def on_pcm(self, discord_id: str, pcm: bytes, at: float) -> None:
        if rms(pcm) >= self.settings.silence_rms:
            self._last_voice_at = max(self._last_voice_at, at)
        if self.stream is not None:
            self.stream.feed(discord_id, pcm, at)
            return
        for chunk in self.segmenter.push(discord_id, pcm, at):
            self._transcribe(chunk)

    # --- the clock ------------------------------------------------------------------------

    async def run_clock(self) -> None:
        """Closes turns and utterances on silence, emits `turn.tick`s, reports receive health."""
        last_stats = time.time()
        while True:
            await asyncio.sleep(CLOCK_SECONDS)
            now = time.time()
            for frame in self.turns.tick(now):
                self._emit_turn(frame)
            if self._playing is None and self._playback:
                self._play_next()  # a line waiting for a pause
            if self.stream is not None:
                self.stream.tick(now)
            for chunk in self.segmenter.tick(now):
                self._transcribe(chunk)
            if now - last_stats >= RECEIVE_STATS_EVERY:
                last_stats = now
                stats = self.voice.receive_stats() if self.voice is not None else {}
                if stats:
                    self.debug("voice.receive", **stats)

    def _emit_turn(self, frame: EarsFrame) -> None:
        self.emit(frame)
        if isinstance(frame, TurnEnd):
            self.store.add(
                Turn(
                    id=uuid.UUID(frame.turn_id),
                    discord_id=frame.discord_id,
                    started_at=parse_iso(frame.started_at),
                    ended_at=parse_iso(frame.ended_at),
                    duration_ms=frame.duration_ms,
                    speaking_ms=frame.speaking_ms,
                )
            )

    def _close_open_speech(self) -> None:
        for frame in self.turns.close_all(time.time()):
            self._emit_turn(frame)
        for chunk in self.segmenter.flush_all():
            self._transcribe(chunk)

    # --- transcription -----------------------------------------------------------------

    def _transcribe(self, chunk: Chunk) -> None:
        if self.stt is None:
            return
        # Captured now: by the time STT answers, the turn may have ended.
        turn_id = self.turns.current_turn_id(chunk.discord_id)
        self._spawn(self._transcribe_chunk(chunk, turn_id))

    async def _transcribe_chunk(self, chunk: Chunk, turn_id: str | None) -> None:
        assert self.stt is not None
        pcm = to_mono_16k(chunk.pcm)
        level = rms(pcm)
        who = {"discordId": chunk.discord_id, "utteranceId": chunk.utterance_id, "seq": chunk.seq}
        if level < self.settings.silence_rms:
            self.debug("stt.skipped", **who, audioMs=chunk.audio_ms, rms=round(level, 1))
            return
        keyterms = [p.name for p in self.participants.values()]
        # One request at a time per speaker keeps their transcript in order.
        # asyncio.Lock wakes waiters FIFO.
        lock = self._stt_locks.setdefault(chunk.discord_id, asyncio.Lock())
        async with lock:
            try:
                result = await self.stt.transcribe(pcm, keyterms=keyterms)
            except SttError as exc:
                logger.warning("stt.failed", discord_id=chunk.discord_id, error=str(exc))
                self.debug("stt.failed", **who, error=str(exc)[:300])
                return
        self.debug(
            "stt.result",
            **who,
            final=chunk.final,
            audioMs=chunk.audio_ms,
            sttMs=result.latency_ms,
            rms=round(level, 1),
            empty=not result.text,
        )
        if not result.text:
            return
        person = self.participants.get(chunk.discord_id)
        frame = Transcript(
            discord_id=chunk.discord_id,
            name=person.name if person else chunk.discord_id,
            text=result.text,
            started_at=iso(chunk.started_at),
            ended_at=iso(chunk.ended_at),
            utterance_id=chunk.utterance_id,
            seq=chunk.seq,
            final=chunk.final,
            turn_id=turn_id,
            confidence=result.confidence,
        )
        self.emit(frame)
        logger.info(
            "transcript",
            who=frame.name,
            text=frame.text,
            audio_ms=chunk.audio_ms,
            stt_ms=result.latency_ms,
        )
        self.store.add(
            TranscriptChunk(
                discord_id=chunk.discord_id,
                utterance_id=uuid.UUID(chunk.utterance_id),
                seq=chunk.seq,
                turn_id=uuid.UUID(turn_id) if turn_id else None,
                started_at=parse_iso(frame.started_at),
                ended_at=parse_iso(frame.ended_at),
                text=result.text,
                confidence=result.confidence,
                audio_ms=chunk.audio_ms,
                stt_ms=result.latency_ms,
            )
        )

    # --- streaming transcription ------------------------------------------------------

    def _keyterms(self) -> list[str]:
        names = {p.name for p in self.participants.values()}
        if self.meeting is not None:
            names |= {a.name for a in self.meeting.agenda.attendees if a.name}
        return sorted(names)[:50]

    def _stt_context(self) -> str:
        m = self.meeting
        if m is None:
            return ""
        topics = "; ".join(t.title for t in m.agenda.topics if t.title)
        return " ".join(x for x in (m.title, m.agenda.purpose, m.context, topics) if x)

    def _on_segments(self, discord_id: str, segments: list[Segment]) -> None:
        person = self.participants.get(discord_id)
        turn_id = self.turns.current_turn_id(discord_id)
        now = time.time()
        for seg in segments:
            utterance_id, seq = self._utterance.get(discord_id) or (str(uuid.uuid4()), 0)
            frame = Transcript(
                discord_id=discord_id,
                name=person.name if person else discord_id,
                text=seg.text,
                started_at=iso(seg.started_at),
                ended_at=iso(seg.ended_at),
                utterance_id=utterance_id,
                seq=seq,
                final=seg.utterance_end,
                turn_id=turn_id,
                confidence=seg.confidence,
                speaker=seg.speaker,
            )
            self._utterance[discord_id] = (
                (str(uuid.uuid4()), 0) if seg.utterance_end else (utterance_id, seq + 1)
            )
            self.debug(
                "stt.final",
                discordId=discord_id,
                utteranceId=utterance_id,
                seq=seq,
                speaker=seg.speaker,
                lagMs=int((now - seg.ended_at) * 1000),
            )
            self.emit(frame)
            logger.info("transcript", who=frame.name, speaker=seg.speaker, text=seg.text)
            self.store.add(
                TranscriptChunk(
                    discord_id=discord_id,
                    utterance_id=uuid.UUID(utterance_id),
                    seq=seq,
                    turn_id=uuid.UUID(turn_id) if turn_id else None,
                    started_at=parse_iso(frame.started_at),
                    ended_at=parse_iso(frame.ended_at),
                    text=seg.text,
                    confidence=seg.confidence,
                    audio_ms=int((seg.ended_at - seg.started_at) * 1000),
                    stt_ms=int((now - seg.ended_at) * 1000),
                )
            )

    # --- speaking into the call ---------------------------------------------------------

    def command(self, raw: str | bytes) -> None:
        """A frame from the brain, over the WebSocket or Redis."""
        frame = parse_brain_frame(raw)
        if frame is None:
            logger.warning("command.ignored", raw=str(raw)[:120])
            self.debug("command.ignored", raw=str(raw)[:120])
        elif isinstance(frame, Stop):
            self.stop_playback()
        elif isinstance(frame, Speak):
            try:
                audio = base64.b64decode(frame.audio, validate=True)
            except (binascii.Error, ValueError):
                self.emit(
                    Spoken(utterance_id=frame.utterance_id, error="audio is not valid base64")
                )
                return
            self.enqueue(
                _Utterance(
                    frame.utterance_id,
                    audio,
                    "brain",
                    frame.priority,
                    frame.text,
                    quiet_ms=frame.quiet_ms,
                    max_wait_ms=frame.max_wait_ms,
                )
            )
        elif isinstance(frame, SpeakStart):
            stream = PcmStream(channels=frame.channels)
            self._streams[frame.utterance_id] = stream
            self.enqueue(
                _Utterance(
                    frame.utterance_id,
                    b"",
                    "brain",
                    frame.priority,
                    frame.text,
                    stream,
                    quiet_ms=frame.quiet_ms,
                    max_wait_ms=frame.max_wait_ms,
                )
            )
        elif isinstance(frame, SpeakChunk):
            target = self._streams.get(frame.utterance_id)
            if target is None:
                return
            try:
                target.feed(base64.b64decode(frame.audio, validate=True))
            except (binascii.Error, ValueError):
                self.debug("speak.bad_chunk", utteranceId=frame.utterance_id)
        elif isinstance(frame, SpeakEnd):
            ended = self._streams.pop(frame.utterance_id, None)
            if ended is not None:
                ended.end()
                self.debug(
                    "speak.stream_end",
                    utteranceId=frame.utterance_id,
                    bytes=ended.fed_bytes,
                    underruns=ended.underruns,
                    error=frame.error,
                )
        elif isinstance(frame, Mute):
            self._spawn(self._mute(frame.discord_id, frame.seconds, frame.reason))
        elif isinstance(frame, Unmute):
            if frame.discord_id in self._muted:
                self._spawn(self._unmute(frame.discord_id))
            else:
                self.emit(
                    Moderation(
                        action="failed", discord_id=frame.discord_id, error="not muted by gavel"
                    )
                )

    async def say(self, text: str) -> dict[str, Any]:
        """Console say-box: SLNG TTS, then the same playback path as the brain's `speak`."""
        if self.tts is None:
            raise TtsError("TTS is off — SLNG_API_KEY is unset")
        uid = str(uuid.uuid4())
        self.debug("tts.request", utteranceId=uid, text=text, model=self.tts.model)
        try:
            result = await self.tts.synthesize(text)
        except TtsError as exc:
            self.debug("tts.failed", utteranceId=uid, error=str(exc)[:300])
            raise
        self.debug(
            "tts.result",
            utteranceId=uid,
            ttsMs=result.latency_ms,
            bytes=len(result.audio),
            contentType=result.content_type,
        )
        self.enqueue(_Utterance(uid, result.audio, "console"))
        return {"utteranceId": uid, "ttsMs": result.latency_ms}

    def enqueue(self, item: _Utterance) -> None:
        if item.priority:
            # Ahead of everything queued; cut off whatever non-priority line is playing.
            self._playback.appendleft(item)
        else:
            self._playback.append(item)
        self.debug(
            "speak.queued",
            utteranceId=item.utterance_id,
            source=item.source,
            bytes=len(item.audio),
            queued=len(self._playback),
            priority=item.priority,
            text=item.text,
        )
        playing = self._playing
        if (
            item.priority
            and playing is not None
            and not playing.priority
            and self.voice
            and self._may_start(item, time.time())
        ):
            self.debug("speak.preempted", utteranceId=playing.utterance_id)
            self._interrupted = True
            self.voice.stop_playback()
            return
        self._play_next()

    def stop_playback(self) -> None:
        dropped = len(self._playback)
        for item in self._playback:
            if item.stream is not None:
                item.stream.end()
                self._streams.pop(item.utterance_id, None)
        self._playback.clear()
        self.debug("speak.stop", dropped=dropped, playing=self._playing is not None)
        if self._playing is not None and self.voice is not None:
            self._interrupted = True
            self.voice.stop_playback()

    def _play_next(self) -> None:
        if self._playing is not None or not self._playback:
            return
        now = time.time()
        item = self._playback[0]
        if item.quiet_ms is not None:
            if not self._may_start(item, now):
                if self._holding_since is None:
                    self._holding_since = now
                    self.debug("speak.holding", utteranceId=item.utterance_id)
                return  # the clock asks again every tick
            quiet = (now - self._last_voice_at) * 1000
            self.debug(
                "speak.released",
                utteranceId=item.utterance_id,
                waitedMs=int((now - item.queued_at) * 1000),
                pause=quiet >= item.quiet_ms,
            )
        self._holding_since = None
        self._playback.popleft()
        played = self.voice is not None and (
            self.voice.play_source(item.stream, self._on_played, item.priority)
            if item.stream is not None
            else self.voice.play(item.audio, self._on_played, item.priority)
        )
        if not played:
            self.emit(Spoken(utterance_id=item.utterance_id, error="not in a voice channel"))
            self._play_next()
            return
        self._playing = item
        self.debug(
            "speak.playing",
            utteranceId=item.utterance_id,
            source=item.source,
            priority=item.priority,
        )
        logger.info("speak.playing", utterance_id=item.utterance_id, source=item.source)

    def _may_start(self, item: _Utterance, now: float) -> bool:
        """Nobody has been heard for `quiet_ms`, or the line has waited long enough."""
        if item.quiet_ms is None:
            return True
        if (now - self._last_voice_at) * 1000 >= item.quiet_ms:
            return True
        return item.max_wait_ms is not None and (now - item.queued_at) * 1000 >= item.max_wait_ms

    def _on_played(self, error: Exception | None) -> None:
        item, self._playing = self._playing, None
        interrupted, self._interrupted = self._interrupted, False
        if item is not None:
            self.emit(
                Spoken(
                    utterance_id=item.utterance_id,
                    interrupted=interrupted,
                    error=str(error) if error else None,
                )
            )
        self._play_next()

    # --- the brain's store -----------------------------------------------------------------
    # The brain writes what it decided through ears, so there is one database. Each write
    # also lands in the console log.

    async def add_memory(self, body: dict[str, Any]) -> dict[str, Any]:
        memory = await self.store.add_memory(body)
        self.debug("memory.added", memory=memory)
        return memory

    async def set_memory_status(self, memory_id: str, status: str) -> dict[str, Any] | None:
        memory = await self.store.set_memory_status(memory_id, status)
        if memory is not None:
            self.debug("memory.updated", id=memory_id, status=status)
        return memory

    def record_intervention(self, body: dict[str, Any]) -> None:
        self.store.intervention(body)
        self.debug(
            "chair.intervention",
            intervention={k: v for k, v in body.items() if v is not None},
        )

    def record_llm_call(self, body: dict[str, Any]) -> dict[str, float]:
        totals = self.store.llm_call(body)
        self.debug(
            "chair.llm",
            agent=body["agent"],
            model=body["model"],
            inputTokens=body.get("input_tokens", 0),
            outputTokens=body.get("output_tokens", 0),
            latencyMs=body.get("latency_ms", 0),
            cacheHit=body.get("cache_hit", False),
            sessionCostUsd=round(totals["costUsd"], 6),
        )
        return totals

    # --- moderation ------------------------------------------------------------------------

    async def _mute(self, discord_id: str, seconds: float, reason: str | None) -> None:
        seconds = min(seconds, MAX_MUTE_SECONDS)
        if self.voice is None:
            self.emit(
                Moderation(action="failed", discord_id=discord_id, error="not in a voice channel")
            )
            return
        try:
            await self.voice.set_mute(discord_id, True, reason)
        except Exception as exc:  # noqa: BLE001 - permissions, left the channel, API errors
            logger.warning("moderation.mute_failed", discord_id=discord_id, error=str(exc))
            self.emit(Moderation(action="failed", discord_id=discord_id, error=str(exc)[:300]))
            return
        previous = self._muted.pop(discord_id, None)
        if previous is not None:
            previous.cancel()
        self._muted[discord_id] = asyncio.get_running_loop().call_later(
            seconds, lambda: self._spawn(self._unmute(discord_id))
        )
        until = int((time.time() + seconds) * 1000)
        self.emit(Moderation(action="muted", discord_id=discord_id, until=until))
        logger.info("moderation.muted", discord_id=discord_id, seconds=seconds, reason=reason)

    async def _unmute(self, discord_id: str) -> None:
        handle = self._muted.pop(discord_id, None)
        if handle is None:
            return
        handle.cancel()
        if self.voice is None:
            return
        try:
            await self.voice.set_mute(discord_id, False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("moderation.unmute_failed", discord_id=discord_id, error=str(exc))
            self.emit(Moderation(action="failed", discord_id=discord_id, error=str(exc)[:300]))
            return
        self.emit(Moderation(action="unmuted", discord_id=discord_id))
        logger.info("moderation.unmuted", discord_id=discord_id)

    def _unmute_all(self) -> None:
        for discord_id in list(self._muted):
            self._spawn(self._unmute(discord_id))

    # --- plumbing -----------------------------------------------------------------------------

    def _set_participants(self, participants: list[Participant]) -> None:
        self.participants = {p.discord_id: p for p in participants}
        self.store.participants(participants)

    def _spawn(self, coro: Any) -> None:
        task = asyncio.get_running_loop().create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def shutdown(self) -> None:
        await asyncio.gather(*(self._unmute(d) for d in list(self._muted)))
        self._close_open_speech()
        if self.stream is not None:
            await self.stream.close()
        if self._tasks:
            await asyncio.wait(self._tasks, timeout=5)
        self.end_session()
