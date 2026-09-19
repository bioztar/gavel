"""Turn a raw `.ics` invite into a `ParsedInvite`: title, start, end, attendees,
and draft topics scraped from the description.

Uses `icalendar` for the RFC 5545 mechanics (folded lines, `TZID=`, escaped
text) rather than hand-rolling them — that is the part that differs between
Google, Outlook and a hand-written invite, and `python-dateutil`'s `rruleset`
for recurrence expansion (`parse_ics_occurrences`), for the same reason.
Topic-line parsing is ours: it tries a few shapes and skips anything it does
not recognize. It must never raise on a real-world invite; `InvalidInvite` is
only for an .ics with no usable event at all.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from typing import Any

from dateutil.rrule import rrule as dateutil_rrule
from dateutil.rrule import rruleset, rrulestr
from icalendar import Calendar
from icalendar.prop import vCalAddress, vRecur

# An RRULE with neither COUNT nor UNTIL is infinite. Expansion is bounded by the
# caller's query window first, and by this per-event cap second — a feed that
# asks for a decade-wide window, or one minute-ly event, still cannot make the
# poller generate an unbounded number of occurrences.
MAX_OCCURRENCES_PER_EVENT = 500


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
    uid: str = ""
    # Stable, deterministic identity of *this* occurrence: the bare `UID` for a
    # single event, `UID::<original start, UTC basic form>` for one instance of a
    # recurring series. Callers key stored meetings on this (see
    # `scheduler._session_id_for`), so re-polling a series never duplicates it.
    occurrence_uid: str = ""

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


def _calendar_from(raw: bytes | str) -> Calendar:
    try:
        return Calendar.from_ical(raw)
    except Exception as exc:  # icalendar raises several different error types
        raise InvalidInvite(f"could not parse .ics: {exc}") from exc


def _events_of(cal: Calendar) -> list[Any]:
    events = [c for c in cal.walk() if c.name == "VEVENT"]
    if not events:
        raise InvalidInvite("no VEVENT in this .ics")
    return events


def _parse_event(event: Any) -> ParsedInvite:
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
    uid = str(event.get("uid", "")).strip()

    return ParsedInvite(
        title=title,
        start=start,
        end=end,
        attendees=attendees,
        topics=topics,
        description=description,
        uid=uid,
        occurrence_uid=uid,
    )


def parse_ics(raw: bytes | str) -> ParsedInvite:
    """The first VEVENT of an .ics, as a single occurrence at its own DTSTART.

    This is the `POST /invite` path: someone hands us one invite. Recurrence is
    not expanded here — `parse_ics_occurrences` does that, for the feed poller.
    """
    return _parse_event(_events_of(_calendar_from(raw))[0])


# --- recurrence --------------------------------------------------------------------
#
# The recurrence maths is `python-dateutil`'s (`rruleset`), never ours. What is
# ours is translating one VEVENT's properties into it correctly:
#
#   * DTSTART sets the "space" every other date is read in. A TZID-qualified
#     DTSTART expands in its own zone (so a weekly 09:00 standup stays 09:00
#     local across a DST change), a floating or all-day DTSTART expands naive
#     and is read as UTC on the way out — same rule `_to_utc` already applies.
#   * UNTIL is UTC-anchored even when DTSTART is not, and RDATE/EXDATE may be
#     DATE-valued against a datetime DTSTART. `_aligned` moves each of them into
#     DTSTART's space, which is also what dateutil requires (it refuses to mix
#     naive and aware datetimes).
#   * A RECURRENCE-ID VEVENT is an override: it *replaces* the generated
#     instance whose start it names, wherever the override itself was moved to.


def _aligned(value: datetime | date, reference: datetime) -> datetime:
    """One RRULE/RDATE/EXDATE/UNTIL/RECURRENCE-ID value, in DTSTART's space."""
    if not isinstance(value, datetime):
        value = datetime.combine(value, time.min)
    if reference.tzinfo is None:
        return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value
    return value if value.tzinfo else value.replace(tzinfo=reference.tzinfo)


def _local_dtstart(event: Any) -> datetime:
    dtstart = event.get("dtstart")
    if dtstart is None:
        raise InvalidInvite("event has no DTSTART")
    value = dtstart.dt
    if not isinstance(value, datetime):
        # All-day (VALUE=DATE): expand over naive midnights, land on UTC
        # midnight, exactly as `_to_utc` reads a bare DATE.
        return datetime.combine(value, time.min)
    return value


