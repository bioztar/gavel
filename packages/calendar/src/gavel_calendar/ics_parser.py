"""Turn a raw `.ics` invite into a `ParsedInvite`: title, start, end, attendees,
and draft topics scraped from the description.

Uses `icalendar` for the RFC 5545 mechanics (folded lines, `TZID=`, escaped
text) rather than hand-rolling them — that is the part that differs between
Google, Outlook and a hand-written invite. Topic-line parsing is ours: it
tries a few shapes and skips anything it does not recognize. It must never
raise on a real-world invite; `InvalidInvite` is only for an .ics with no
usable event at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time

from icalendar import Calendar
from icalendar.prop import vCalAddress


class InvalidInvite(ValueError):
    """The .ics has no VEVENT, or the event has no usable start/end/title."""


@dataclass(frozen=True)
class InviteAttendee:
    email: str
    name: str
    is_organizer: bool = False


@dataclass(frozen=True)
class TopicDraft:
    title: str
    budget_seconds: int | None
    owner_name: str | None


@dataclass(frozen=True)
class ParsedInvite:
    title: str
    start: datetime
    end: datetime
    attendees: list[InviteAttendee]
    topics: list[TopicDraft] = field(default_factory=list)
    description: str = ""

    @property
    def duration_seconds(self) -> int:
        return max(int((self.end - self.start).total_seconds()), 0)


# --- topic lines -----------------------------------------------------------------
#
# Accepted shapes (a few, on purpose — real invites vary):
#   "- Pricing — 10m (owner: Artem)"
#   "1. Pricing (10 min)"
#   "* Pricing - 10 minutes"
# Anything that is not a bulleted/numbered line is not a topic and is skipped.

_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.*\S)\s*$")
_OWNER_RE = re.compile(r"\(\s*owner\s*:\s*([^)]+?)\s*\)", re.IGNORECASE)
_DASH_MIN_RE = re.compile(r"[—\-–]\s*(\d+)\s*m(?:in(?:ute)?s?)?\b", re.IGNORECASE)  # noqa: RUF001
_PAREN_MIN_RE = re.compile(r"\(\s*(\d+)\s*min(?:ute)?s?\s*\)", re.IGNORECASE)
_BARE_MIN_RE = re.compile(r"\b(\d+)\s*min(?:ute)?s?\b", re.IGNORECASE)


def parse_topics(description: str) -> list[TopicDraft]:
    topics: list[TopicDraft] = []
    for raw_line in description.splitlines():
        bullet = _BULLET_RE.match(raw_line)
        if not bullet:
            continue
        body = bullet.group(1)

        owner_name: str | None = None
        owner_match = _OWNER_RE.search(body)
        if owner_match:
            owner_name = owner_match.group(1).strip()
            body = _OWNER_RE.sub("", body)

        minutes: int | None = None
        for pattern in (_DASH_MIN_RE, _PAREN_MIN_RE, _BARE_MIN_RE):
            match = pattern.search(body)
            if match:
                minutes = int(match.group(1))
                body = pattern.sub("", body, count=1)
                break

        title = body.strip(" \t-–—:")  # noqa: RUF001
        if not title:
            continue
        topics.append(
            TopicDraft(
                title=title,
                budget_seconds=minutes * 60 if minutes is not None else None,
                owner_name=owner_name,
            )
        )
    return topics


# --- the .ics itself ---------------------------------------------------------------


def _to_utc(value: datetime | date) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            # Floating time — no TZID, no Z. Treated as UTC; documented in the README.
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    # All-day / date-only value (VALUE=DATE): midnight UTC.
    return datetime.combine(value, time.min, tzinfo=UTC)


def _addresses(value: object) -> list[vCalAddress]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]  # type: ignore[list-item]


def _attendee_name(addr: vCalAddress, email: str) -> str:
    cn = addr.params.get("CN")
    if cn:
        return str(cn)
    return email.split("@")[0].replace(".", " ").replace("_", " ").title()


def _email(addr: vCalAddress) -> str:
    return str(addr).removeprefix("mailto:").removeprefix("MAILTO:").strip().lower()


def parse_ics(raw: bytes | str) -> ParsedInvite:
    try:
        cal = Calendar.from_ical(raw)
    except Exception as exc:  # icalendar raises several different error types
        raise InvalidInvite(f"could not parse .ics: {exc}") from exc

    events = [c for c in cal.walk() if c.name == "VEVENT"]
    if not events:
        raise InvalidInvite("no VEVENT in this .ics")
    event = events[0]

    dtstart = event.get("dtstart")
    dtend = event.get("dtend")
    if dtstart is None:
        raise InvalidInvite("event has no DTSTART")
    start = _to_utc(dtstart.dt)
    end = _to_utc(dtend.dt) if dtend is not None else start

    title = str(event.get("summary", "")).strip() or "Untitled meeting"

    organizer_email = None
    organizer = event.get("organizer")
    if organizer is not None:
        organizer_email = _email(organizer)

    attendees: list[InviteAttendee] = []
    seen_emails: set[str] = set()
    for addr in _addresses(event.get("attendee")):
        email = _email(addr)
        if not email or email in seen_emails:
            continue
        seen_emails.add(email)
        attendees.append(
            InviteAttendee(
                email=email,
                name=_attendee_name(addr, email),
                is_organizer=(email == organizer_email),
            )
        )

    description = str(event.get("description", ""))
    topics = parse_topics(description)

    return ParsedInvite(
        title=title,
        start=start,
        end=end,
        attendees=attendees,
        topics=topics,
        description=description,
    )
