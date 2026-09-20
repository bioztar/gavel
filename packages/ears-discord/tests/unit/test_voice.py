"""Discord voice lifecycle decisions without connecting to Discord."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import discord

from ears.voice import Voice


class FakeVoiceClient:
    def __init__(self) -> None:
        self.disconnected = False

    async def disconnect(self, *, force: bool) -> None:
        assert force is True
        self.disconnected = True


class FakeEvents:
    def __init__(self) -> None:
        self.left = 0

    def on_left(self) -> None:
        self.left += 1


def empty_voice(grace: float) -> tuple[Voice, FakeVoiceClient, FakeEvents]:
    voice = Voice.__new__(Voice)
    client = FakeVoiceClient()
    events = FakeEvents()
    voice._settings = SimpleNamespace(discord_leave_grace_seconds=grace)  # type: ignore[assignment]
    voice._events = events  # type: ignore[assignment]
    voice._loop = asyncio.get_running_loop()
    voice._vc = client  # type: ignore[assignment]
    voice._channel = SimpleNamespace(name="Meeting", members=[])  # type: ignore[assignment]
    voice._leave_task = None
    voice._selected_channels = {}
    voice._joining = False
    voice.client = SimpleNamespace(guilds=[])  # type: ignore[assignment]
    return voice, client, events


async def test_moderator_leaves_after_empty_channel_grace() -> None:
    voice, client, events = empty_voice(0.01)

    voice._schedule_leave()
    await asyncio.sleep(0.03)

    assert client.disconnected is True
    assert events.left == 1
    assert voice._channel is None


async def test_pending_leave_can_be_cancelled_when_someone_returns() -> None:
    voice, client, events = empty_voice(0.02)

    voice._schedule_leave()
    await asyncio.sleep(0)
    voice._cancel_leave()
    await asyncio.sleep(0.03)

    assert client.disconnected is False
    assert events.left == 0


class FakeMember:
    def __init__(self, member_id: int, name: str, guild: FakeGuild) -> None:
        self.id = member_id
        self.display_name = name
        self.bot = False
        self.guild = guild


class FakeGuild:
    """Discord only pushes renames with the members intent, so the cached member keeps
    the name it was first seen with; `fetch_member` is the current server profile."""

    def __init__(self, current: dict[int, str]) -> None:
        self.current = current
        self.fetched: list[int] = []

    async def fetch_member(self, member_id: int) -> FakeMember:
        self.fetched.append(member_id)
        return FakeMember(member_id, self.current[member_id], self)


def renamed_voice() -> tuple[Voice, FakeGuild]:
    voice = Voice.__new__(Voice)
    guild = FakeGuild({7: "New Name"})
    stale = FakeMember(7, "Old Name", guild)
    voice._names = {}
    voice._channel = SimpleNamespace(members=[stale], guild=guild)  # type: ignore[assignment]
    return voice, guild


async def test_refresh_names_reads_the_current_server_profile() -> None:
    voice, guild = renamed_voice()

    people = await voice.refresh_names()

    assert [(p.discord_id, p.name) for p in people] == [("7", "New Name")]
    assert voice.participants()[0].name == "New Name"
    assert guild.fetched == [7]


async def test_refresh_names_keeps_the_cached_name_when_discord_fails() -> None:
    voice, guild = renamed_voice()

    async def boom(member_id: int) -> FakeMember:
        raise discord.HTTPException(SimpleNamespace(status=500, reason="nope"), "nope")

    guild.fetch_member = boom  # type: ignore[assignment]
    people = await voice.refresh_names()

    assert [p.name for p in people] == ["Old Name"]
