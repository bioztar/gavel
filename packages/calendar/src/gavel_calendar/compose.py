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


def render_brief_form(default_attendees: str) -> str:
    e = html.escape
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>gavel calendar — compose</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 720px; margin: 3rem auto; padding: 0 1rem; }}
textarea, input {{ width: 100%; font: inherit; padding: 0.5rem; box-sizing: border-box; margin: 0.3rem 0 1rem; }}
textarea {{ height: 8rem; }}
label {{ font-weight: 600; }}
button {{ font-size: 1.1rem; padding: 0.6rem 1.4rem; cursor: pointer; }}
</style></head>
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


def _rows_from_parsed(parsed: ParsedBrief | None, timezone: str) -> tuple[list[_Row], str]:
    if parsed is None:
        return [_Row() for _ in range(_MIN_TOPIC_ROWS)], ""
    rows = [
        _Row(
            title=t.title,
            minutes="" if t.minutes is None else str(t.minutes),
            owner=t.owner or "",
            must_hear=", ".join(t.must_hear),
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
    rows, start_value = _rows_from_parsed(parsed, timezone)
    title = e(parsed.title if parsed else "")
    duration = str(parsed.duration_minutes) if parsed else ""
    warning = (
        ""
        if parsed is not None
        else "<p style='color:#a33'><strong>Could not parse that brief.</strong> "
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
<style>
body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 3rem auto; padding: 0 1rem; }}
input {{ width: 100%; font: inherit; padding: 0.4rem; box-sizing: border-box; }}
table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
td, th {{ text-align: left; padding: 0.4rem 0.6rem; }}
label {{ font-weight: 600; display: block; margin-top: 1rem; }}
button {{ font-size: 1.1rem; padding: 0.6rem 1.4rem; cursor: pointer; margin-top: 1rem; }}
</style></head>
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
    except Exception as exc:  # noqa: BLE001 — isolation of last resort, see mailer.py
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
    except Exception as exc:  # noqa: BLE001 — a mailer bug must never fail the meeting
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
        "<p style='color:#2a7'>Invite emailed.</p>"
        if mail_result.sent
        else f"<p style='color:#a73'>invite email not sent: {e(mail_result.reason or 'unknown reason')}</p>"
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{e(record.title)} — created</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 720px; margin: 3rem auto; padding: 0 1rem; }}
table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
td, th {{ text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #ddd; }}
a.button {{ display: inline-block; font-size: 1.1rem; padding: 0.6rem 1.4rem; }}
</style></head>
<body>
<h1>{e(record.title)}</h1>
<p>{e(record.start.isoformat())} — {e(record.end.isoformat())}</p>
{notice}
<p><a class="button" href="{e(join_url)}">Join link</a></p>
<p>Discord: <a href="{e(discord_url)}">{e(discord_url)}</a></p>
<h2>Agenda</h2>
<table><tr><th>Topic</th><th>Budget</th><th>Owner</th></tr>{rows}</table>
</body></html>"""
