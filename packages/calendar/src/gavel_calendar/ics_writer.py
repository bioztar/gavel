"""A contract agenda → a `.ics` invite that our own `ics_parser.parse_ics`
reads back to the same agenda — see `tests/test_ics_writer.py`'s round trip.

The `DESCRIPTION` we write is built from the *already-built* agenda (post
`agenda.py:_budget_seconds` split), not the raw form input: every topic's
budget is by then a whole number of seconds, so `budgetSeconds // 60` never
truncates and the number that comes back out of a re-parse is the one that
went in. `compose.py` is responsible for handing every topic an explicit
whole-minute duration before calling `build_agenda`, precisely so this holds.
"""

from __future__ import annotations

from datetime import UTC, datetime

from icalendar import Calendar, Event
from icalendar.prop import vCalAddress, vText

from .agenda import attendee_name


def _topic_line(agenda: dict, topic: dict) -> str:
    minutes = topic["budgetSeconds"] // 60
    owner = attendee_name(agenda, topic.get("owner"))
    must_hear = [attendee_name(agenda, i) for i in topic.get("mustHear", [])]
    line = f"- {topic['title']} — {minutes}m"
    parts = []
    if owner:
        parts.append(f"owner: {owner}")
    if must_hear:
        parts.append(f"must hear: {', '.join(must_hear)}")
    if parts:
        line += f" ({', '.join(parts)})"
    return line


def _description(agenda: dict, join_url: str) -> str:
    lines: list[str] = []
    purpose = str(agenda.get("purpose", "")).strip()
    if purpose:
        lines.append(purpose)
        lines.append("")
    lines.append("Agenda:")
    lines.extend(_topic_line(agenda, topic) for topic in agenda["topics"])
    lines.append("")
    lines.append(f"Join: {join_url}")
    return "\n".join(lines)


def build_ics(
    *,
    session_id: str,
    title: str,
    start: datetime,
    end: datetime,
    agenda: dict,
    attendees: list[tuple[str, str]],
    organizer_email: str,
    organizer_name: str,
    discord_url: str,
    join_url: str,
) -> bytes:
    """`attendees` and `organizer_email` are real addresses, kept separate
    from the agenda's `discordId`s: those default to email but may be
    Discord snowflakes once `CALENDAR_ATTENDEE_MAP` maps someone, and a
    snowflake is not a mailable address.
    """
    cal = Calendar()
    cal.add("prodid", "-//gavel//compose//EN")
    cal.add("version", "2.0")
    cal.add("method", "REQUEST")

    event = Event()
    event.add("uid", f"gavel-compose-{session_id}@gavel.invalid")
    event.add("dtstamp", datetime.now(UTC))
    event.add("dtstart", start)
    event.add("dtend", end)
    event.add("summary", title)
    event.add("location", discord_url)
    event.add("description", _description(agenda, join_url))

    organizer = vCalAddress(f"mailto:{organizer_email}")
    organizer.params["cn"] = vText(organizer_name)
    event["organizer"] = organizer

    for name, email in attendees:
        addr = vCalAddress(f"mailto:{email}")
        addr.params["cn"] = vText(name)
        addr.params["role"] = vText("REQ-PARTICIPANT")
        event.add("attendee", addr)

    cal.add_component(event)
    return cal.to_ical()
