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
from collections import Counter
from typing import Any, Protocol

import discord
from discord import player as _player
from discord.channel import VocalGuildChannel
from discord.enums import SpeakingState
from discord.sinks import Sink
from discord.voice.enums import OpCodes
from discord.voice.receive import reader as _reader

from .frames import Participant
from .logging import get_logger
from .settings import Settings

logger = get_logger(__name__)

# py-cord warns on every start_recording that receive is broken under DAVE. The
# pinned PR branch is the fix; the warning text predates it.
warnings.filterwarnings(
    "ignore", message="Voice reception is currently broken", category=RuntimeWarning
)


# --- receive hardening -------------------------------------------------------------
# The pinned py-cord decodes whatever it holds when the DAVE session is not ready yet
# (right after joining, and on every key rotation when someone joins or leaves): the
# payload is still end-to-end encrypted, and Opus turns ciphertext into noise that STT
# then transcribes as nonsense. DAVE frames end in the 0xFAFA magic marker, so drop
# those while the session is not ready, and let genuinely unencrypted passthrough
# audio through. Every packet is counted by outcome for the console.

DAVE_MAGIC = b"\xfa\xfa"
RECEIVE_STATS: Counter[str] = Counter()
_original_decrypt = _reader.PacketDecryptor.decrypt_rtp


def _decrypt_rtp(self: Any, packet: Any) -> bytes:
    state = self.client._connection
    dave = state.dave_session
    if dave is not None and not dave.ready:
        raw = self._decryptor_rtp(packet)
        if raw.endswith(DAVE_MAGIC):
            RECEIVE_STATS["dropped_dave_not_ready"] += 1
            packet.decrypted_data = b""
            return b""
        RECEIVE_STATS["passthrough"] += 1
        packet.decrypted_data = raw
        return raw
    known = state.ssrc_user_map.get(packet.ssrc) is not None
    data = _original_decrypt(self, packet)
    if data:
        RECEIVE_STATS["ok"] += 1
    else:
        RECEIVE_STATS["dropped_dave_failed" if known else "dropped_unknown_ssrc"] += 1
    return data


_reader.PacketDecryptor.decrypt_rtp = _decrypt_rtp  # type: ignore[method-assign]


# --- priority speaker -----------------------------------------------------------------
# Discord ducks everyone else while a priority speaker talks. The flag rides on the
# voice gateway's SPEAKING op (voice=1 | priority=4), which py-cord's player always
# sends as plain `voice`; `SpeakingState` is an Enum, so the flags cannot be OR-ed
# through it. While a client is marked `_gavel_priority`, send the raw bits instead.
# Needs the Priority Speaker permission, silently ignored by Discord without it.

PRIORITY_SPEAKING = int(SpeakingState.voice) | int(SpeakingState.priority)
_original_speak = _player.AudioPlayer._speak


def _speak(self: Any, speaking: SpeakingState) -> None:
    client = self.client
    if speaking is SpeakingState.voice and getattr(client, "_gavel_priority", False):
        payload = {"op": int(OpCodes.speaking), "d": {"speaking": PRIORITY_SPEAKING, "delay": 0}}
        try:
            asyncio.run_coroutine_threadsafe(client.ws.send_as_json(payload), client.client.loop)
        except Exception as exc:  # noqa: BLE001 - never break playback over the flag
            logger.warning("voice.priority_failed", error=str(exc))
        return
    _original_speak(self, speaking)


_player.AudioPlayer._speak = _speak  # type: ignore[method-assign]


def take_receive_stats() -> dict[str, int]:
    """Counts since the last call. Written from py-cord's socket thread; read on the loop."""
    snapshot = dict(RECEIVE_STATS)
    RECEIVE_STATS.subtract(snapshot)
    return {k: v for k, v in snapshot.items() if v}


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


def _humans(channel: VocalGuildChannel, names: dict[str, str] | None = None) -> list[Participant]:
    names = names or {}
    return [
        Participant(discord_id=str(m.id), name=names.get(str(m.id), m.display_name))
        for m in channel.members
        if not m.bot
    ]


def _can_post(channel: Any) -> bool:
    """Send Messages + Embed Links there: what the status message needs."""
    me = channel.guild.me
    if me is None:
        return False
    perms = channel.permissions_for(me)
    return bool(perms.view_channel and perms.send_messages and perms.embed_links)