def _as_list(value: object) -> list[Any]:
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


def _date_values(value: object) -> list[datetime | date]:
    """The dates in an RDATE/EXDATE property (each holds one or many)."""
    return [entry.dt for prop in _as_list(value) for entry in getattr(prop, "dts", [])]


def _rrule_text(recur: Any, dtstart: datetime) -> str:
    values = dict(recur)
    until = values.get("UNTIL")
    if until:
        values["UNTIL"] = [_aligned(u, dtstart) for u in _as_list(until)]
    return vRecur(values).to_ical().decode()


def _rule_set(event: Any, dtstart: datetime) -> rruleset:
    rules = rruleset()
    for recur in _as_list(event.get("rrule")):
        rule = rrulestr(_rrule_text(recur, dtstart), dtstart=dtstart)
        if not isinstance(rule, dateutil_rrule):
            # `rrulestr` only returns a set for multi-property input; one RRULE
            # line is always a single rule.
            raise InvalidInvite("unsupported RRULE")
        rules.rrule(rule)
    for value in _date_values(event.get("rdate")):
        rules.rdate(_aligned(value, dtstart))
    for value in _date_values(event.get("exdate")):
        rules.exdate(_aligned(value, dtstart))
    return rules


def _is_recurring(event: Any) -> bool:
    return bool(event.get("rrule") or event.get("rdate"))


def _occurrence_uid(uid: str, start: datetime) -> str:
    return f"{uid}::{start.astimezone(UTC):%Y%m%dT%H%M%SZ}"


def parse_ics_occurrences(
    raw: bytes | str,
    *,
    window_start: datetime,
    window_end: datetime,
    max_occurrences: int = MAX_OCCURRENCES_PER_EVENT,
) -> list[ParsedInvite]:
    """Every occurrence of the .ics's event that starts inside the window.

    One `.ics` here means one event: a master VEVENT plus any RECURRENCE-ID
    VEVENTs overriding single instances of it (that is how a feed carries a
    series). A non-recurring event yields at most one invite — itself — so this
    is a superset of `parse_ics`, and the old path is the one-occurrence case of
    the new one rather than a second code path.

    Occurrences come back in start order, each with a distinct, deterministic
    `occurrence_uid`.
    """
    events = _events_of(_calendar_from(raw))
    masters = [e for e in events if e.get("recurrence-id") is None]
    if not masters:
        # Overrides with no master in the same .ics: nothing to expand against,
        # so each stands on its own at the time it was moved to.
        return sorted(
            (p for p in map(_parse_event, events) if window_start <= p.start <= window_end),
            key=lambda p: p.start,
        )

    master = masters[0]
    base = _parse_event(master)
    if not _is_recurring(master):
        return [base] if window_start <= base.start <= window_end else []

    dtstart = _local_dtstart(master)
    duration = base.end - base.start
    overrides = {
        _to_utc(_aligned(event["recurrence-id"].dt, dtstart)): event
        for event in events
        if event.get("recurrence-id") is not None
    }

    occurrences: list[ParsedInvite] = []
    rules = _rule_set(master, dtstart)
    # `count=` is the runaway guard: an RRULE with no COUNT and no UNTIL is
    # infinite, and `xafter` is lazy, so nothing past the cap is ever generated.
    for local_start in rules.xafter(
        _aligned(window_start, dtstart), count=max_occurrences, inc=True
    ):
        start = _to_utc(local_start)
        if start > window_end:
            break
        if start in overrides:
            continue  # replaced below, at wherever the override moved it to
        occurrences.append(
            dataclasses.replace(
                base,
                start=start,
                end=start + duration,
                occurrence_uid=_occurrence_uid(base.uid, start),
            )
        )

    for original_start, event in overrides.items():
        moved = _parse_event(event)
        if not (window_start <= moved.start <= window_end):
            continue
        # Keyed on the instance's *original* start, not the new one: the moved
        # instance is the same meeting as the one it replaced, so it must land
        # on the same id — both against the generated occurrence it supersedes
        # and against an earlier poll that saw it before it moved.
        occurrences.append(
            dataclasses.replace(
                moved,
                end=moved.end if event.get("dtend") is not None else moved.start + duration,
                occurrence_uid=_occurrence_uid(base.uid, original_start),
            )
        )

    occurrences.sort(key=lambda p: p.start)
    return occurrences[:max_occurrences]
