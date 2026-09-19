"""The Discord status message: the brain's view rendered, one message per session, edited on change."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from ears.settings import Settings
from ears.status_board import FIELD_LIMIT, StatusBoard, render

ACTIVE: dict[str, Any] = {
    "sessionId": "s1",
    "title": "Launch sync",
    "purpose": "Agree the launch date",
    "chairName": "Karen",
    "phase": "active",
    "missingAttendees": [],
    "agendaFinished": False,
    "topic": {"index": 1, "title": "The date", "budgetSeconds": 120, "elapsedSeconds": 60},
    "topics": [
        {"title": "Status", "budgetSeconds": 90, "done": True},
        {"title": "The date", "budgetSeconds": 120, "done": False},
        {"title": "Hiring", "budgetSeconds": 300, "done": False},
    ],
    "people": [
        {"name": "Ana", "totalSeconds": 30, "speaking": False, "muted": False},
        {"name": "Vitaly", "totalSeconds": 90, "speaking": True, "muted": False},
    ],
    "digest": {
        "source": "llm",
        "facts": ["QA needs two weeks."],
        "decisions": ["Launch on 3 October."],
        "openItems": [],
        "parked": [{"name": "Vitaly", "summary": "office move"}],
    },
}


def fields(embed: dict[str, Any]) -> dict[str, str]:
    return {f["name"]: f["value"] for f in embed["fields"]}


def test_render_active_meeting() -> None:
    embed = render(ACTIVE, now=0)
    assert embed["title"] == "Launch sync"
    assert "topic 2 of 3" in embed["description"]
    assert "**The date**" in embed["description"] and "1:00 / 2:00" in embed["description"]
    assert "*Agree the launch date*" in embed["description"]
    f = fields(embed)
    assert f["🗂️ Agenda"].splitlines() == [
        "✅ ~~Status~~",
        "▶️ **The date** · 2 min",
        "▫️ Hiring · 5 min",
    ]
    # Loudest first, with who holds the floor now.
    assert f["🎙️ Talk time"].splitlines() == ["🗣️ **Vitaly** 75% · 1:30", "▫️ **Ana** 25% · 0:30"]
    assert f["✅ Decisions"] == "• Launch on 3 October."
    assert f["🅿️ Parking lot"] == "• **Vitaly** — office move"
    assert "❓ Still open" not in f  # empty sections are left out


def test_render_overrun_lobby_and_raw_notes() -> None:
    over = render({**ACTIVE, "topic": {**ACTIVE["topic"], "elapsedSeconds": 150}})
    assert over["color"] == 0xE74C3C and "**+0:30**" in over["description"]

    lobby = render({"phase": "gathering", "title": "Sync", "missingAttendees": ["Ana", "Marc"]})
    assert "waiting for Ana and Marc" in lobby["description"]
    assert "Nothing captured yet" in fields(lobby)["📝 Notes"]

    # An older brain without `digest`: the raw notes.
    raw = render(
        {
            "phase": "active",
            "understanding": {"facts": ["A"], "offTopics": [{"name": "Ana", "summary": "b"}]},
        }
    )
    assert fields(raw)["📌 Key facts"] == "• A"


def test_long_lists_keep_the_newest_within_discord_limits() -> None:
    facts = [f"Fact number {i} with a bit of padding to take up room." for i in range(60)]
    embed = render({**ACTIVE, "digest": {**ACTIVE["digest"], "facts": facts}})
    value = fields(embed)["📌 Key facts"]
    assert len(value) <= FIELD_LIMIT
    assert value.startswith("*…") and value.endswith(
        "Fact number 59 with a bit of padding to take up room."
    )


class FakePoster:
    def __init__(self) -> None:
        self.status_channel_id: str | None = "chan"
        self.sent: list[dict[str, Any]] = []
        self.edits: list[dict[str, Any]] = []
        self.gone = False

    async def send_embed(self, channel_id: str, embed: dict[str, Any]) -> tuple[str, str]:
        self.sent.append(embed)
        return f"m{len(self.sent)}", "https://discord.com/channels/g/chan/m"

    async def edit_embed(self, channel_id: str, message_id: str, embed: dict[str, Any]) -> None:
        if self.gone:
            raise LookupError("gone")
        self.edits.append(embed)


def test_board_posts_once_per_session_and_edits_only_on_change() -> None:
    state: dict[str, Any] = dict(ACTIVE)

    def brain(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=state)

    async def scenario() -> FakePoster:
        poster = FakePoster()
        async with httpx.AsyncClient(transport=httpx.MockTransport(brain)) as http:
            board = StatusBoard(Settings(_env_file=None), http, poster)  # type: ignore[call-arg]
            await board.update()
            await board.update()  # unchanged: no edit
            state["topic"] = {**ACTIVE["topic"], "elapsedSeconds": 65}
            await board.update()
            poster.gone = True  # someone deleted the message: post it again
            state["topic"] = {**ACTIVE["topic"], "elapsedSeconds": 70}
            await board.update()
            poster.gone = False
            state["sessionId"] = "s2"  # a new session gets its own message
            await board.update()
            assert board.message_id == "m3"
        return poster

    poster = asyncio.run(scenario())
    assert len(poster.sent) == 3
    assert len(poster.edits) == 1


def test_board_waits_for_a_brain_and_a_channel() -> None:
    async def scenario() -> FakePoster:
        poster = FakePoster()
        poster.status_channel_id = None
        down = httpx.MockTransport(lambda _: httpx.Response(503))
        up = httpx.MockTransport(lambda _: httpx.Response(200, json=ACTIVE))
        for transport in (down, up):
            async with httpx.AsyncClient(transport=transport) as http:
                await StatusBoard(Settings(_env_file=None), http, poster).update()  # type: ignore[call-arg]
        return poster

    assert asyncio.run(scenario()).sent == []
