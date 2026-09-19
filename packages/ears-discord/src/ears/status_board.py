"""The meeting's status as one Discord message, edited in place as the meeting moves.

Reads the brain's view (the same `/state` the console's *What Karen understands* panel
shows), renders it as an embed, and keeps one message per session up to date. Each server
chooses in the console whether it wants the message and where: the meeting voice channel's
own text chat (the default) or a text channel. The notes come from the brain's `digest`:
deduplicated there, by a model call that runs only when the notes change.

`render` is pure; `StatusBoard` only fetches, compares and hands embeds to `voice.py`,
which stays the only module that imports discord.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

from .logging import get_logger
from .settings import Settings

logger = get_logger(__name__)

# Discord limits: 1024 characters per field value, 6000 per embed, 4096 per description.
FIELD_LIMIT = 1000
BAR_CELLS = 10

COLORS = {
    "idle": 0x95A5A6,
    "gathering": 0xF1C40F,
    "active": 0x2ECC71,
    "overrun": 0xE74C3C,
    "finished": 0x5865F2,
}


@dataclass(frozen=True)
class StatusConfig:
    """One server's choice, set in the console. `channel_id` None: the voice channel's chat."""

    enabled: bool = True
    channel_id: str | None = None

    def view(self) -> dict[str, Any]:
        return {"enabled": self.enabled, "channelId": self.channel_id}


class StatusPoster(Protocol):
    @property
    def guild_id(self) -> str | None: ...
    @property
    def channel_id(self) -> str | None: ...
    async def send_embed(self, channel_id: str, embed: dict[str, Any]) -> tuple[str, str]: ...
    async def edit_embed(self, channel_id: str, message_id: str, embed: dict[str, Any]) -> None: ...


# --- rendering ------------------------------------------------------------------------------


def render(state: dict[str, Any], now: float | None = None) -> dict[str, Any]:
    """The brain's view as a Discord embed (plain dict, `discord.Embed.from_dict` shape)."""
    phase = state.get("phase") or "idle"
    topic = state.get("topic")
    overrun = bool(
        phase == "active"
        and topic
        and topic.get("budgetSeconds")
        and topic.get("elapsedSeconds", 0) > topic["budgetSeconds"]
    )
    title = state.get("title") or state.get("purpose") or "Meeting"
    chair = (state.get("persona") or {}).get("displayName") or state.get("chairName") or "Karen"

    lines = [_status_line(state, phase)]
    if state.get("purpose") and state.get("purpose") != title:
        lines.append(f"*{_clip(state['purpose'], 200)}*")

    fields: list[dict[str, Any]] = []
    agenda = _agenda(state, phase)
    if agenda:
        fields.append({"name": "🗂️ Agenda", "value": agenda, "inline": True})
    floor = _floor(state.get("people") or [])
    if floor:
        fields.append({"name": "🎙️ Talk time", "value": floor, "inline": True})

    notes = _notes(state)
    sections = [
        ("✅ Decisions", notes["decisions"]),
        ("📌 Key facts", notes["facts"]),
        ("❓ Still open", notes["openItems"]),
        ("🅿️ Parking lot", [f"**{p['name']}** — {p['summary']}" for p in notes["parked"]]),
    ]
    for name, items in sections:
        if items:
            fields.append({"name": name, "value": _bullets(items), "inline": False})
    if not any(items for _, items in sections) and phase != "idle":
        fields.append(
            {
                "name": "📝 Notes",
                "value": f"*Nothing captured yet — {chair} is listening.*",
                "inline": False,
            }
        )

    return {
        "title": _clip(title, 250),
        "description": "\n".join(lines),
        "color": COLORS["overrun" if overrun else phase] if phase in COLORS else COLORS["idle"],
        "fields": fields,
        "footer": {"text": f"{chair} · live meeting status"},
        "timestamp": datetime.fromtimestamp(now or time.time(), UTC).isoformat(),
    }


def _status_line(state: dict[str, Any], phase: str) -> str:
    if phase == "gathering":
        missing = state.get("missingAttendees") or []
        if missing:
            return f"⏳ **Waiting to start** — waiting for {_names(missing)}."
        return "⏳ **Ready to start** — say *“Karen, let's start the meeting.”*"
    if phase == "finished" or state.get("agendaFinished"):
        return "🏁 **Agenda complete.**"
    if phase == "active":
        topic = state.get("topic")
        if not topic:
            return "🟢 **In progress**"
        total = len(state.get("topics") or []) or 1
        elapsed = int(topic.get("elapsedSeconds") or 0)
        budget = int(topic.get("budgetSeconds") or 0)
        head = f"🟢 **In progress** · topic {topic.get('index', 0) + 1} of {total}"
        now_on = f"**{_clip(topic.get('title') or '', 120)}**"
        if not budget:
            return f"{head}\n{now_on} · {_clock(elapsed)}"
        clock = f"{_clock(elapsed)} / {_clock(budget)}"
        if elapsed > budget:
            return f"🔴 **Over time** · topic {topic.get('index', 0) + 1} of {total}\n{now_on}\n`{_bar(1)}` {clock} · **+{_clock(elapsed - budget)}**"
        return f"{head}\n{now_on}\n`{_bar(elapsed / budget)}` {clock}"
    return "💤 **No meeting running.**"


def _agenda(state: dict[str, Any], phase: str) -> str:
    topics = state.get("topics") or []
    current = (state.get("topic") or {}).get("index")
    rows = []
    for i, t in enumerate(topics):
        budget = f" · {_minutes(t['budgetSeconds'])}" if t.get("budgetSeconds") else ""
        name = _clip(t.get("title") or "", 60)
        if t.get("done") or phase == "finished":
            rows.append(f"✅ ~~{name}~~")
        elif phase == "active" and i == current:
            rows.append(f"▶️ **{name}**{budget}")
        else:
            rows.append(f"▫️ {name}{budget}")
    return _fit(rows)


