"""Discord voice lifecycle decisions without connecting to Discord."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

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
