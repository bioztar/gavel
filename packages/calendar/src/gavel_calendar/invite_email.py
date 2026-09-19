"""The invite email body: the agenda, rendered the way a chair would hand it out.

What goes out is built from the *already-built* agenda dict (the same one ears
receives), never from the brief the host dictated. The brief is how a human
talks; an invite is a document, and the people reading it want to know what is
being decided, who owns each item, how long it has, and where they personally
are expected to speak.

Email HTML is not web HTML: no `<style>` block survives Gmail reliably, so
every rule here is an inline `style=` attribute on a table. Light background on
purpose — dark-mode inversion in mail clients is unpredictable, and a light
document is what the recipients' other invites look like.
"""

from __future__ import annotations

import html
from datetime import datetime

from .agenda import attendee_name

_INK = "#12151c"
_DIM = "#5b6478"
_LINE = "#e2e6ee"
_ACCENT = "#4a5bd6"
_WASH = "#f5f7fb"

_HOW_IT_RUNS = (
    "Every topic has an owner and a time budget — both are listed above.",
    "If you are named under <strong>must be heard</strong>, come with a view on that topic.",
    "Karen chairs: she keeps the room on the current topic, brings in anyone named who "
    "has not spoken, and calls time when a topic runs over.",
)


def _when(start: datetime, end: datetime) -> str:
    """'Saturday 20 September, 10:00-10:30 (CEST)' — both ends are already local."""
    zone = start.strftime("%Z") or ""
    day = start.strftime("%A %-d %B")
    # \u2013 is an en dash: a time range, not a subtraction.
    span = f"{start.strftime('%H:%M')}\u2013{end.strftime('%H:%M')}"
    return f"{day}, {span}" + (f" ({zone})" if zone else "")


def _names(agenda: dict, ids: list[str] | None) -> str:
    return ", ".join(attendee_name(agenda, i) for i in (ids or [])) or "—"


def _must_hear(agenda: dict, topic: dict) -> str:
    """Who has to speak on this topic, beyond the person already running it.

    `compose` falls back to the owner when a brief names nobody, so a topic one
    person presents arrives with that same person as its only must-hear. Printing
    "owner: Vitaly / must be heard: Vitaly" tells an invitee nothing and makes the
    column look like filler everywhere else it is real.
    """
    ids = topic.get("mustHear") or []
    owner = topic.get("owner")
    if owner is not None and list(ids) == [owner]:
        return "—"
    return _names(agenda, ids)


def _minutes(topic: dict) -> str:
    return f"{max(round(int(topic.get('budgetSeconds', 0)) / 60), 1)} min"


def render_invite_text(
    agenda: dict, *, title: str, start: datetime, end: datetime, join_url: str, discord_url: str
) -> str:
    """The plain-text alternative. Same document, no markup — some clients show
    only this one, and it is what a screen reader reads first."""
    lines = [title, _when(start, end), ""]
    purpose = str(agenda.get("purpose", "")).strip()
    if purpose:
        lines += [purpose, ""]
    lines.append("AGENDA")
    for n, t in enumerate(agenda.get("topics", []), start=1):
        lines.append(f"{n}. {t['title']} — {_minutes(t)}")
        lines.append(f"   owner: {attendee_name(agenda, t.get('owner'))}")
        lines.append(f"   must be heard: {_must_hear(agenda, t)}")
        if t.get("type") == "presentation":
            lines.append("   presentation — one speaker, uninterrupted")
    lines += [
        "",
        "HOW THIS MEETING RUNS",
        "- Every topic has an owner and a time budget.",
        "- If you are named under 'must be heard', come with a view on that topic.",
        "- Karen chairs: she holds the room to the current topic, brings in anyone",
        "  named who has not spoken, and calls time when a topic runs over.",
        "",
        f"Agenda and live status: {join_url}",
        f"Call: {discord_url}",
    ]
    return "\n".join(lines)


