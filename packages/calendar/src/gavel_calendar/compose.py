"""The compose front door: a plain-English brief -> LLM -> an editable confirm
form -> a real meeting in `InviteStore`, a join link, and a best-effort
Resend email.

Ordering, per the mission: the meeting is built in the store *before* the
`.ics`, the ears session or the email is even attempted, so the join URL always
works even if everything after it fails. Handing it to ears comes next, because
a meeting that exists but is not the one the chair is holding is the friction
this front door was built to remove. Nothing here imports `app.py` — the three routes
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

from . import service
from .agenda import attendee_name, build_agenda
from .ears_client import EarsClient
from .ics_parser import InviteAttendee, ParsedInvite, TopicDraft
from .ics_writer import build_ics
from .invite_email import render_invite_html, render_invite_text
from .llm import NebiusClient, ParsedBrief
from .mailer import MailResult, send_invite
from .schema import DEFAULT_ENFORCEMENT, ENFORCEMENT_LEVELS
from .store import InviteRecord, InviteStore

if TYPE_CHECKING:
    from starlette.datastructures import FormData

    from .settings import Settings

logger = logging.getLogger(__name__)

# `_rows_from_parsed` falls back to this many blank rows when there is nothing to
# show at all. The no-agenda case never reaches it -- that is `render_gate_html`.
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
#
# Light, near-white, one accent, hairline rules, a lot of air. The system font
# stack resolves to SF on the machine this is demoed from, which is most of the
# look; the rest is restraint -- no gradients, no second accent, no card that
# does not need an edge.
_STYLE = """
:root {
  color-scheme: light;
  --bg: #fbfbfd;
  --surface: #ffffff;
  --ink: #1d1d1f;
  --dim: #6e6e73;
  --line: #d2d2d7;
  --hair: #e8e8ed;
  --accent: #0071e3;
  --warn: #b25000;
  --good: #087443;
}
* { box-sizing: border-box; }
html { background: var(--bg); -webkit-font-smoothing: antialiased; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI",
               Roboto, Helvetica, Arial, sans-serif;
  font-size: 17px; line-height: 1.5; color: var(--ink); background: var(--bg);
  margin: 0; padding: 88px 24px 120px;
}
.page { max-width: 680px; margin: 0 auto; }
.eyebrow { margin: 0 0 14px; font-size: 12px; font-weight: 590;
           letter-spacing: .14em; text-transform: uppercase; color: var(--dim); }
h1 { margin: 0 0 12px; font-size: 44px; line-height: 1.06;
     letter-spacing: -.024em; font-weight: 600; }
h2 { margin: 52px 0 12px; font-size: 12px; font-weight: 590; letter-spacing: .09em;
     text-transform: uppercase; color: var(--dim); }
.lede { margin: 0 0 8px; font-size: 19px; line-height: 1.5; color: var(--dim);
        max-width: 33em; }
