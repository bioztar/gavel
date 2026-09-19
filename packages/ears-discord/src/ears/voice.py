"""Discord voice via py-cord — the only module that imports discord.

Joins a voice channel, reports participants, speaking changes and decoded
per-speaker PCM, and plays audio back. It makes no decisions.

py-cord's receive side runs on its own threads (packet router, speaking timer);
every callback into the app is marshalled onto the event loop, so `VoiceEvents`
implementations never see a foreign thread.
"""

from __future__ import annotations

import asyncio
import io
import time
import warnings
from typing import Any, Protocol

import discord
from discord.channel import VocalGuildChannel
from discord.sinks import Sink

from .frames import Participant
from .logging import get_logger
from .settings import Settings

logger = get_logger(__name__)

# py-cord warns on every start_recording that receive is broken under DAVE. The
# pinned PR branch is the fix; the warning text predates it.
warnings.filterwarnings(
    "ignore", message="Voice reception is currently broken", category=RuntimeWarning
)


class VoiceEvents(Protocol):
    def on_joined(
        self, guild_id: str, channel_id: str, participants: list[Participant]
    ) -> None: ...
    def on_left(self) -> None: ...
    def on_participants(self, participants: list[Participant]) -> None: ...
    def on_speaking(self, discord_id: str, speaking: bool, at: float) -> None: ...
    def on_pcm(self, discord_id: str, pcm: bytes, at: float) -> None: ...


class _StenoSink(Sink):
    """Forwards decoded PCM and speaking changes instead of storing anything."""

    __sink_listeners__ = [  # noqa: RUF012 - py-cord's own declaration style
        ("on_member_speaking_start", "_speaking_start"),
        ("on_member_speaking_stop", "_speaking_stop"),
    ]

    def __init__(self, voice: Voice) -> None:
        super().__init__()
        self._voice = voice

    # Called on py-cord's packet-router thread.
    def write(self, data: Any, user: Any) -> None:  # type: ignore[override]
        if user is None or getattr(user, "bot", False):
            return
        pcm = getattr(data, "pcm", data)
        if pcm:
            self._voice._emit("on_pcm", str(user.id), bytes(pcm), time.time())

    # Called on py-cord's sink-event thread.
    def _speaking_start(self, member: Any) -> None:
        if not getattr(member, "bot", False):
            self._voice._emit("on_speaking", str(member.id), True, time.time())

    def _speaking_stop(self, member: Any) -> None:
        if not getattr(member, "bot", False):
            self._voice._emit("on_speaking", str(member.id), False, time.time())

    def cleanup(self) -> None:
        self.finished = True


def _humans(channel: VocalGuildChannel) -> list[Participant]:
    return [
        Participant(discord_id=str(m.id), name=m.display_name) for m in channel.members if not m.bot
    ]