class Voice:
    def __init__(
        self,
        settings: Settings,
        events: VoiceEvents,
        selected_channels: dict[str, str] | None = None,
    ) -> None:
        self._settings = settings
        self._events = events
        self._loop: asyncio.AbstractEventLoop | None = None
        intents = discord.Intents.none()
        intents.guilds = True
        intents.voice_states = True
        self.client = discord.Client(intents=intents)
        self._vc: discord.VoiceClient | None = None
        self._channel: VocalGuildChannel | None = None
        self._guild_id: int | None = None
        self._joining = False
        # Current server profile names, read over REST. Discord only pushes nickname changes
        # with the privileged members intent, which this bot does not ask for, so a cached
        # Member keeps whatever name it had when it first appeared in the voice channel.
        self._names: dict[str, str] = {}
        self._selected_channels = dict(selected_channels or {})
        # Keep the old env pair as a one-time seed while deployments move to the console.
        if settings.discord_guild_id is not None and settings.discord_voice_channel_id is not None:
            self._selected_channels.setdefault(
                str(settings.discord_guild_id), str(settings.discord_voice_channel_id)
            )
        self._leave_task: asyncio.Task[None] | None = None
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
        self._cancel_leave()
        if self._vc is not None:
            await self._vc.disconnect(force=True)
        await self.client.close()

    @property
    def channel_id(self) -> str | None:
        return str(self._channel.id) if self._channel else None

    def participants(self) -> list[Participant]:
        return _humans(self._channel, self._names) if self._channel else []

    async def refresh_names(self) -> list[Participant]:
        """Drop the cached names and re-read everyone's server profile over REST.

        The gateway never tells this bot about a nickname change (that needs the privileged
        members intent), so a name that changed mid-call stays stale until it is fetched.
        Called when the bot joins, when a session starts, and from the console button.
        """
        self._names = {}
        channel = self._channel
        if channel is None:
            return []
        guild = channel.guild
        for member in channel.members:
            if member.bot:
                continue
            try:
                fresh = await guild.fetch_member(member.id)
            except discord.HTTPException as exc:
                logger.warning("voice.name_fetch_failed", discord_id=str(member.id), error=str(exc))
                continue
            if fresh.display_name != member.display_name:
                logger.info(
                    "voice.name_changed",
                    discord_id=str(member.id),
                    was=member.display_name,
                    now=fresh.display_name,
                )
            self._names[str(member.id)] = fresh.display_name
        return _humans(channel, self._names)

    async def _refresh_one(self, member: discord.Member) -> None:
        """Re-read one member's server profile — they just walked into the channel."""
        self._names.pop(str(member.id), None)
        try:
            fresh = await member.guild.fetch_member(member.id)
        except discord.HTTPException as exc:
            logger.warning("voice.name_fetch_failed", discord_id=str(member.id), error=str(exc))
            return
        self._names[str(member.id)] = fresh.display_name

    def discord_servers(self) -> dict[str, Any]:
        """Console-safe view of every server and voice channel visible to the bot."""
        return {
            "connected": self.client.is_ready(),
            "servers": [
                {
                    "id": str(guild.id),
                    "name": guild.name,
                    "selectedChannelId": self._selected_channels.get(str(guild.id)),
                    "connectedChannelId": (
                        str(self._channel.id)
                        if self._channel is not None and self._channel.guild.id == guild.id
                        else None
                    ),
                    "channels": [
                        {
                            "id": str(channel.id),
                            "name": channel.name,
                            "participants": len(_humans(channel)),
                            "canPost": _can_post(channel),
                        }
                        for channel in guild.voice_channels
                    ],
                    # Where the status message may go instead of the voice channel's chat.
                    "textChannels": [
                        {"id": str(channel.id), "name": channel.name, "canPost": _can_post(channel)}
                        for channel in guild.text_channels
                    ],
                }
                for guild in self.client.guilds
            ],
        }

    async def configure_channel(self, guild_id: str, channel_id: str | None) -> None:
        """Select the meeting channel for a server and apply it immediately."""
        guild = self.client.get_guild(int(guild_id))
        if guild is None:
            raise ValueError("Discord server is not available to this bot")
        channel: VocalGuildChannel | None = None
        if channel_id is not None:
            candidate = guild.get_channel(int(channel_id))
            if not isinstance(candidate, VocalGuildChannel):
                raise ValueError("voice channel is not available on this Discord server")
            channel = candidate

        old = self._selected_channels.get(guild_id)
        if channel_id is None:
            self._selected_channels.pop(guild_id, None)
        else:
            self._selected_channels[guild_id] = channel_id
        logger.info("voice.configured", guild=guild.name, channel=channel.name if channel else None)

        if self._channel is not None and self._channel.guild.id == guild.id and old != channel_id:
            await self._disconnect("channel configuration changed")
        if self._channel is None and channel is not None and _humans(channel):
            await self._join(channel)

    # --- the status message (status_board.py) -----------------------------------------

    @property
    def guild_id(self) -> str | None:
        return str(self._channel.guild.id) if self._channel else None

    async def send_embed(self, channel_id: str, embed: dict[str, Any]) -> tuple[str, str]:
        message = await self._messageable(channel_id).send(embed=discord.Embed.from_dict(embed))
        return str(message.id), message.jump_url

    async def edit_embed(self, channel_id: str, message_id: str, embed: dict[str, Any]) -> None:
        message = self._messageable(channel_id).get_partial_message(int(message_id))
        try:
            await message.edit(embed=discord.Embed.from_dict(embed))
        except discord.NotFound as exc:
            raise LookupError("status message no longer exists") from exc

    def _messageable(self, channel_id: str) -> Any:
        channel = self.client.get_channel(int(channel_id))
        if channel is None or not hasattr(channel, "get_partial_message"):
            raise LookupError(f"channel {channel_id} is not a text chat this bot can see")
        return channel

    def play(self, audio: bytes, done: Any, priority: bool = False) -> bool:
        """Play encoded audio (wav/mp3/ogg — anything FFmpeg reads). `done(error)` runs on the loop.

        `priority` plays as Discord's priority speaker, ducking everyone else.
        """
        if self._vc is None or not self._vc.is_connected():
            return False
        return self.play_source(
            discord.FFmpegPCMAudio(io.BytesIO(audio), pipe=True), done, priority
        )

    def play_source(self, source: discord.AudioSource, done: Any, priority: bool = False) -> bool:
        """Play any audio source — a finished file or a line still streaming in."""
        vc = self._vc
        if vc is None or not vc.is_connected():
            return False
        vc._gavel_priority = priority  # type: ignore[attr-defined]  # read by _speak above

        def after(error: Exception | None) -> None:
            self._call(done, error)

        # py-cord calls `after(error)`; its type stub claims `after(sink)`.
        vc.play(source, after=after)  # type: ignore[arg-type]
        return True

    def receive_stats(self) -> dict[str, int]:
        return take_receive_stats()

    def stop_playback(self) -> None:
        if self._vc is not None and self._vc.is_playing():
            self._vc.stop()

    async def set_mute(self, discord_id: str, muted: bool, reason: str | None = None) -> None:
        """Server-mute or unmute a member. Needs Mute Members; raises on failure.

        A server mute is guild-wide and outlives the call, so the lookup goes through the
        guild, not the channel: an unmute still works after the bot has left.
        """
        guild = self.client.get_guild(self._guild_id) if self._guild_id else None
        if guild is None:
            raise RuntimeError("not in a guild yet")
        member = guild.get_member(int(discord_id)) or await guild.fetch_member(int(discord_id))
        if muted and (member.voice is None or member.voice.channel is None):
            raise RuntimeError("not in a voice channel")  # Discord rejects muting them
        await member.edit(mute=muted, reason=reason or "gavel chair")

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
                logger.info("voice.waiting", reason="no humans in a configured voice channel")

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
                self._cancel_leave()
                self._vc, self._channel = None, None
                self._events.on_left()
            elif (
                after.channel is not None
                and self._channel is not None
                and after.channel.id != self._channel.id
            ):
                # Someone dragged the bot to another channel: follow it.
                self._channel = after.channel
                people = await self.refresh_names()
                self._events.on_joined(str(after.channel.guild.id), str(after.channel.id), people)
                if people:
                    self._cancel_leave()
                else:
                    self._schedule_leave()
            return
        if member.bot:
            return
        if self._channel is None:
            wanted = self._selected_channels.get(str(member.guild.id))
            if after.channel is not None and wanted == str(after.channel.id):
                await self._join(after.channel)
            return
        ours = self._channel.id
        if (before.channel and before.channel.id == ours) or (
            after.channel and after.channel.id == ours
        ):
            if after.channel is not None and after.channel.id == ours:
                await self._refresh_one(member)
            people = _humans(self._channel, self._names)
            self._events.on_participants(people)
            if people:
                self._cancel_leave()
            else:
                self._schedule_leave()

    def _pick_channel(self) -> VocalGuildChannel | None:
        for guild in self.client.guilds:
            wanted = self._selected_channels.get(str(guild.id))
            if wanted is None:
                continue
            channel = guild.get_channel(int(wanted))
            if isinstance(channel, VocalGuildChannel) and _humans(channel):
                return channel
        return None

    async def _join(self, channel: VocalGuildChannel) -> None:
        if self._joining or self._vc is not None:
            return
        self._joining = True
        try:
            logger.info("voice.joining", guild=channel.guild.name, channel=channel.name)
            vc = await channel.connect(reconnect=True)
            self._vc, self._channel = vc, channel
            self._guild_id = channel.guild.id
            self._start_listening()
            people = await self.refresh_names()
            self._events.on_joined(str(channel.guild.id), str(channel.id), people)
            if not people:
                self._schedule_leave()
        except Exception as exc:
            logger.exception("voice.join_failed", error=str(exc))
        finally:
            self._joining = False

    def _schedule_leave(self) -> None:
        if self._leave_task is None and self._loop is not None:
            self._leave_task = self._loop.create_task(self._leave_when_empty())

    def _cancel_leave(self) -> None:
        if self._leave_task is not None:
            if self._leave_task is not asyncio.current_task():
                self._leave_task.cancel()
            self._leave_task = None

    async def _leave_when_empty(self) -> None:
        try:
            await asyncio.sleep(self._settings.discord_leave_grace_seconds)
            if self._channel is not None and not _humans(self._channel):
                await self._disconnect("channel empty")
        except asyncio.CancelledError:
            raise
        finally:
            self._leave_task = None

    async def _disconnect(self, reason: str) -> None:
        vc, channel = self._vc, self._channel
        if vc is None and channel is None:
            return
        self._vc, self._channel = None, None
        self._cancel_leave()
        logger.info("voice.leaving", channel=channel.name if channel else None, reason=reason)
        try:
            if vc is not None:
                await vc.disconnect(force=True)
        finally:
            self._events.on_left()
        next_channel = self._pick_channel()
        if next_channel is not None:
            await self._join(next_channel)

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
