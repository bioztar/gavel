"""The compose front door: a plain-English brief -> LLM -> an editable confirm
form -> a real meeting in `InviteStore`, a join link, and a best-effort
Resend email.

Ordering, per the mission: the meeting is built in the store *before* the
`.ics` or the email is even attempted, so the join URL always works even if
everything after it fails. Nothing here imports `app.py` — the three routes
live there instead (see its module docstring) so they share its one `store`
instance without a circular import; this module only takes the store, an
already-built `Settings`, and form data as plain arguments.
"""

from __future__ import annotations

import html
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from email.utils import getaddresses
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from .agenda import attendee_name, build_agenda
from .ics_parser import InviteAttendee, ParsedInvite, TopicDraft
from .ics_writer import build_ics
from .llm import NebiusClient, ParsedBrief
from .mailer import MailResult, send_invite
from .store import InviteRecord, InviteStore

if TYPE_CHECKING:
    from starlette.datastructures import FormData

    from .settings import Settings

logger = logging.getLogger(__name__)

# When the LLM found no topics, or failed outright, this many blank rows are
# rendered so there is still something to type into without JS to add rows.
_MIN_TOPIC_ROWS = 3


def _form_str(form: FormData, key: str, default: str = "") -> str:
    value = form.get(key)
    return value if isinstance(value, str) else default


def _attendees_from_field(raw: str) -> list[tuple[str, str]]:
    """"Name <email>, email2, ..." -> [(name, email), ...]. A bare address
    falls back to its local part for a name, same convention as
    `ics_parser._attendee_name`.
    """
    out: list[tuple[str, str]] = []
    for name, email in getaddresses([raw]):
        email = email.strip().lower()
        if not email:
            continue
        display = name.strip() or email.split("@")[0].replace(".", " ").replace("_", " ").title()
        out.append((display, email))
    return out


def _fill_topic_minutes(minutes: list[int | None], total_minutes: int) -> list[int]:
    """Every row that named a duration keeps it; whatever is left splits
    evenly, in whole minutes, across the rows that did not — the last one
    absorbs the remainder. Mirrors `agenda.py:_budget_seconds`, but in
    minutes: every value handed to `TopicDraft.budget_seconds` must be an
    exact multiple of 60, or the `.ics` round trip (`ics_writer.py`, minutes
    only) truncates it on the way back in.
    """
    known = [m for m in minutes if m is not None]
    remaining = max(total_minutes - sum(known), 0)
    unknown_count = sum(1 for m in minutes if m is None)
    if unknown_count == 0:
        return [m for m in minutes if m is not None]

    share, extra = divmod(remaining, unknown_count)
    out: list[int] = []
    given = 0
    for m in minutes:
        if m is not None:
            out.append(m)
            continue
        given += 1
        out.append(share + (extra if given == unknown_count else 0))
    return out


# --- GET /compose ------------------------------------------------------------------