def _topic_row(agenda: dict, n: int, topic: dict, striped: bool) -> str:
    e = html.escape
    bg = _WASH if striped else "#ffffff"
    badge = (
        f'<span style="display:inline-block;margin-left:8px;padding:1px 7px;border-radius:999px;'
        f'background:#eceefb;color:{_ACCENT};font-size:11px;font-weight:600;letter-spacing:.04em;'
        f'text-transform:uppercase">presentation</span>'
        if topic.get("type") == "presentation"
        else ""
    )
    cell = f"padding:11px 14px;border-top:1px solid {_LINE};vertical-align:top;font-size:15px"
    return f"""<tr style="background:{bg}">
<td style="{cell};color:{_DIM};width:26px">{n}</td>
<td style="{cell};color:{_INK};font-weight:600">{e(topic["title"])}{badge}</td>
<td style="{cell};color:{_DIM};white-space:nowrap">{_minutes(topic)}</td>
<td style="{cell};color:{_INK}">{e(attendee_name(agenda, topic.get("owner")))}</td>
<td style="{cell};color:{_INK}">{e(_must_hear(agenda, topic))}</td>
</tr>"""


def render_invite_html(
    agenda: dict, *, title: str, start: datetime, end: datetime, join_url: str, discord_url: str
) -> str:
    e = html.escape
    topics = agenda.get("topics", [])
    rows = "".join(
        _topic_row(agenda, n, t, striped=n % 2 == 0) for n, t in enumerate(topics, start=1)
    )
    total = sum(int(t.get("budgetSeconds", 0)) for t in topics) // 60
    purpose = str(agenda.get("purpose", "")).strip()
    purpose_block = (
        f"""<tr><td style="padding:0 0 22px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
 style="border-left:3px solid {_ACCENT};background:{_WASH}">
<tr><td style="padding:12px 16px;font-size:16px;line-height:1.5;color:{_INK}">{e(purpose)}</td></tr>
</table></td></tr>"""
        if purpose
        else ""
    )
    head = f"padding:9px 14px;text-align:left;font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:{_DIM};background:{_WASH};border-bottom:1px solid {_LINE}"
    bullets = "".join(
        f'<li style="margin:0 0 6px">{b}</li>' for b in _HOW_IT_RUNS
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
<body style="margin:0;padding:0;background:#eef1f6">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eef1f6">
<tr><td align="center" style="padding:28px 12px">
<table role="presentation" width="640" cellpadding="0" cellspacing="0"
 style="width:640px;max-width:100%;background:#ffffff;border:1px solid {_LINE};border-radius:12px;
 font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif">

<tr><td style="padding:26px 30px 0">
  <p style="margin:0 0 4px;font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:{_DIM}">
    Meeting invitation</p>
  <h1 style="margin:0;font-size:23px;line-height:1.25;color:{_INK};font-weight:700">{e(title)}</h1>
  <p style="margin:8px 0 0;font-size:15px;color:{_DIM}">{e(_when(start, end))} &nbsp;·&nbsp;
    {total} min on the agenda</p>
</td></tr>

<tr><td style="padding:22px 30px 0"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">
{purpose_block}
<tr><td>
  <p style="margin:0 0 8px;font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:{_DIM}">
    Agenda</p>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
   style="border:1px solid {_LINE};border-radius:8px;border-collapse:separate;overflow:hidden">
  <tr><th style="{head};width:26px"></th><th style="{head}">Topic</th>
      <th style="{head}">Time</th><th style="{head}">Owner</th>
      <th style="{head}">Must be heard</th></tr>
  {rows}
  </table>
</td></tr>
</table></td></tr>

<tr><td style="padding:22px 30px 0">
  <p style="margin:0 0 8px;font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:{_DIM}">
    How this meeting runs</p>
  <ul style="margin:0;padding-left:18px;font-size:15px;line-height:1.55;color:{_INK}">{bullets}</ul>
</td></tr>

<tr><td style="padding:24px 30px 28px">
  <a href="{e(discord_url)}" style="display:inline-block;padding:11px 22px;border-radius:8px;
   background:{_ACCENT};color:#ffffff;font-size:15px;font-weight:600;text-decoration:none">Join the call</a>
  <a href="{e(join_url)}" style="display:inline-block;margin-left:14px;padding:11px 0;
   color:{_ACCENT};font-size:15px;font-weight:600;text-decoration:none">Agenda &amp; live status →</a>
  <p style="margin:18px 0 0;font-size:12px;color:{_DIM}">
    The calendar invite is attached. Chaired by Karen · gavel</p>
</td></tr>

</table></td></tr></table></body></html>"""