class Voice:
    def __init__(self, settings: Settings, events: VoiceEvents) -> None:
        self._settings = settings
        self._events = events
        self._loop: asyncio.AbstractEventLoop | None = None
        intents = discord.Intents.none()
        intents.guilds = True
        intents.voice_states = True
        self.client = discord.Client(intents=intents)
        self._vc: discord.VoiceClient | None = None
        self._channel: VocalGuildChannel | None = None
        self._joining = False
        self._register()

    # --- public -------------------------------------------------------------------

    async def run(self) -> None:
        self._loop = asyncio.get_running_loop()
        if not discord.opus.is_loaded():
            try:
                discord.opus.load_opus(self._settings.opus_lib)
            except OSError as exc:
                raise RuntimeError(
                    f"cannot load libopus from {self._settings.opus_lib} — brew install opus, or set OPUS_LIB"
                ) from exc
        watchdog = self._loop.create_task(self._watchdog())
        try:
            await self.client.start(self._settings.discord_ears_token)
        finally:
            watchdog.cancel()

    async def close(self) -> None:
        if self._vc is not None:
            await self._vc.disconnect(force=True)
        await self.client.close()

    @property
    def channel_id(self) -> str | None:
        return str(self._channel.id) if self._channel else None

    def participants(self) -> list[Participant]:
        return _humans(self._channel) if self._channel else []

    def play(self, audio: bytes, done: Any) -> bool:
        """Play encoded audio (wav/mp3/ogg — anything FFmpeg reads). `done(error)` runs on the loop."""
        vc = self._vc
        if vc is None or not vc.is_connected():
            return False
        source = discord.FFmpegPCMAudio(io.BytesIO(audio), pipe=True)

        def after(error: Exception | None) -> None:
            self._call(done, error)

        # py-cord calls `after(error)`; its type stub claims `after(sink)`.
        vc.play(source, after=after)  # type: ignore[arg-type]
        return True

    def stop_playback(self) -> None:
        if self._vc is not None and self._vc.is_playing():
            self._vc.stop()

    # --- discord events ------------------------------------------------------------

    def _register(self) -> None:
        @self.client.event
        async def on_ready() -> None:
            user = self.client.user
            logger.info(
                "discord.ready", user=str(user), guilds=[g.name for g in self.client.guilds]
            )
            channel = self._pick_channel()
            if channel is not None:
                await self._join(channel)
            else:
                logger.info("voice.waiting", reason="no humans in any voice channel yet")

        @self.client.event
        async def on_guild_join(guild: discord.Guild) -> None:
            logger.info("discord.guild_joined", guild=guild.name)
            channel = self._pick_channel()
            if channel is not None:
                await self._join(channel)

        @self.client.event
        async def on_voice_state_update(
            member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
        ) -> None:
            await self._on_voice_state(member, before, after)

    async def _on_voice_state(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ) -> None:
        me = self.client.user
        if me is not None and member.id == me.id:
            if after.channel is None and self._channel is not None:
                logger.warning("voice.left", channel=self._channel.name)
                self._vc, self._channel = None, None
                self._events.on_left()
            elif (
                after.channel is not None
                and self._channel is not None
                and after.channel.id != self._channel.id
            ):
                # Someone dragged the bot to another channel: follow it.
                self._channel = after.channel
                self._events.on_joined(
                    str(after.channel.guild.id), str(after.channel.id), _humans(after.channel)
                )
            return
        if member.bot:
            return
        if self._channel is None:
            wanted = self._settings.discord_voice_channel_id
            if after.channel is not None and (wanted is None or after.channel.id == wanted):
                await self._join(after.channel)
            return
        ours = self._channel.id
        if (before.channel and before.channel.id == ours) or (
            after.channel and after.channel.id == ours
        ):
            self._events.on_participants(_humans(self._channel))

    def _pick_channel(self) -> VocalGuildChannel | None:
        wanted = self._settings.discord_voice_channel_id
        guilds = self.client.guilds
        if self._settings.discord_guild_id is not None:
            guilds = [g for g in guilds if g.id == self._settings.discord_guild_id]
        for guild in guilds:
            if wanted is not None:
                channel = guild.get_channel(wanted)
                if isinstance(channel, VocalGuildChannel):
                    return channel
                continue
            occupied = [c for c in guild.voice_channels if _humans(c)]
            if occupied:
                return max(occupied, key=lambda c: len(_humans(c)))
        if wanted is not None:
            logger.error("voice.channel_not_found", channel_id=wanted)
        return None

    async def _join(self, channel: VocalGuildChannel) -> None:
        if self._joining or self._vc is not None:
            return
        self._joining = True
        try:
            logger.info("voice.joining", guild=channel.guild.name, channel=channel.name)
            vc = await channel.connect(reconnect=True)
            self._vc, self._channel = vc, channel
            self._start_listening()
            self._events.on_joined(str(channel.guild.id), str(channel.id), _humans(channel))
        except Exception as exc:
            logger.exception("voice.join_failed", error=str(exc))
        finally:
            self._joining = False

    def _start_listening(self) -> None:
        vc = self._vc
        if vc is None or not vc.is_connected() or vc.is_recording():
            return
        # No `after` callback: the pinned py-cord only invokes it when extra args are
        # passed. The watchdog notices a dead receiver instead.
        vc.start_recording(_StenoSink(self))
        logger.info("voice.listening")

    async def _watchdog(self) -> None:
        """Restart receive if it died while we are still in the call."""
        while True:
            await asyncio.sleep(2)
            vc = self._vc
            if vc is not None and vc.is_connected() and not vc.is_recording():
                logger.warning("voice.listening_restarted")
                try:
                    self._start_listening()
                except Exception as exc:
                    logger.exception("voice.listen_failed", error=str(exc))

    # --- thread → loop -----------------------------------------------------------------

    def _emit(self, method: str, *args: Any) -> None:
        self._call(getattr(self._events, method), *args)

    def _call(self, fn: Any, *args: Any) -> None:
        if self._loop is not None and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(fn, *args)
