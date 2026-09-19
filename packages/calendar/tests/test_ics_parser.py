from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gavel_calendar.ics_parser import InvalidInvite, parse_ics, parse_topics

GOOGLE_STYLE = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//Google Inc//Google Calendar 70.9054//EN\r\n"
    "BEGIN:VEVENT\r\n"
    "UID:abc123@google.com\r\n"
    "DTSTAMP:20260918T120000Z\r\n"
    "DTSTART:20260920T140000Z\r\n"
    "DTEND:20260920T143000Z\r\n"
    "SUMMARY:Launch readiness\r\n"
    "ORGANIZER;CN=Vitaly:mailto:vitaly@example.com\r\n"
    "ATTENDEE;CN=Vitaly;PARTSTAT=ACCEPTED;CUTYPE=INDIVIDUAL:mailto:vitaly@examp\r\n"
    " le.com\r\n"
    "ATTENDEE;CN=Ana;PARTSTAT=NEEDS-ACTION:mailto:ana@example.com\r\n"
    "DESCRIPTION:Agenda:\\n- Pricing — 10m (owner: Ana)\\n- Rollout plan (5 min)\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)

# Outlook: TZID-qualified times, a VTIMEZONE block, REQ-PARTICIPANT roles, a
# numbered agenda.
OUTLOOK_STYLE = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//Microsoft Corporation//Outlook 16.0//EN\r\n"
    "BEGIN:VTIMEZONE\r\n"
    "TZID:Europe/Madrid\r\n"
    "BEGIN:STANDARD\r\n"
    "DTSTART:19701025T030000\r\n"
    "TZOFFSETFROM:+0200\r\n"
    "TZOFFSETTO:+0100\r\n"
    "END:STANDARD\r\n"
    "BEGIN:DAYLIGHT\r\n"
    "DTSTART:19700329T020000\r\n"
    "TZOFFSETFROM:+0100\r\n"
    "TZOFFSETTO:+0200\r\n"
    "END:DAYLIGHT\r\n"
    "END:VTIMEZONE\r\n"
    "BEGIN:VEVENT\r\n"
    "UID:000000-outlook@example.com\r\n"
    "DTSTAMP:20260918T120000Z\r\n"
    "DTSTART;TZID=Europe/Madrid:20260920T160000\r\n"
    "DTEND;TZID=Europe/Madrid:20260920T163000\r\n"
    "SUMMARY:Launch readiness sync\r\n"
    'ORGANIZER;CN="Marc":mailto:marc@example.com\r\n'
    'ATTENDEE;CN="Marc";ROLE=CHAIR;PARTSTAT=ACCEPTED:mailto:marc@example.com\r\n'
    'ATTENDEE;CN="Artem";ROLE=REQ-PARTICIPANT:mailto:artem@example.com\r\n'
    "DESCRIPTION:1. Pricing (10 min)\\n2. Rollout plan (5 min)\\nSee the doc fo\r\n"
    " r background.\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)

