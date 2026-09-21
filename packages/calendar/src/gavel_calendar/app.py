"""HTTP surface.

    GET  /                  redirects to /board (Traefik routes the whole host here)
    GET  /compose            the brief textarea — see compose.py
    POST /compose/parse      brief → LLM → editable confirm form
    POST /compose/send       confirm → meeting created, handed to ears as the session it
                             is now holding, .ics + email sent best-effort
    POST /invite            upload or paste an .ics → {sessionId, joinUrl}
    GET  /m/{session_id}    the meeting room: the agenda before, Karen's face and
                             her running commentary during, the report after —
                             one link for all three. See room.py
    GET  /m/{session_id}/state  what that page polls: the brain's view of this
                             meeting, or the last one banked for it
    POST /m/{session_id}/join   force-starts the session now
    GET  /board              upcoming ingested meetings, each with its Join button —
                              the demo path from a read-only feed to a running session
    GET  /health

Both the Join button and the scheduler end in `service.start` — see scheduler.py.
The compose routes' form-parsing and HTML live in `compose.py`; the routes stay
here so they share this module's single `store` instance.
"""

from __future__ import annotations

import asyncio
import html
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from . import compose, room, scheduler, service
from .agenda import build_agenda
from .ears_client import EarsClient
from .feed_store import FeedRegistry
from .ics_parser import InvalidInvite, parse_ics
from .settings import get_settings
from .store import InviteRecord, InviteStore

settings = get_settings()
store = InviteStore()
ears = EarsClient(settings.ears_api_url)
feed_registry = FeedRegistry()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Before the scheduler, never after: it starts whatever is `pending()` and
    # already due, so an unrehydrated store would start a second ears session
    # for a meeting this process had already started before a restart.
    await store.attach(settings.async_postgres_dsn)

    tasks = [asyncio.create_task(scheduler.run(store, ears, settings.scheduler_poll_seconds))]
    if settings.ics_feed_urls:
        tasks.append(
            asyncio.create_task(
                scheduler.poll_feeds(
                    store,
                    feed_registry,
                    settings.ics_feed_urls,
                    settings.attendee_map,
                    settings.scheduler_poll_seconds,
                    settings.feed_window,
                )
            )
        )
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await store.close()


app = FastAPI(title="gavel calendar", lifespan=lifespan)


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    # The whole host routes here (Traefik); a judge types the bare domain.
    return RedirectResponse("/board", status_code=307)


@app.get("/health")
async def health() -> dict[str, Any]:
    feeds = []
    for i in range(len(settings.ics_feed_urls)):
        h = feed_registry.health_for(i)
        feeds.append(
            {
                "feed": i,
                "lastSuccess": h.last_success.isoformat() if h.last_success else None,
                "eventCount": h.event_count,
                "lastError": h.last_error,
            }
        )
    return {
        "status": "ok",
        # False means invites live only as long as this process — the store
        # could not reach Postgres at boot. Worth seeing before a demo.
        "durable": store.durable,
        "pending": len(store.pending()),
        "feeds": feeds,
    }


@app.post("/invite")
async def invite(
    file: UploadFile | None = None,
    ics: str | None = Form(None),
) -> dict[str, str]:
    if file is not None:
        raw: bytes | str = await file.read()
    elif ics:
        raw = ics
    else:
        raise HTTPException(422, "provide an .ics file upload or an `ics` form field")

    try:
        parsed = parse_ics(raw)
    except InvalidInvite as exc:
        raise HTTPException(422, str(exc)) from exc

    session_id = uuid.uuid4().hex[:12]
    agenda = build_agenda(parsed, session_id, settings.attendee_map)
    await store.save(
        InviteRecord(
            session_id=session_id,
            title=parsed.title,
            start=parsed.start,
            end=parsed.end,
            agenda=agenda,
            context=parsed.description,
        )
    )
    join_url = f"{settings.calendar_public_url}/m/{session_id}"
    return {"sessionId": session_id, "joinUrl": join_url}


@app.get("/compose", response_class=HTMLResponse)
async def compose_form() -> str:
    return compose.render_brief_form()


@app.post("/compose/parse", response_class=HTMLResponse)
async def compose_parse(
    brief: str = Form(...), attendees: str = Form(""), agenda: str = Form("")
) -> str:
    # Both optional fields default to "" rather than being required. An empty
    # text input posts as `attendees=`, which this Starlette version reports as
    # *missing*, not as an empty string — required, that 422s the one path the
    # host actually uses: dictate the brief, click Continue, name nobody.
    # `agenda` is the same shape, posted back by the gate page when the brief
    # had no agenda in it.
    return await compose.render_confirm_form(brief, attendees, settings, agenda)


