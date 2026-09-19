"""HTTP surface.

    GET  /                  redirects to /board (Traefik routes the whole host here)
    GET  /compose            the brief textarea — see compose.py
    POST /compose/parse      brief → LLM → editable confirm form
    POST /compose/send       confirm → meeting created, .ics + email sent best-effort
    POST /invite            upload or paste an .ics → {sessionId, joinUrl}
    GET  /m/{session_id}    the join page: title, agenda with budgets, expected
                             attendees, one Join button
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
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from . import compose, scheduler, service
from .agenda import attendee_name, build_agenda
from .ears_client import EarsClient
from .feed_store import FeedRegistry
from .ics_parser import InvalidInvite, parse_ics
from .settings import get_settings
from .store import InviteRecord, InviteStore

settings = get_settings()
store = InviteStore()
ears = EarsClient(settings.ears_api_url)
feed_registry = FeedRegistry()


@asynccontextmanager
async def lifespan(_app: FastAPI):
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
    return {"status": "ok", "pending": len(store.pending()), "feeds": feeds}


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
    store.save(
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
    return await compose.handle_send(form, store, settings)


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
async def join_page(session_id: str) -> str:
    record = store.get(session_id)
    if record is None:
        raise HTTPException(404, "no such invite")
    return _render_join_page(record)


@app.post("/m/{session_id}/join", response_class=HTMLResponse)
async def join(session_id: str) -> str:
    record = store.get(session_id)
    if record is None:
        raise HTTPException(404, "no such invite")
    try:
        result = await service.start(store, ears, session_id)
    except Exception as exc:  # ears unreachable, meeting rejected, etc.
        raise HTTPException(502, f"could not start the session: {exc}") from exc
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


def _render_join_page(record: InviteRecord) -> str:
    e = html.escape
    rows = "".join(
        f"<tr><td>{e(t['title'])}</td><td>{t['budgetSeconds'] // 60} min</td>"
        f"<td>{e(attendee_name(record.agenda, t.get('owner')))}</td></tr>"
        for t in record.agenda["topics"]
    )
    attendees = "".join(
        f"<li>{e(a['name'])} ({e(a['role'])})</li>" for a in record.agenda["attendees"]
    )
    started_banner = "<p><strong>Already started.</strong></p>" if record.started else ""
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{e(record.title)}</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 720px; margin: 3rem auto; padding: 0 1rem; }}
table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
td, th {{ text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #ddd; }}
button {{ font-size: 1.1rem; padding: 0.6rem 1.4rem; cursor: pointer; }}
</style></head>
<body>
<h1>{e(record.title)}</h1>
<p>{e(record.start.isoformat())} — {e(record.end.isoformat())}</p>
<p>{e(record.agenda["purpose"])}</p>
{started_banner}
<h2>Agenda</h2>
<table><tr><th>Topic</th><th>Budget</th><th>Owner</th></tr>{rows}</table>
<h2>Expected</h2>
<ul>{attendees}</ul>
<form method="post" action="/m/{e(record.session_id)}/join">
<button type="submit">Join</button>
</form>
</body></html>"""


def _render_started_page(record: InviteRecord, result: dict[str, str]) -> str:
    e = html.escape
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{e(record.title)} — started</title></head>
<body style="font-family: system-ui, sans-serif; max-width: 720px; margin: 3rem auto;">
<h1>Session started</h1>
<p>{e(record.title)} is live.</p>
<p>ears meeting <code>{e(result["meetingId"])}</code>, session <code>{e(result["sessionId"])}</code>.</p>
</body></html>"""

