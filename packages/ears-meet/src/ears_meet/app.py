"""The composition root: raw observations in, contract frames out, brain commands in.

`Ears` owns the wire hubs, the roster, the speaking debounce, the turn tracker, the
caption miner, the mixed-audio STT, the playback queue and the session — everything that
is not the browser or PulseAudio themselves. It never touches Playwright: browser.py
posts observer events into `on_observer_event`, pulse.py's Recorder calls `on_pcm`, and
the `Surface` protocol is the handful of browser actions the app asks for. Tests drive
this class with a fake surface and a FakePlayer; the shape is ears-discord's app.py.

Where each contract frame comes from, on Meet:
  ready / participants   the tiles + People panel (roster.py)
  speaking.start / .end  the tile indicator, debounced (speaking.py) — no audio involved
  transcript             Meet captions (captions.py) or SLNG STT on the mixed audio,
                         attributed by the speaking timeline (attribution.py)
  spoken                 playback into the microphone sink finished (pulse.py)
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import time
import uuid
from collections import deque
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from . import selectors as sel
from .agenda import agenda_for
from .attribution import UNATTRIBUTED, Attributor
from .audio import rms
from .captions import Caption, CaptionMiner
from .frames import (
    ChairVoice,
    EarsFrame,
    Moderation,
    Mute,
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
from .pulse import FakePlayer, PcmSource, Player
from .roster import Roster, Tile
from .settings import Settings
from .speaking import SpeakingDebouncer, Transition
from .store import FrameLog, MemoryStore
from .stt_stream import MIX_ID, Segment, StreamingStt, make_provider
from .tts import SlngTts, TtsError
from .turns import TurnTracker
from .wire import Hub

logger = get_logger("ears_meet.app")

CLOCK_SECONDS = 0.1
SURFACE_HEALTH_EVERY = 5.0
SHUTDOWN_TIMEOUT_SECONDS = 5
RECENT_FRAMES = 500
# Egress proof: a line at least this long must light the bot's own indicator, or `spoken`
# carries an error. Shorter lines can be swallowed by Meet's VAD attack time.
EGRESS_VERIFY_MIN_S = 1.0


class Surface(Protocol):
    """What the app asks of the browser. browser.Browser satisfies it; tests use a fake."""

    async def ensure_unmuted(self) -> bool: ...
    async def self_check(self) -> sel.SelfCheckResult: ...
    async def present_stage(self) -> bool: ...
    async def pages(self) -> list[dict[str, str]]: ...
    async def observer_alive(self) -> bool: ...
    async def install_observer(self) -> None: ...
    async def is_in_call(self) -> bool: ...
    async def leave(self) -> None: ...


@dataclass
class _Utterance:
    utterance_id: str
    audio: bytes
    source: str  # "brain" | "console"
    priority: bool = False
    text: str | None = None
    stream: PcmSource | None = None
    quiet_ms: int | None = None
    max_wait_ms: int | None = None
    queued_at: float = 0.0
    started_at: float = 0.0


class Ears:
    def __init__(
        self,
        settings: Settings,
        *,
        player: Player | None = None,
        surface: Surface | None = None,
        http: httpx.AsyncClient | None = None,
        frame_log: FrameLog | None = None,
        clock: Callable[[], float] = time.time,
        verify_egress: bool = False,
    ) -> None:
        self.settings = settings
        self.clock = clock
        self.verify_egress = verify_egress
        self.hub = Hub()
        self.console = Hub()
        self.store = MemoryStore()
        self.frame_log = frame_log or FrameLog("")
        self.recent: deque[dict[str, Any]] = deque(maxlen=RECENT_FRAMES)
        self.player: Player = player if player is not None else FakePlayer()
        self.surface = surface
        self.http = http or httpx.AsyncClient()
        self.tts = SlngTts(settings, self.http) if settings.slng_api_key else None
        self.tts_voice = settings.slng_tts_voice

        self.roster = Roster(settings.meet_bot_name)
        self.debounce = SpeakingDebouncer(settings.speaking_on_ms, settings.speaking_off_ms)
        self.turns = TurnTracker(settings.turn_gap_ms, settings.turn_tick_ms)
        self.captions = CaptionMiner(settings.caption_settle_ms)
        self.attributor = Attributor()
        self.stream: StreamingStt | None = None
        if settings.stt_enabled and settings.transcript_source in ("auto", "stt"):
            self.stream = StreamingStt(
                settings,
                make_provider(settings),
                on_segments=self._on_segments,
                debug=self.debug,
                keyterms=self._keyterms,
                context=self._stt_context,
            )

        self.channel_id: str | None = None  # the Meet code, once joined
        self.session_id: str | None = None
        self.saved_agenda: dict[str, Any] | None = None
        self._session_agenda: dict[str, Any] | None = None
        self._title: str | None = None
        self._context: str | None = None
        self.captions_visible = False
        self.stage_presenting = False
        self.self_check_result: sel.SelfCheckResult | None = None
        self._last_voice_at = 0.0
        self._alone_since: float | None = None
        self._pcm_frames = 0
        self._pcm_audible = 0

        self._playback: deque[_Utterance] = deque()
        self._playing: _Utterance | None = None
        self._interrupted = False
        self._holding_since: float | None = None
        self._streams: dict[str, PcmSource] = {}
        # Egress proof: when the bot's own tile indicator was last on.
        self._self_indicator_on_at: float | None = None
        self._self_indicator_seen = False

        self._utterance: dict[str, tuple[str, int]] = {}  # participant → (utterance id, seq)
        self._tasks: set[asyncio.Task[Any]] = set()
        self._surface_checked_at = 0.0
        self.on_leave: Callable[[], Coroutine[Any, Any, None]] | None = None
        # No MEET_URL: the wire, PulseAudio, Xvfb and the browser run, but nothing is joined.
        self.standby = not settings.meet_url

    # --- fan-out ------------------------------------------------------------------

    def emit(self, frame: EarsFrame, *, at: float | None = None) -> dict[str, Any]:
        body = stamp(frame, self.clock() if at is None else at)
        self.hub.broadcast(body)
        self.console.broadcast(body)
        self.recent.append(body)
        self.frame_log.write(body)
        return body

    def debug(self, kind: str, **data: Any) -> None:
        now = self.clock()
        body = {"type": "debug", "kind": kind, **data, "at": iso(now), "atMs": int(now * 1000)}
        self.console.broadcast(body)
        self.recent.append(body)

    def hello(self) -> list[dict[str, Any]]:
        """Re-announced to every brain that connects, per the contract."""
        out: list[dict[str, Any]] = [stamp(ChairVoice(voice=self.tts_voice))]
        if self.channel_id is not None:
            people = self.roster.participants()
            out += [
                stamp(Ready(channel_id=self.channel_id, participants=people)),
                stamp(Participants(participants=people)),
            ]
        if self.session_id is not None:
            out.append(stamp(self._session_frame(self.session_id)))
        return out

    def status(self) -> dict[str, Any]:
        check = self.self_check_result
        return {
            "mode": "standby" if self.standby else "call",
            "inCall": self.channel_id is not None,
            "channelId": self.channel_id,
            "sessionId": self.session_id,
            "participants": [p.model_dump(by_alias=True) for p in self.roster.participants()],
            "speaking": self.debounce.speaking(),
            "turns": self.turns.active(),
            "captions": self.captions_visible,
            "stage": self.stage_presenting,
            "stt": self.stream is not None,
            "tts": self.tts is not None,
            "transcriptSource": self.transcript_source(),
            "playing": self._playing.utterance_id if self._playing else None,
            "queued": len(self._playback),
            "brains": len(self.hub),
            "selfCheck": None
            if check is None
            else {"ok": check.ok, "missing": check.missing_required, "message": check.message()},
            "ingress": {"frames": self._pcm_frames, "audible": self._pcm_audible},
            "egressSeen": self._self_indicator_seen,
        }

    # --- sessions ------------------------------------------------------------------

    def start_session(
        self,
        *,
        title: str | None = None,
        context: str | None = None,
        agenda: dict[str, Any] | None = None,
    ) -> str:
        self.end_session()
        self.session_id = str(uuid.uuid4())
        saved = agenda if agenda is not None else self.saved_agenda
        self._session_agenda = agenda_for(saved, self.session_id, self.roster.participants())
        self._title = title or self.settings.meeting_title or None
        self._context = context or self.settings.meeting_context or None
        self.emit(self._session_frame(self.session_id))
        logger.info("session.started", session_id=self.session_id, title=self._title)
        return self.session_id

    def end_session(self) -> None:
        if self.session_id is None:
            return
        self._close_open_speech()
        self.emit(SessionEnded(session_id=self.session_id))
        logger.info("session.ended", session_id=self.session_id)
        self.session_id = None
        self._session_agenda = None

    def _session_frame(self, session_id: str) -> SessionStarted:
        agenda = self._session_agenda
        return SessionStarted(
            session_id=session_id,
            meeting_id=None,
            title=self._title or (agenda or {}).get("purpose"),
            context=self._context,
            agenda=agenda,
        )

    # --- the call ------------------------------------------------------------------

    def on_joined(self, channel_id: str) -> None:
        """We are in the call. `channel_id` is the Meet code (xxx-yyyy-zzz)."""
        self.channel_id = channel_id
        self.debug("meet.joined", channelId=channel_id)
        if self.session_id is None:
            self.start_session()
        self.emit(Ready(channel_id=channel_id, participants=self.roster.participants()))

    def on_left(self) -> None:
        self._close_open_speech()
        self.channel_id = None
        self.debug("meet.left")

    def on_observer_event(self, event: dict[str, Any]) -> None:
        """A raw observation from observer.js, via the Playwright binding."""
        kind = event.get("kind")
        at = float(event["t"]) / 1000 if "t" in event else self.clock()
        if kind == "tiles":
            self._on_tiles([Tile.from_event(t) for t in event.get("participants", [])], at)
        elif kind == "indicator":
            self._on_indicator(str(event.get("id", "")), bool(event.get("on")), at)
        elif kind == "caption":
            self._on_caption(
                int(event.get("key", 0)),
                str(event.get("speaker", "")),
                str(event.get("text", "")),
                at,
            )
        elif kind == "captions":
            self.captions_visible = bool(event.get("visible"))
            self.debug("captions.visible", visible=self.captions_visible)

    def _on_tiles(self, tiles: list[Tile], at: float) -> None:
        changed, joined, left = self.roster.update(tiles)
        for pid in left:
            self._apply(self.debounce.forget(pid, at))
        if not changed:
            return
        self.debug("roster.changed", joined=joined, left=left, size=len(self.roster))
        if self.channel_id is not None:
            self.emit(Participants(participants=self.roster.participants()), at=at)
        self._alone_since = at if len(self.roster) == 0 else None

    def _on_indicator(self, participant_id: str, on: bool, at: float) -> None:
        if not participant_id:
            return
        if self.roster.is_self(participant_id):
            self._self_indicator_seen = True
            if on:
                self._self_indicator_on_at = at
            return
        self._apply(self.debounce.observe(participant_id, on, at))

    def _apply(self, transitions: list[Transition]) -> None:
        for tr in transitions:
            if tr.speaking:
                self._last_voice_at = max(self._last_voice_at, tr.at)
                self.emit(SpeakingStart(discord_id=tr.participant_id), at=tr.at)
                self.attributor.speaking_start(tr.participant_id, tr.at)
                for frame in self.turns.speaking_start(tr.participant_id, tr.at):
                    self.emit(frame, at=tr.at)
            else:
                self.emit(SpeakingEnd(discord_id=tr.participant_id), at=tr.at)
                self.attributor.speaking_end(tr.participant_id, tr.at)
                for frame in self.turns.speaking_end(tr.participant_id, tr.at):
                    self.emit(frame, at=tr.at)

    def _close_open_speech(self) -> None:
        now = self.clock()
        self._apply(self.debounce.close_all(now))
        for frame in self.turns.close_all(now):
            self.emit(frame)
        for cap in self.captions.close_all():
            self._emit_caption(cap)

    # --- transcripts ---------------------------------------------------------------

    def transcript_source(self) -> str:
        """Which path feeds `transcript` right now."""
        mode = self.settings.transcript_source
        if mode == "auto":
            if self.captions_visible:
                return "captions"
            return "stt" if self.stream is not None else "none"
        if mode == "stt" and self.stream is None:
            return "none"
        return mode

    def _on_caption(self, key: int, speaker: str, text: str, at: float) -> None:
        if self.transcript_source() != "captions":
            return
        for cap in self.captions.observe(key, speaker, text, at):
            self._emit_caption(cap)

    def _emit_caption(self, cap: Caption) -> None:
        if cap.speaker.casefold() in ("you", self.settings.meet_bot_name.casefold()):
            return  # the chair's own lines are not the room's transcript
        person = self.roster.by_name(cap.speaker)
        pid = person.discord_id if person else UNATTRIBUTED
        turn_id = self.turns.current_turn_id(pid) if person else None
        self.emit(
            Transcript(
                discord_id=pid,
                name=person.name if person else (cap.speaker or "?"),
                text=cap.text,
                started_at=iso(cap.started_at),
                ended_at=iso(cap.ended_at),
                utterance_id=cap.utterance_id,
                seq=cap.seq,
                final=cap.final,
                turn_id=turn_id,
                confidence=None,
                speaker=None,
            ),
            at=cap.ended_at,
        )

    def on_pcm(self, pcm: bytes, at: float) -> None:
        """A 20 ms frame of the room's mixed audio (48 kHz stereo s16le)."""
        self._pcm_frames += 1
        if rms(pcm) >= self.settings.silence_rms:
            self._pcm_audible += 1
            self._last_voice_at = max(self._last_voice_at, at)
        if self.stream is not None and self.transcript_source() == "stt":
            self.stream.feed(MIX_ID, pcm, at)

    def _on_segments(self, _source: str, segments: list[Segment]) -> None:
        for seg in segments:
            pid = self.attributor.attribute(seg.started_at, seg.ended_at)
            person = self.roster.get(pid)
            utterance_id, seq = self._utterance.get(pid) or (str(uuid.uuid4()), 0)
            frame = Transcript(
                discord_id=pid,
                name=person.name if person else pid,
                text=seg.text,
                started_at=iso(seg.started_at),
                ended_at=iso(seg.ended_at),
                utterance_id=utterance_id,
                seq=seq,
                final=seg.utterance_end,
                turn_id=self.turns.current_turn_id(pid),
                confidence=seg.confidence,
                speaker=seg.speaker,
            )
            self._utterance[pid] = (
                (str(uuid.uuid4()), 0) if seg.utterance_end else (utterance_id, seq + 1)
            )
            self.debug(
                "stt.final",
                discordId=pid,
                utteranceId=utterance_id,
                text=seg.text,
                diarization=seg.speaker,
            )
            self.emit(frame)

    def _keyterms(self) -> list[str]:
        return [p.name for p in self.roster.participants()]

    def _stt_context(self) -> str:
        agenda = self._session_agenda or {}
        return str(agenda.get("purpose") or "")

    # --- brain → ears --------------------------------------------------------------

    def command(self, raw: str | bytes) -> None:
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
            source = PcmSource(channels=frame.channels)
            self._streams[frame.utterance_id] = source
            self.enqueue(
                _Utterance(
                    frame.utterance_id,
                    b"",
                    "brain",
                    frame.priority,
                    frame.text,
                    source,
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
        elif isinstance(frame, Mute | Unmute):
            # Meet lets a host mute others but never unmute them, and the bot is rarely
            # host. Honest answer: `failed`, as ears-discord does without Mute Members.
            self.emit(
                Moderation(
                    action="failed",
                    discord_id=frame.discord_id,
                    error="Google Meet gives a participant no mute/unmute control",
                )
            )

    async def say(self, text: str) -> dict[str, Any]:
        if self.tts is None:
            raise TtsError("TTS is off — SLNG_API_KEY is unset")
        uid = str(uuid.uuid4())
        self.debug("tts.request", utteranceId=uid, text=text, model=self.tts.model)
        result = await self.tts.synthesize(text)
        self.debug(
            "tts.result", utteranceId=uid, latencyMs=result.latency_ms, bytes=len(result.audio)
        )
        self.enqueue(_Utterance(uid, result.audio, "console", text=text))
        return {"utteranceId": uid, "latencyMs": result.latency_ms, "bytes": len(result.audio)}

    # --- playback ------------------------------------------------------------------

    def enqueue(self, item: _Utterance) -> None:
        item.queued_at = self.clock()
        if item.priority:
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
            and self._may_start(item, self.clock())
        ):
            self.debug("speak.preempted", utteranceId=playing.utterance_id)
            self._interrupted = True
            self.player.stop()
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
        if self._playing is not None:
            self._interrupted = True
            self.player.stop()

    def _play_next(self) -> None:
        if self._playing is not None or not self._playback:
            return
        now = self.clock()
        item = self._playback[0]
        if item.quiet_ms is not None:
            if not self._may_start(item, now):
                if self._holding_since is None:
                    self._holding_since = now
                    self.debug("speak.holding", utteranceId=item.utterance_id)
                return
            quiet = (now - self._last_voice_at) * 1000
            self.debug(
                "speak.released",
                utteranceId=item.utterance_id,
                waitedMs=int((now - item.queued_at) * 1000),
                pause=quiet >= item.quiet_ms,
            )
        self._holding_since = None
        self._playback.popleft()
        if self.channel_id is None:
            self.emit(Spoken(utterance_id=item.utterance_id, error="not in a call"))
            self._play_next()
            return
        item.started_at = now
        self._self_indicator_on_at = None
        played = (
            self.player.play_source(item.stream, self._on_played)
            if item.stream is not None
            else self.player.play(item.audio, self._on_played)
        )
        if not played:
            self.emit(Spoken(utterance_id=item.utterance_id, error="player busy"))
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
        if item.quiet_ms is None:
            return True
        if (now - self._last_voice_at) * 1000 >= item.quiet_ms:
            return True
        return item.max_wait_ms is not None and (now - item.queued_at) * 1000 >= item.max_wait_ms

    def _on_played(self, error: Exception | None) -> None:
        item, self._playing = self._playing, None
        interrupted, self._interrupted = self._interrupted, False
        if item is not None:
            err = str(error) if error else self._egress_verdict(item)
            if err:
                logger.warning("speak.failed", utterance_id=item.utterance_id, error=err)
            self.emit(Spoken(utterance_id=item.utterance_id, interrupted=interrupted, error=err))
        self._play_next()

    def _egress_verdict(self, item: _Utterance) -> str | None:
        """Did the call hear us? Meet lights the bot's own tile indicator from the mic it
        captures, so an indicator that never lit while we played a long enough line
        means the audio did not get into the call. Only judged when the indicator on the
        self tile is known to exist (else the DOM, not the audio, is what is broken)."""
        played_s = self.clock() - item.started_at
        if not self.verify_egress or not self._self_indicator_seen:
            return None
        if played_s < EGRESS_VERIFY_MIN_S or self._interrupted:
            return None
        if (
            self._self_indicator_on_at is not None
            and self._self_indicator_on_at >= item.started_at - 0.5
        ):
            return None
        self.debug("egress.unheard", utteranceId=item.utterance_id, playedS=round(played_s, 2))
        return "egress unheard: Meet's own tile never showed audio while playing (mic sink not attached, or muted)"

    # --- the brain's store ---------------------------------------------------------

    async def add_memory(self, body: dict[str, Any]) -> dict[str, Any]:
        memory = await self.store.add_memory(body)
        self.debug("memory.added", memory=memory)
        return memory

    def record_intervention(self, body: dict[str, Any]) -> None:
        self.store.intervention(body)
        self.debug(
            "chair.intervention", intervention={k: v for k, v in body.items() if v is not None}
        )

    def record_llm_call(self, body: dict[str, Any]) -> dict[str, float]:
        totals = self.store.llm_call(body)
        self.debug("chair.llm", agent=body["agent"], model=body["model"], totals=totals)
        return totals

    # --- the surface (browser) ---------------------------------------------------

    async def self_check(self) -> sel.SelfCheckResult | None:
        if self.surface is None or self.channel_id is None:
            return None
        self.self_check_result = await self.surface.self_check()
        return self.self_check_result

    async def present_stage(self) -> bool:
        if self.surface is None:
            return False
        self.stage_presenting = await self.surface.present_stage()
        self.debug("stage.presenting", presenting=self.stage_presenting)
        return self.stage_presenting

    async def browser_pages(self) -> list[dict[str, str]]:
        if self.surface is None:
            return []
        return await self.surface.pages()

    # --- the clock -----------------------------------------------------------------

    def tick(self, now: float) -> None:
        """One clock beat: due debounces, turns, caption finals, STT pauses, held lines."""
        self._apply(self.debounce.tick(now))
        for frame in self.turns.tick(now):
            self.emit(frame)
            if isinstance(frame, TurnEnd):
                self.debug("turn.ended", discordId=frame.discord_id, speakingMs=frame.speaking_ms)
        for cap in self.captions.tick(now):
            self._emit_caption(cap)
        if self.stream is not None:
            self.stream.tick(now)
        if self._playing is None and self._playback:
            self._play_next()

    async def run_clock(self) -> None:
        while True:
            await asyncio.sleep(CLOCK_SECONDS)
            now = self.clock()
            self.tick(now)
            if self.surface is not None and now - self._surface_checked_at >= SURFACE_HEALTH_EVERY:
                self._surface_checked_at = now
                await self._surface_health(now)

    async def _surface_health(self, now: float) -> None:
        # The caller already checked; this is a guard, not an assert, because `python -O`
        # strips asserts and the next line would raise AttributeError on None instead.
        if self.surface is None:
            return
        if self.channel_id is None:
            return
        if not await self.surface.is_in_call():
            logger.warning("meet.call_ended")
            self.on_left()
            if self.on_leave is not None:
                await self.on_leave()
            return
        if not await self.surface.observer_alive():
            logger.warning("observer.reinstalling")
            await self.surface.install_observer()
        leave_after = self.settings.meet_leave_when_alone_s
        if leave_after and self._alone_since is not None and now - self._alone_since >= leave_after:
            logger.info("meet.alone_too_long", seconds=leave_after)
            await self.surface.leave()
            self.on_left()
            if self.on_leave is not None:
                await self.on_leave()

    def _spawn(self, coro: Coroutine[Any, Any, Any]) -> None:
        task = asyncio.get_running_loop().create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def shutdown(self) -> None:
        self._close_open_speech()
        if self.stream is not None:
            await self.stream.close()
        if self._tasks:
            await asyncio.wait(self._tasks, timeout=SHUTDOWN_TIMEOUT_SECONDS)
        self.end_session()
        self.frame_log.close()
        await self.http.aclose()