@app.post("/compose/send", response_class=HTMLResponse)
async def compose_send(request: Request) -> str:
    form = await request.form()
    return await compose.handle_send(form, store, settings, ears)


@app.get("/board", response_class=HTMLResponse)
async def board() -> str:
    records = sorted(store.pending(), key=lambda r: r.start)
    return _render_board_page(records)


def _mounted_doc(filename: str, what: str) -> str:
    """Serve an HTML file mounted read-only into the image at request time.

    Mounted rather than baked in, so a wording fix before the pitch needs no
    rebuild. A missing file is a 404 and never a 500 — neither document is
    load-bearing for any meeting.
    """
    doc = Path("/app") / filename
    if not doc.is_file():
        raise HTTPException(status_code=404, detail=f"{what} not mounted")
    return doc.read_text(encoding="utf-8")


# Both routes are sync on purpose: FastAPI runs them in a threadpool, so the
# small blocking read never sits on the event loop.
@app.get("/architecture", response_class=HTMLResponse)
def architecture() -> str:
    """The demo deck (docs/architecture.html), on the same host as everything else."""
    return _mounted_doc("architecture.html", "architecture deck")


@app.get("/demo-script", response_class=HTMLResponse)
def demo_script() -> str:
    """The run sheet for the demo (docs/demo-script.html) — readable on a phone on stage."""
    return _mounted_doc("demo-script.html", "demo script")


@app.get("/m/{session_id}", response_class=HTMLResponse)
async def meeting_room(session_id: str) -> str:
    record = store.get(session_id)
    if record is None:
        raise HTTPException(404, "no such invite")
    return room.render_room_page(record, discord_url=settings.discord_meeting_url)


@app.get("/m/{session_id}/state")
async def meeting_state(session_id: str) -> dict[str, Any]:
    record = store.get(session_id)
    if record is None:
        raise HTTPException(404, "no such invite")
    brain = await _brain_state()
    if room.is_live(record, brain) and brain is not None:
        # Bank it: the brain forgets this session the moment the next one starts,
        # and the report has to outlive it.
        await store.bank_state(session_id, brain)
    return room.room_state(record, brain)


async def _brain_state() -> dict[str, Any] | None:
    """The brain's `/state`, or None. A page that cannot reach the brain shows
    the agenda or the banked report — it never shows an error to a room."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(settings.brain_state_url)
        response.raise_for_status()
        state = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    return state if isinstance(state, dict) else None


@app.post("/m/{session_id}/join", response_class=HTMLResponse)
async def join(session_id: str) -> str:
    record = store.get(session_id)
    if record is None:
        raise HTTPException(404, "no such invite")
    try:
        result = await service.start(store, ears, session_id)
    except Exception as exc:  # ears unreachable, meeting rejected, etc.
        logger.exception("join.start_failed session_id=%s", session_id)
        # Recommended by Norma — fixed with GPT-5 via Codex
        # Upstream URLs and transport details remain server-side; callers get a stable error.
        raise HTTPException(502, "could not start the session") from exc
    return _render_started_page(record, result)


def _render_board_page(records: list[InviteRecord]) -> str:
    e = html.escape
    rows = "".join(
        f"""<tr>
<td><a href="/m/{e(r.session_id)}">{e(r.title)}</a></td>
<td>{e(r.start.isoformat())}</td>
<td>{len(r.agenda.get("topics", []))}</td>
<td><form method="post" action="/m/{e(r.session_id)}/join">
<button type="submit">Join</button></form></td>
</tr>"""
        for r in records
    )
    empty = "<p>Nothing upcoming.</p>" if not records else ""
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>gavel calendar — board</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 3rem auto; padding: 0 1rem; }}
table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
td, th {{ text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #ddd; }}
button {{ font-size: 1rem; padding: 0.4rem 1rem; cursor: pointer; }}
form {{ margin: 0; }}
</style></head>
<body>
<h1>Upcoming meetings</h1>
{empty}
<table><tr><th>Meeting</th><th>Start</th><th>Topics</th><th></th></tr>{rows}</table>
</body></html>"""


def _render_started_page(record: InviteRecord, result: dict[str, str]) -> str:
    e = html.escape
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{e(record.title)} — started</title></head>
<body style="font-family: system-ui, sans-serif; max-width: 720px; margin: 3rem auto;">
<h1>Session started</h1>
<p>{e(record.title)} is live. <a href="/m/{e(record.session_id)}">Follow it in the room</a>.</p>
<p>ears meeting <code>{e(result["meetingId"])}</code>, session <code>{e(result["sessionId"])}</code>.</p>
</body></html>"""
