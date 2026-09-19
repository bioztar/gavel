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

import dataclasses
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
    must_hear_names: list[str] = field(default_factory=list)
    goal: str = ""
    questions: list[str] = field(default_factory=list)


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
#   "- Pricing — 10m (owner: Ana, must hear: Marc, Ana)"  # owner/must hear, order-free
# and, on their own indented line(s) right after a topic:
#   "  goal: one honest number per region"
#   "  q: what breaks if we wait a week?"                # repeatable
# Anything that is not a bulleted/numbered line, and not a goal/q continuation of
# the topic just above it, is not a topic and is skipped.

_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.*\S)\s*$")
_OWNER_OR_MUST_HEAR_GROUP_RE = re.compile(r"\(([^)]*(?:owner|must\s*hear)[^)]*)\)", re.IGNORECASE)
_KEY_SPLIT_RE = re.compile(r"(?=owner\s*:|must\s*hear\s*:)", re.IGNORECASE)
_DASH_MIN_RE = re.compile(r"[—\-–]\s*(\d+)\s*m(?:in(?:ute)?s?)?\b", re.IGNORECASE)  # noqa: RUF001
_PAREN_MIN_RE = re.compile(r"\(\s*(\d+)\s*min(?:ute)?s?\s*\)", re.IGNORECASE)
_BARE_MIN_RE = re.compile(r"\b(\d+)\s*min(?:ute)?s?\b", re.IGNORECASE)
_GOAL_RE = re.compile(r"^\s+goal\s*:\s*(.*\S)\s*$", re.IGNORECASE)
_QUESTION_RE = re.compile(r"^\s+q(?:uestions?)?\s*:\s*(.*\S)\s*$", re.IGNORECASE)


def _owner_and_must_hear(body: str) -> tuple[str, str | None, list[str]]:
    """Pulls an "(owner: ..., must hear: ...)" group out of a topic line, both
    keys optional and order-free, and returns the body with that group removed.
    """
    match = _OWNER_OR_MUST_HEAR_GROUP_RE.search(body)
    if not match:
        return body, None, []

    owner_name: str | None = None
    must_hear: list[str] = []
    for chunk in _KEY_SPLIT_RE.split(match.group(1)):
        chunk = chunk.strip().strip(",").strip()
        if not chunk:
            continue
        key, _, value = chunk.partition(":")
        value = value.strip().strip(",").strip()
        normalized_key = key.strip().lower().replace(" ", "")
        if normalized_key == "owner":
            owner_name = value or None
        elif normalized_key == "musthear":
            must_hear = [name.strip() for name in value.split(",") if name.strip()]

    body = body[: match.start()] + body[match.end() :]
    return body, owner_name, must_hear


def parse_topics(description: str) -> list[TopicDraft]:
    topics: list[TopicDraft] = []
    for raw_line in description.splitlines():
        bullet = _BULLET_RE.match(raw_line)
        if not bullet:
            if topics:
                goal_match = _GOAL_RE.match(raw_line)
                if goal_match:
                    topics[-1] = dataclasses.replace(topics[-1], goal=goal_match.group(1).strip())
                    continue
                question_match = _QUESTION_RE.match(raw_line)
                if question_match:
                    topics[-1] = dataclasses.replace(
                        topics[-1],
                        questions=[*topics[-1].questions, question_match.group(1).strip()],
                    )
                    continue
            continue

        body = bullet.group(1)
        body, owner_name, must_hear_names = _owner_and_must_hear(body)

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
                must_hear_names=must_hear_names,
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