def _floor(people: list[dict[str, Any]]) -> str:
    total = sum(p.get("totalSeconds") or 0 for p in people)
    if total <= 0:
        return ""
    rows = []
    for p in sorted(people, key=lambda p: p.get("totalSeconds") or 0, reverse=True):
        secs = p.get("totalSeconds") or 0
        mark = "🔇" if p.get("muted") else "🗣️" if p.get("speaking") else "▫️"
        rows.append(
            f"{mark} **{_clip(p.get('name') or '?', 24)}** {round(100 * secs / total)}% · {_clock(secs)}"
        )
    return _fit(rows)


def _notes(state: dict[str, Any]) -> dict[str, list[Any]]:
    digest = state.get("digest")
    if isinstance(digest, dict):
        return {k: list(digest.get(k) or []) for k in ("facts", "decisions", "openItems", "parked")}
    # A brain without the digest: the raw notes, as the console shows them.
    u = state.get("understanding") or {}
    return {
        "facts": list(u.get("facts") or []),
        "decisions": list(u.get("decisions") or []),
        "openItems": list(u.get("openItems") or []),
        "parked": list(u.get("offTopics") or state.get("parked") or []),
    }


def _bullets(items: list[str]) -> str:
    """Newest last; when the field is full, the oldest give way to an '…N earlier' line."""
    rows = [f"• {_clip(str(x), 200)}" for x in items]
    kept: list[str] = []
    size = 0
    for row in reversed(rows):
        if size + len(row) + 1 > FIELD_LIMIT - 20:
            break
        kept.insert(0, row)
        size += len(row) + 1
    hidden = len(rows) - len(kept)
    return "\n".join(([f"*…{hidden} earlier*"] if hidden else []) + kept)


def _fit(rows: list[str]) -> str:
    out: list[str] = []
    size = 0
    for i, row in enumerate(rows):
        if size + len(row) + 1 > FIELD_LIMIT - 20:
            out.append(f"*…and {len(rows) - i} more*")
            break
        out.append(row)
        size += len(row) + 1
    return "\n".join(out)


def _bar(fraction: float) -> str:
    filled = max(0, min(BAR_CELLS, round(fraction * BAR_CELLS)))
    return "▰" * filled + "▱" * (BAR_CELLS - filled)


def _clock(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60}:{s % 60:02d}"


def _minutes(seconds: float) -> str:
    m = seconds / 60
    return f"{m:.0f} min" if m >= 1 else f"{int(seconds)} s"


def _names(names: list[str]) -> str:
    names = [str(n) for n in names]
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def _clip(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


# --- the loop ---------------------------------------------------------------------------------


class StatusBoard:
    """One message per brain session, edited only when what it shows has changed."""

    def __init__(
        self,
        settings: Settings,
        http: httpx.AsyncClient,
        poster: StatusPoster,
        config: Callable[[str], StatusConfig] = lambda _: StatusConfig(),
        debug: Any = None,
    ) -> None:
        self.settings = settings
        self.http = http
        self.poster = poster
        self.config = config
        self.debug = debug or (lambda kind, **data: None)
        self.session_id: str | None = None
        self.guild_id: str | None = None
        self.channel_id: str | None = None
        self.message_id: str | None = None
        self._shown: str | None = None
        self._last_error: str | None = None

    async def run(self) -> None:
        while True:
            try:
                await self.update()
                self._last_error = None
            except Exception as exc:  # noqa: BLE001 - a status message never takes ears down
                if str(exc) != self._last_error:  # log each new failure once, not every tick
                    logger.warning("status.failed", error=str(exc))
                    self._last_error = str(exc)
            await asyncio.sleep(self.settings.discord_status_interval_seconds)

    async def update(self) -> None:
        state = await self._fetch()
        if state is None or not isinstance(session := state.get("sessionId"), str):
            return
        # Between calls the bot may be out of voice: the server of the message it already has.
        guild = self.poster.guild_id or self.guild_id
        if guild is None:
            return
        config = self.config(guild)
        if not config.enabled:
            return
        target = config.channel_id or self.poster.channel_id
        embed = render(state)
        shown = json.dumps({k: v for k, v in embed.items() if k != "timestamp"}, sort_keys=True)
        current = (
            session == self.session_id
            and self.message_id is not None
            and target in (None, self.channel_id)
        )
        if current and self.message_id is not None:
            if shown == self._shown:
                return
            try:
                await self.poster.edit_embed(self.channel_id or "", self.message_id, embed)
                self._shown = shown
                return
            except LookupError:
                logger.info("status.message_gone", message_id=self.message_id)  # deleted: post anew
        if state.get("phase") == "idle":
            return  # a session with no agenda: nothing worth a message yet
        if target is None:
            return  # not in voice and no text channel chosen: nowhere to post
        message_id, url = await self.poster.send_embed(target, embed)
        self.session_id, self.guild_id = session, guild
        self.channel_id, self.message_id, self._shown = target, message_id, shown
        logger.info("status.posted", session_id=session, url=url)
        self.debug("status.posted", sessionId=session, url=url)

    async def _fetch(self) -> dict[str, Any] | None:
        try:
            response = await self.http.get(self.settings.brain_state_url, timeout=2.0)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError):
            return None  # brain down or restarting: keep the last message as it was
        return data if isinstance(data, dict) else None