.quote { margin: 0 0 40px; font-size: 19px; line-height: 1.5; color: var(--dim);
         max-width: 33em; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
label { display: block; margin: 30px 0 8px; font-size: 13px; font-weight: 590;
        letter-spacing: -.005em; color: var(--ink); }
label .opt { font-weight: 400; color: var(--dim); }
input, textarea, select {
  width: 100%; font: inherit; color: var(--ink); background: var(--surface);
  border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px;
  transition: border-color .15s, box-shadow .15s;
}
textarea { min-height: 148px; resize: vertical; line-height: 1.55; }
input:focus, textarea:focus, select:focus {
  outline: none; border-color: var(--accent); box-shadow: 0 0 0 4px rgba(0,113,227,.16);
}
::placeholder { color: #a1a1a6; }
button, .button {
  display: inline-block; margin-top: 36px; font: inherit; font-size: 17px;
  font-weight: 500; padding: 13px 28px; border: 0; border-radius: 980px;
  background: var(--accent); color: #fff; cursor: pointer; text-decoration: none;
}
button:hover, .button:hover { background: #0077ed; text-decoration: none; }
.quiet { display: block; margin-top: 20px; font-size: 14px; color: var(--dim); }
.hint { margin: 12px 0 0; font-size: 13.5px; line-height: 1.45; color: var(--dim); }
table { width: 100%; border-collapse: collapse; margin-top: 10px; }
th { text-align: left; font-size: 11px; font-weight: 590; letter-spacing: .08em;
     text-transform: uppercase; color: var(--dim);
     padding: 0 10px 10px; border-bottom: 1px solid var(--line); }
td { padding: 5px 4px; border-bottom: 1px solid var(--hair); vertical-align: middle; }
td input, td select { border-color: transparent; background: transparent;
                      padding: 9px 10px; border-radius: 9px; }
/* let the type column size to its own longest option ("presentation") instead of
   being squeezed by the 100% width every other control inherits */
td select { width: auto; }
th:first-child, td:first-child { width: 38%; }
td input:focus, td select:focus { border-color: var(--accent); background: var(--surface); }

/* the agenda gate */
.gate { margin: 0 0 8px; padding: 18px 22px; border-left: 3px solid var(--warn);
        background: #fff8f2; border-radius: 0 12px 12px 0; }
.gate p { margin: 0; font-size: 16.5px; line-height: 1.5; color: #5c3a1e; }

/* enforcement gauge */
.seg { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 10px; }
.seg input { position: absolute; opacity: 0; pointer-events: none; }
.seg label { display: block; margin: 0; padding: 14px 16px; cursor: pointer;
             border: 1px solid var(--line); border-radius: 14px; background: var(--surface);
             transition: border-color .15s, box-shadow .15s, background .15s; }
.seg label b { display: block; font-size: 15px; font-weight: 590; letter-spacing: -.01em; }
.seg label span { display: block; margin-top: 5px; font-size: 12.5px; line-height: 1.4;
                  font-weight: 400; color: var(--dim); }
.seg input:checked + label { border-color: var(--accent); background: #f2f8ff;
                             box-shadow: 0 0 0 3px rgba(0,113,227,.13); }

/* success */
.notice { display: inline-block; margin: 0 0 4px; font-size: 14px;
          padding: 8px 15px; border-radius: 980px; }
.notice.ok { background: #e9f7ef; color: var(--good); }
.notice.bad { background: #fdf2e8; color: var(--warn); }
.meta { margin: 0 0 28px; font-size: 16px; color: var(--dim); }

@media (max-width: 640px) {
  body { padding: 52px 20px 80px; }
  h1 { font-size: 33px; }
  .seg { grid-template-columns: 1fr; }
  table, tbody, tr, td { display: block; }
  thead { display: none; }
  td { border: 0; padding: 3px 0; }
  tr { border-bottom: 1px solid var(--hair); padding: 12px 0; }
  td input, td select { border-color: var(--line); background: var(--surface); }
}
"""



def render_brief_form() -> str:
    """Page one is one box and one button.

    No attendee list is pre-filled on purpose: the host dictates the meeting the
    way they would say it out loud, and who needs to be in the room is read off
    that brief on the next page, where it can still be corrected. An address
    list on the first screen is a form to fill in; this is a sentence to say.
    """
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>gavel — set up a meeting</title>
<style>{_STYLE}</style></head>
<body><div class="page">
<p class="eyebrow">gavel</p>
<h1>Set up a meeting.</h1>
<p class="quote">Say it the way you would say it out loud &mdash; &ldquo;thirty minutes with
Artem tomorrow at ten, we need to land pricing, the launch date and who owns the
blockers.&rdquo;</p>
<form method="post" action="/compose/parse">
<label for="brief">The brief</label>
<textarea id="brief" name="brief" required autofocus
 placeholder="Dictate or type it."></textarea>
<label for="attendees">Who to invite <span class="opt">&mdash; optional, we read it off
the brief</span></label>
<input id="attendees" name="attendees" placeholder="Name &lt;email&gt;, Name &lt;email&gt;">
<button type="submit">Continue</button>
</form>
</div></body></html>"""


# --- POST /compose/parse ------------------------------------------------------------


def _resolve_invitees(typed: str, settings: Settings) -> list[tuple[str, str]]:
    """Who ends up on the invite: the standing room, plus anyone typed in.

    The standing room is `COMPOSE_DEFAULT_ATTENDEES` and it is always included —
    reading a guest list out of a spoken brief reliably enough to *remove*
    someone is not a bet worth taking on a live meeting, so the brief can add
    people and the confirm page can take them away, but a silent omission is
    not possible. De-duplicated on the address, first spelling of a name wins.
    """
    pairs = _attendees_from_field(settings.compose_default_attendees)
    seen = {email for _, email in pairs}
    for name, email in _attendees_from_field(typed):
        if email not in seen:
            seen.add(email)
            pairs.append((name, email))
    return pairs


def _attendee_field(pairs: list[tuple[str, str]]) -> str:
    return ", ".join(f"{name} <{email}>" for name, email in pairs)


def render_gate_html(brief: str, attendees: str, typed: str = "") -> str:
    """The refusal, and the one thing that clears it.

    Everything else about this meeting is already inferred and waiting on the
    next screen. The agenda is the one field nobody can infer, so this page asks
    for that and nothing else: a sentence saying why, a box, a button. A grid of
    empty topic rows here would read as paperwork, and the point is not that
    Karen wants a form filled in -- it is that she will not book the meeting.
    """
    e = html.escape
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>gavel — agenda needed</title>
<style>{_STYLE}</style></head>
<body><div class="page">
<p class="eyebrow">not booked yet</p>
<h1>There&rsquo;s no agenda in that brief.</h1>
<div class="gate"><p>Karen won&rsquo;t put a meeting in three people&rsquo;s calendars
without one. What does this call have to decide?</p></div>
<form method="post" action="/compose/parse">
<input type="hidden" name="brief" value="{e(brief)}">
<input type="hidden" name="attendees" value="{e(attendees)}">
<label for="agenda">The agenda</label>
<textarea id="agenda" name="agenda" required autofocus
 placeholder="One line per topic. Who owns it, and how long, if you know.">{e(typed)}</textarea>
<p class="hint">&ldquo;Pricing &mdash; Artem, 10 min. Launch date &mdash; me, 5 min.
Then open discussion on the blockers.&rdquo;</p>
<button type="submit">Add agenda</button>
<a class="quiet" href="/compose">Start over with a new brief</a>
</form>
</div></body></html>"""


def _rows_from_lines(typed: str, host_name: str) -> list[_Row]:
    """Last-resort reading of a typed agenda: one topic per line.

    Only reached when the host has already been asked for an agenda, typed one,
    and the model still came back with no topics -- a parse failure, not an
    empty brief. Taking the lines literally is worse than a real parse and far
    better than refusing a second time, which is the one way this beat can
    dead-end in front of a room.
    """
    parts = [
        chunk.strip(" \t-*\u2022")
        for line in typed.splitlines()
        for chunk in line.split(";")
    ]
    return [_Row(title=chunk, owner=host_name) for chunk in parts if chunk]


async def render_confirm_form(
    brief: str, attendees: str, settings: Settings, agenda_text: str = ""
) -> str:
    """Page two, or the gate.

    `agenda_text` is set only by the gate page posting back. When it is present
    it is appended to the brief and the whole thing is re-parsed, so the agenda
    arrives through exactly the same path as one that was dictated in the first
    place -- there is no second-class agenda in this system.
    """
    llm = NebiusClient(settings.nebius_base_url, settings.nebius_api_key)
    now = datetime.now(ZoneInfo(settings.compose_timezone))
    attendee_pairs = _resolve_invitees(attendees, settings)
    attendee_field = _attendee_field(attendee_pairs)
    typed = agenda_text.strip()
    combined = f"{brief}\n\nAgenda:\n{typed}" if typed else brief
    parsed = await llm.parse_brief(
        combined,
        now=now,
        timezone=settings.compose_timezone,
        attendees=[name for name, _ in attendee_pairs],
    )
    if parsed is None or not parsed.topics:
        if not typed:
            return render_gate_html(brief, attendee_field)
        host_name = attendee_pairs[0][0] if attendee_pairs else ""
        fallback = _rows_from_lines(typed, host_name)
        if fallback:
            return _render_confirm_html(
                brief, attendee_field, parsed, settings.compose_timezone, fallback
            )
        return render_gate_html(brief, attendee_field, typed)
    return _render_confirm_html(brief, attendee_field, parsed, settings.compose_timezone)


@dataclass
class _Row:
    title: str = ""
    minutes: str = ""
    owner: str = ""
    must_hear: str = ""
    # "discussion" | "presentation" — see TopicDraft.type. A slot where one
    # person speaks by design (a demo, a readout) is a presentation, and the
    # chair will not hand the floor on inside it.
    type: str = "discussion"


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
            type=t.type,
        )
        for t in parsed.topics
    ]
    # One spare row: enough to add a topic that was missed, not so many that a
    # parsed agenda reads as a half-empty form.
    rows.append(_Row())
    local_start = parsed.start.astimezone(ZoneInfo(timezone))
    return rows, local_start.strftime("%Y-%m-%dT%H:%M")


def _render_confirm_html(
    brief: str,
    attendees: str,
    parsed: ParsedBrief | None,
    timezone: str,
    fallback_rows: list[_Row] | None = None,
) -> str:
    e = html.escape
    attendee_pairs = _attendees_from_field(attendees)
    host_name = attendee_pairs[0][0] if attendee_pairs else ""
    rows, start_value = _rows_from_parsed(parsed, timezone, host_name)
    if fallback_rows:
        rows = [*fallback_rows, _Row()]
    title = e(parsed.title if parsed else "")
    purpose = e(parsed.purpose.strip() if parsed and parsed.purpose.strip() else "")
    duration = str(parsed.duration_minutes) if parsed else ""

    topic_rows = "".join(
        f"""<tr>
<td><input name="topic_title_{i}" value="{e(r.title)}"></td>
<td><input name="topic_minutes_{i}" value="{e(r.minutes)}" size="4"></td>
<td><input name="topic_owner_{i}" value="{e(r.owner)}"></td>
<td><input name="topic_must_hear_{i}" value="{e(r.must_hear)}"></td>
<td><select name="topic_type_{i}">
<option value="discussion"{"" if r.type == "presentation" else " selected"}>discussion</option>
<option value="presentation"{" selected" if r.type == "presentation" else ""}>presentation</option>
</select></td>
</tr>"""
        for i, r in enumerate(rows)
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>gavel — confirm</title>
<style>{_STYLE}</style></head>
<body><div class="page">
<p class="eyebrow">before it goes out</p>
<h1>Here&rsquo;s the contract.</h1>
<p class="lede">This is what the invitees will read, and what the chair will hold
the room to. Change anything that is wrong.</p>
<form method="post" action="/compose/send">
<input type="hidden" name="brief" value="{e(brief)}">
<label for="title">Title</label>
<input id="title" name="title" value="{title}">
<label for="purpose">Purpose <span class="opt">&mdash; one line, read first</span></label>
<input id="purpose" name="purpose" value="{purpose}">
<label for="attendees">Invitees <span class="opt">&mdash; add or remove</span></label>
<input id="attendees" name="attendees" value="{e(attendees)}">
<label for="start">Start <span class="opt">&mdash; {e(timezone)}</span></label>
<input id="start" name="start" type="datetime-local" value="{e(start_value)}">
<label for="duration_minutes">Duration <span class="opt">&mdash; minutes</span></label>
<input id="duration_minutes" name="duration_minutes" type="number" min="1" value="{e(duration)}">

<h2>Agenda</h2>
<input type="hidden" name="topics_count" value="{len(rows)}">
<table><thead><tr><th>Topic</th><th>Min</th><th>Owner</th><th>Must be heard</th>
<th>Type</th></tr></thead><tbody>{topic_rows}</tbody></table>
<p class="hint">A <strong>presentation</strong> is one person holding the floor on
purpose. The chair keeps it on the agenda and never hands the floor on inside it.</p>

<h2>How hard she chairs</h2>
<div class="seg">
<input type="radio" id="enf_low" name="enforcement" value="low">
<label for="enf_low"><b>Low</b><span>Long rope. She only speaks up when a topic
badly overruns.</span></label>
<input type="radio" id="enf_medium" name="enforcement" value="medium" checked>
<label for="enf_medium"><b>Medium</b><span>Waits for a pause, then moves the room
on. The default chair.</span></label>
<input type="radio" id="enf_high" name="enforcement" value="high">
<label for="enf_high"><b>High</b><span>Cuts in mid-sentence, short grace, and may
mute after a warning is ignored.</span></label>
</div>
<p class="hint">Nobody is exempt, including you. If the host is the one running over, the host is the one who gets chaired.</p>

<button type="submit">Send the invite</button>
</form>
</div></body></html>"""


# --- POST /compose/send --------------------------------------------------------------


def _rows_from_form(form: FormData) -> list[_Row]:
    count = int(_form_str(form, "topics_count", "0") or 0)
    return [
        _Row(
            title=_form_str(form, f"topic_title_{i}"),
            minutes=_form_str(form, f"topic_minutes_{i}"),
            owner=_form_str(form, f"topic_owner_{i}"),
            must_hear=_form_str(form, f"topic_must_hear_{i}"),
            type=_form_str(form, f"topic_type_{i}", "discussion"),
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
            type="presentation" if r.type.strip() == "presentation" else "discussion",
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


async def handle_send(
    form: FormData,
    store: InviteStore,
    settings: Settings,
    ears: EarsClient | None = None,
) -> str:
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
    # The gauge is merged *over* the environment's overrides: the environment
    # carries deployment facts, the gauge carries this meeting's intent, and the
    # gauge wins on the keys it names. Unknown value falls back to Medium rather
    # than 500ing -- a hand-rolled POST must still produce a meeting.
    level = _form_str(form, "enforcement", DEFAULT_ENFORCEMENT).strip().lower()
    overrides = {
        **settings.policy_overrides,
        **ENFORCEMENT_LEVELS.get(level, ENFORCEMENT_LEVELS[DEFAULT_ENFORCEMENT]),
    }
    agenda = build_agenda(invite, session_id, settings.attendee_map, overrides)
    # The host's own one-liner wins over the sentence `agenda.py` scrapes off the
    # top of the brief. `invite.description` stays the full brief either way —
    # that is what `record.context` carries to the chair.
    purpose = _form_str(form, "purpose").strip()
    if purpose:
        agenda["purpose"] = purpose
    record = InviteRecord(
        session_id=session_id,
        title=title,
        start=start,
        end=end,
        agenda=agenda,
        context=invite.description,
    )
    # The meeting exists from this point on, no matter what happens next.
    await store.save(record)
    join_url = f"{settings.calendar_public_url}/m/{session_id}"

    # ...and it is the meeting ears is holding, from this point on too. Creating it is the
    # moment the host has the agenda in front of them and knows it is right, so this is
    # where the chair is handed it — not at the event's start time, by which point people
    # are already in the voice channel wondering why Karen has nothing to say. The session
    # opens a lobby, nothing more: the agenda clock only starts once the room is full or
    # somebody asks her to begin (docs/CONTRACT.md §2).
    started = await _safe_start(store, ears, session_id)

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

    return _render_success_page(
        record, join_url, settings.discord_meeting_url, mail_result, started
    )


async def _safe_start(
    store: InviteStore, ears: EarsClient | None, session_id: str
) -> bool:
    """Make this the meeting ears is running. Best-effort, like the mail: an ears that is
    down or busy costs the head start, never the invite — the scheduler starts it at the
    event's own time, and the room page's own Join button starts it on a click."""
    if ears is None:
        return False
    try:
        await service.start(store, ears, session_id)
    except Exception:  # ears unreachable, rejecting, restarting...
        logger.exception("compose.start_failed session_id=%s", session_id)
        return False
    return True


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

    # The email carries the agenda itself, not the brief that was dictated to
    # produce it: owner and must-be-heard per topic, in the order they will run.
    kw = {
        "title": title, "start": start, "end": end, "join_url": join_url,
        "discord_url": settings.discord_meeting_url,
    }
    try:
        text_body = render_invite_text(agenda, **kw)  # type: ignore[arg-type]
        html_body = render_invite_html(agenda, **kw)  # type: ignore[arg-type]
    except Exception:  # a rendering bug must not cost the invite
        logger.exception("compose.invite_render_failed")
        text_body = f"{agenda.get('purpose', title)}\n\nJoin: {join_url}"
        html_body = ""
    try:
        return await send_invite(
            api_key=settings.resend_api_key,
            from_email=settings.compose_from_email,
            to=[email for _, email in attendee_pairs],
            subject=title,
            text_body=text_body,
            html_body=html_body,
            ics_bytes=ics_bytes,
        )
    except Exception as exc:  # a mailer bug must never fail the meeting
        logger.exception("compose.mail_call_failed")
        return MailResult(sent=False, reason=f"invite not sent ({type(exc).__name__})")


def _render_success_page(
    record: InviteRecord,
    join_url: str,
    discord_url: str,
    mail_result: MailResult,
    started: bool = False,
) -> str:
    e = html.escape
    rows = "".join(
        f"<tr><td>{e(t['title'])}</td><td>{t['budgetSeconds'] // 60} min</td>"
        f"<td>{e(attendee_name(record.agenda, t.get('owner')))}</td></tr>"
        for t in record.agenda["topics"]
    )
    notice = (
        '<p><span class="notice ok">Invite emailed</span></p>'
        if mail_result.sent
        else '<p><span class="notice bad">Invite email not sent: '
        f"{e(mail_result.reason or 'unknown reason')}</span></p>"
    )
    # Two different promises: the invite went out, and Karen is already holding the room.
    chair = (
        '<p><span class="notice ok">Karen is holding the room</span></p>'
        if started
        else '<p><span class="notice bad">Karen has not been handed this one yet — '
        "the join link starts her</span></p>"
    )
    when = record.start.strftime("%a %d %b, %H:%M")
    mins = int((record.end - record.start).total_seconds()) // 60
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(record.title)} — created</title>
<style>{_STYLE}</style></head>
<body><div class="page">
<p class="eyebrow">in their calendars</p>
<h1>{e(record.title)}</h1>
<p class="meta">{e(when)} &nbsp;·&nbsp; {mins} min</p>
{notice}
{chair}
<p><a class="button" href="{e(join_url)}">Open the meeting room</a></p>
<p class="quiet">Discord: <a href="{e(discord_url)}">{e(discord_url)}</a></p>
<h2>Agenda</h2>
<table><thead><tr><th>Topic</th><th>Budget</th><th>Owner</th></tr></thead>
<tbody>{rows}</tbody></table>
</div></body></html>"""