# The compose pages are the first thing a judge or a colleague sees, so they get
# a real look rather than raw browser defaults. CSS only, one shared constant,
# no CDN font and no JS: the calendar service must render offline on a laptop on
# a conference floor. Interpolated as {_STYLE} into each page's <style> block --
# keep it out of the f-strings themselves so the braces need no doubling.
_STYLE = """
:root {
  color-scheme: dark;
  --bg: #0f1115;
  --card: #171a21;
  --line: #262b36;
  --ink: #e8eaf0;
  --muted: #98a0b3;
  --accent: #6c7cff;
  --accent-ink: #fff;
  --warn: #ffb86b;
  --bad: #ff7b7b;
  --good: #58d6a0;
}
* { box-sizing: border-box; }
html { background: var(--bg); }
body {
  font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  font-size: 16px; line-height: 1.55; color: var(--ink);
  max-width: 860px; margin: 3rem auto 4rem; padding: 2.5rem;
  background: var(--card); border: 1px solid var(--line); border-radius: 16px;
  box-shadow: 0 18px 50px rgba(0,0,0,.45);
}
h1 { font-size: 1.7rem; letter-spacing: -.02em; margin: 0 0 .4rem; }
h1::after {
  content: ""; display: block; width: 54px; height: 3px; margin-top: .7rem;
  background: var(--accent); border-radius: 2px;
}
h2 { font-size: 1.1rem; text-transform: uppercase; letter-spacing: .08em;
     color: var(--muted); margin: 2rem 0 .5rem; }
p { color: var(--muted); }
a { color: var(--accent); }
label { display: block; font-weight: 600; font-size: .85rem; letter-spacing: .04em;
        text-transform: uppercase; color: var(--muted); margin: 1.4rem 0 .35rem; }
input, textarea {
  width: 100%; font: inherit; color: var(--ink);
  background: #10131a; border: 1px solid var(--line); border-radius: 9px;
  padding: .6rem .7rem;
}
textarea { height: 8.5rem; resize: vertical; }
input:focus, textarea:focus {
  outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(108,124,255,.25);
}
table { width: 100%; border-collapse: collapse; margin: .8rem 0 0;
        border: 1px solid var(--line); border-radius: 12px; overflow: hidden; }
th { text-align: left; font-size: .75rem; text-transform: uppercase; letter-spacing: .07em;
     color: var(--muted); background: #10131a; padding: .6rem .7rem; }
td { padding: .45rem .5rem; border-top: 1px solid var(--line); vertical-align: middle; }
tr:nth-child(even) td { background: rgba(255,255,255,.015); }
td input { border-color: transparent; background: transparent; }
td input:focus { border-color: var(--accent); background: #10131a; }
button, a.button {
  display: inline-block; font: inherit; font-weight: 600; font-size: 1rem;
  margin-top: 1.6rem; padding: .7rem 1.5rem; cursor: pointer;
  color: var(--accent-ink); background: var(--accent);
  border: 0; border-radius: 10px; text-decoration: none;
}
button:hover, a.button:hover { filter: brightness(1.1); }
@media (max-width: 640px) {
  body { margin: 0; padding: 1.5rem 1.1rem; border: 0; border-radius: 0; box-shadow: none; }
  table, thead, tbody, tr, td, th { display: block; }
  th { display: none; }
  td { border-top: 0; }
  tr { border-top: 1px solid var(--line); padding: .5rem 0; }
}
"""


def render_brief_form(default_attendees: str) -> str:
    e = html.escape
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>gavel calendar — compose</title>
<style>{_STYLE}</style></head>
<body>
<h1>Set up a meeting</h1>
<p>Type it like you'd say it. "set up a 15 minute meeting in one hour with Artem, we need to
cover pricing, the launch date and who owns the blockers."</p>
<form method="post" action="/compose/parse">
<label for="brief">Brief</label>
<textarea id="brief" name="brief" required autofocus></textarea>
<label for="attendees">Attendees</label>
<input id="attendees" name="attendees" value="{e(default_attendees)}">
<button type="submit">Parse</button>
</form>
</body></html>"""


# --- POST /compose/parse ------------------------------------------------------------


async def render_confirm_form(brief: str, attendees: str, settings: Settings) -> str:
    llm = NebiusClient(settings.nebius_base_url, settings.nebius_api_key)
    now = datetime.now(ZoneInfo(settings.compose_timezone))
    attendee_pairs = _attendees_from_field(attendees)
    parsed = await llm.parse_brief(
        brief,
        now=now,
        timezone=settings.compose_timezone,
        attendees=[name for name, _ in attendee_pairs],
    )
    return _render_confirm_html(brief, attendees, parsed, settings.compose_timezone)


@dataclass
class _Row:
    title: str = ""
    minutes: str = ""
    owner: str = ""
    must_hear: str = ""


def _rows_from_parsed(
    parsed: ParsedBrief | None, timezone: str, host_name: str = ""
) -> tuple[list[_Row], str]:
    """Rows for the confirm table. A topic the brief did not assign gets the
    host as its owner and its only must-hear, rather than a blank box: an
    unowned topic gives the chair nothing to chase, and a guess sitting in an
    editable field is corrected in one keystroke. Blank is not."""
    if parsed is None:
        return [_Row() for _ in range(_MIN_TOPIC_ROWS)], ""
    rows = [
        _Row(
            title=t.title,
            minutes="" if t.minutes is None else str(t.minutes),
            owner=t.owner or host_name,
            must_hear=", ".join(t.must_hear) or (t.owner or host_name),
        )
        for t in parsed.topics
    ]
    while len(rows) < _MIN_TOPIC_ROWS:
        rows.append(_Row())
    local_start = parsed.start.astimezone(ZoneInfo(timezone))
    return rows, local_start.strftime("%Y-%m-%dT%H:%M")


def _render_confirm_html(
    brief: str, attendees: str, parsed: ParsedBrief | None, timezone: str
) -> str:
    e = html.escape
    attendee_pairs = _attendees_from_field(attendees)
    host_name = attendee_pairs[0][0] if attendee_pairs else ""
    rows, start_value = _rows_from_parsed(parsed, timezone, host_name)
    title = e(parsed.title if parsed else "")
    duration = str(parsed.duration_minutes) if parsed else ""
    warning = (
        ""
        if parsed is not None
        else "<p style='color:var(--bad)'><strong>Could not parse that brief.</strong> "
        "Fill in the agenda by hand below.</p>"
    )

    topic_rows = "".join(
        f"""<tr>