HAND_WRITTEN = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:handwritten-1
DTSTART:20260920T090000
DTEND:20260920T093000
SUMMARY:Quick sync
ATTENDEE:mailto:vitaly@example.com
ATTENDEE:mailto:ana@example.com
DESCRIPTION:* Pricing - 10 minutes\\n* Rollout plan - 5 minutes (owner: Ana)\\nunrelated note, ignore me
END:VEVENT
END:VCALENDAR
"""


def test_google_style() -> None:
    invite = parse_ics(GOOGLE_STYLE)
    assert invite.title == "Launch readiness"
    assert invite.start == datetime(2026, 9, 20, 14, 0, tzinfo=UTC)
    assert invite.duration_seconds == 1800
    emails = {a.email for a in invite.attendees}
    assert emails == {"vitaly@example.com", "ana@example.com"}
    organizer = next(a for a in invite.attendees if a.email == "vitaly@example.com")
    assert organizer.is_organizer
    assert [t.title for t in invite.topics] == ["Pricing", "Rollout plan"]
    assert invite.topics[0].budget_seconds == 600
    assert invite.topics[0].owner_name == "Ana"
    assert invite.topics[1].budget_seconds == 300


def test_outlook_style_tzid_normalizes_to_utc() -> None:
    invite = parse_ics(OUTLOOK_STYLE)
    assert invite.title == "Launch readiness sync"
    # Europe/Madrid is UTC+2 in September (CEST) -> 16:00 local = 14:00 UTC.
    assert invite.start == datetime(2026, 9, 20, 14, 0, tzinfo=UTC)
    assert invite.start.tzinfo is UTC
    assert [t.title for t in invite.topics] == ["Pricing", "Rollout plan"]
    assert invite.topics[0].budget_seconds == 600
    assert invite.topics[1].budget_seconds == 300
    # The trailing prose line is not bulleted/numbered — ignored, not crashed on.
    assert all(t.title != "See the doc for background." for t in invite.topics)


def test_hand_written_floating_time_assumed_utc() -> None:
    invite = parse_ics(HAND_WRITTEN)
    assert invite.title == "Quick sync"
    assert invite.start == datetime(2026, 9, 20, 9, 0, tzinfo=UTC)
    assert [t.title for t in invite.topics] == ["Pricing", "Rollout plan"]
    assert invite.topics[1].owner_name == "Ana"
    # No CN param anywhere — names fall back to the email's local part.
    names = {a.name for a in invite.attendees}
    assert names == {"Vitaly", "Ana"}


def test_no_vevent_raises_invalid_invite() -> None:
    with pytest.raises(InvalidInvite):
        parse_ics("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nEND:VCALENDAR\r\n")


def test_garbage_input_raises_invalid_invite_not_some_other_exception() -> None:
    with pytest.raises(InvalidInvite):
        parse_ics(b"this is not an ics file at all")


@pytest.mark.parametrize(
    "line",
    [
        "just some prose with no bullet",
        "",
        "   ",
        "Agenda:",
    ],
)
def test_parse_topics_ignores_non_topic_lines(line: str) -> None:
    assert parse_topics(line) == []


def test_parse_topics_handles_missing_duration() -> None:
    topics = parse_topics("- Open floor")
    assert len(topics) == 1
    assert topics[0].title == "Open floor"
    assert topics[0].budget_seconds is None
    assert topics[0].owner_name is None


def test_must_hear_and_owner_order_free_in_same_group() -> None:
    topics = parse_topics("- Pricing — 10m (must hear: Marc, Ana, owner: Vitaly)")
    assert len(topics) == 1
    assert topics[0].title == "Pricing"
    assert topics[0].owner_name == "Vitaly"
    assert topics[0].must_hear_names == ["Marc", "Ana"]


def test_must_hear_alone_without_owner() -> None:
    topics = parse_topics("- Open floor (must hear: Ana)")
    assert topics[0].owner_name is None
    assert topics[0].must_hear_names == ["Ana"]


def test_goal_and_repeatable_questions_attach_to_preceding_topic() -> None:
    description = (
        "- Pricing — 10m (owner: Ana)\n"
        "  goal: one honest number per region\n"
        "  q: what breaks if we wait a week?\n"
        "  q: who signs off?\n"
        "- Rollout plan - 5 minutes\n"
    )
    topics = parse_topics(description)
    assert [t.title for t in topics] == ["Pricing", "Rollout plan"]
    assert topics[0].goal == "one honest number per region"
    assert topics[0].questions == [
        "what breaks if we wait a week?",
        "who signs off?",
    ]
    # A goal/q line never attaches retroactively to an earlier topic once a new
    # bullet has started.
    assert topics[1].goal == ""
    assert topics[1].questions == []


def test_goal_and_questions_require_indentation_to_avoid_swallowing_prose() -> None:
    # Not indented -> not a goal/q continuation, just skipped like other prose.
    topics = parse_topics("- Pricing — 10m\ngoal: not indented, ignored\n")
    assert topics[0].goal == ""