<td><input name="topic_title_{i}" value="{e(r.title)}"></td>
<td><input name="topic_minutes_{i}" value="{e(r.minutes)}" size="4"></td>
<td><input name="topic_owner_{i}" value="{e(r.owner)}"></td>
<td><input name="topic_must_hear_{i}" value="{e(r.must_hear)}"></td>
</tr>"""
        for i, r in enumerate(rows)
    )

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>gavel calendar — confirm</title>
<style>{_STYLE}</style></head>
<body>
<h1>Confirm the meeting</h1>
{warning}
<form method="post" action="/compose/send">
<input type="hidden" name="brief" value="{e(brief)}">
<input type="hidden" name="attendees" value="{e(attendees)}">
<label for="title">Title</label>
<input id="title" name="title" value="{title}">
<label for="start">Start ({e(timezone)})</label>
<input id="start" name="start" type="datetime-local" value="{e(start_value)}">
<label for="duration_minutes">Duration (minutes)</label>
<input id="duration_minutes" name="duration_minutes" type="number" min="1" value="{e(duration)}">
<label>Topics</label>
<input type="hidden" name="topics_count" value="{len(rows)}">
<table><tr><th>Title</th><th>Min</th><th>Owner</th><th>Must hear</th></tr>{topic_rows}</table>
<button type="submit">Send</button>
</form>
</body></html>"""


# --- POST /compose/send --------------------------------------------------------------


def _rows_from_form(form: FormData) -> list[_Row]:
    count = int(_form_str(form, "topics_count", "0") or 0)
    return [
        _Row(
            title=_form_str(form, f"topic_title_{i}"),
            minutes=_form_str(form, f"topic_minutes_{i}"),
            owner=_form_str(form, f"topic_owner_{i}"),
            must_hear=_form_str(form, f"topic_must_hear_{i}"),
        )
        for i in range(count)
    ]


def _topic_drafts(rows: list[_Row], total_minutes: int) -> list[TopicDraft]:
    named = [r for r in rows if r.title.strip()]
    minutes = [int(r.minutes) if r.minutes.strip().isdigit() else None for r in named]
    filled = _fill_topic_minutes(minutes, total_minutes)
    return [
        TopicDraft(
            title=r.title.strip(),
            budget_seconds=m * 60,
            owner_name=r.owner.strip() or None,
            must_hear_names=[n.strip() for n in r.must_hear.split(",") if n.strip()],
        )
        for r, m in zip(named, filled, strict=True)
    ]


def _host(attendee_pairs: list[tuple[str, str]], from_email: str) -> tuple[str, str]:
    """The attendee this invite's `ORGANIZER` speaks for. Preferring
    `COMPOSE_FROM_EMAIL` when it is itself an attendee keeps `ics_writer.py`'s
    `ORGANIZER` and `ics_parser`'s re-derived `is_organizer` pointing at the
    same person on a round trip; falling back to the first attendee still
    guarantees there always is one.
    """
    from_email = from_email.strip().lower()
    for name, email in attendee_pairs:
        if email == from_email:
            return name, email
    return attendee_pairs[0]


async def handle_send(form: FormData, store: InviteStore, settings: Settings) -> str:
    title = _form_str(form, "title").strip() or "Untitled meeting"
    brief = _form_str(form, "brief")
    attendees_raw = _form_str(form, "attendees")
    attendee_pairs = _attendees_from_field(attendees_raw) or _attendees_from_field(
        settings.compose_default_attendees
    )

    tz = ZoneInfo(settings.compose_timezone)
    try:
        start = datetime.fromisoformat(_form_str(form, "start")).replace(tzinfo=tz)
    except ValueError:
        start = datetime.now(tz)

    duration_raw = _form_str(form, "duration_minutes")
    duration_minutes = int(duration_raw) if duration_raw.strip().isdigit() else 30
    from datetime import timedelta

    end = start + timedelta(minutes=duration_minutes)

    host_name, host_email = _host(attendee_pairs, settings.compose_from_email)
    invite_attendees = [
        InviteAttendee(email=email, name=name, is_organizer=(email == host_email))
        for name, email in attendee_pairs
    ]
    topics = _topic_drafts(_rows_from_form(form), duration_minutes)

    invite = ParsedInvite(
        title=title,
        start=start,
        end=end,
        attendees=invite_attendees,
        topics=topics,
        description=brief.strip() or title,
    )

    session_id = uuid.uuid4().hex[:12]
    agenda = build_agenda(invite, session_id, settings.attendee_map)
    record = InviteRecord(
        session_id=session_id,
        title=title,
        start=start,
        end=end,
        agenda=agenda,
        context=invite.description,
    )
    # The meeting exists from this point on, no matter what happens next.
    store.save(record)
    join_url = f"{settings.calendar_public_url}/m/{session_id}"

    mail_result = await _safe_mail(
        session_id=session_id,
        title=title,
        start=start,
        end=end,
        agenda=agenda,
        attendee_pairs=attendee_pairs,
        host_name=host_name,
        host_email=host_email,
        join_url=join_url,
        settings=settings,
    )

    return _render_success_page(record, join_url, settings.discord_meeting_url, mail_result)


async def _safe_mail(
    *,
    session_id: str,
    title: str,
    start: datetime,
    end: datetime,
    agenda: dict,
    attendee_pairs: list[tuple[str, str]],
    host_name: str,
    host_email: str,
    join_url: str,
    settings: Settings,
) -> MailResult:
    """ics generation and the mail call both run under one net: a bug in
    either must degrade to a visible notice, never a 500 — the meeting in
    `store` was already saved by the caller and must not depend on this.
    """
    try:
        ics_bytes = build_ics(
            session_id=session_id,
            title=title,
            start=start,
            end=end,
            agenda=agenda,
            attendees=attendee_pairs,
            organizer_email=host_email,
            organizer_name=host_name,
            discord_url=settings.discord_meeting_url,
            join_url=join_url,
        )
    except Exception as exc:  # isolation of last resort, see mailer.py
        logger.exception("compose.ics_build_failed")
        return MailResult(sent=False, reason=f"invite not sent (ics build failed: {type(exc).__name__})")

    text_body = f"{agenda.get('purpose', title)}\n\nJoin: {join_url}\nDiscord: {settings.discord_meeting_url}"
    try:
        return await send_invite(
            api_key=settings.resend_api_key,
            from_email=settings.compose_from_email,
            to=[email for _, email in attendee_pairs],
            subject=title,
            text_body=text_body,
            ics_bytes=ics_bytes,
        )
    except Exception as exc:  # a mailer bug must never fail the meeting
        logger.exception("compose.mail_call_failed")
        return MailResult(sent=False, reason=f"invite not sent ({type(exc).__name__})")


def _render_success_page(
    record: InviteRecord, join_url: str, discord_url: str, mail_result: MailResult
) -> str:
    e = html.escape
    rows = "".join(
        f"<tr><td>{e(t['title'])}</td><td>{t['budgetSeconds'] // 60} min</td>"
        f"<td>{e(attendee_name(record.agenda, t.get('owner')))}</td></tr>"
        for t in record.agenda["topics"]
    )
    notice = (
        "<p style='color:var(--good)'>Invite emailed.</p>"
        if mail_result.sent
        else f"<p style='color:var(--warn)'>invite email not sent: {e(mail_result.reason or 'unknown reason')}</p>"
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{e(record.title)} — created</title>
<style>{_STYLE}</style></head>
<body>
<h1>{e(record.title)}</h1>
<p>{e(record.start.isoformat())} — {e(record.end.isoformat())}</p>
{notice}
<p><a class="button" href="{e(join_url)}">Join link</a></p>
<p>Discord: <a href="{e(discord_url)}">{e(discord_url)}</a></p>
<h2>Agenda</h2>
<table><tr><th>Topic</th><th>Budget</th><th>Owner</th></tr>{rows}</table>
</body></html>"""
