from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from gavel_calendar.agenda import build_agenda
from gavel_calendar.ics_parser import InviteAttendee, ParsedInvite, TopicDraft, parse_ics
from gavel_calendar.ics_writer import build_ics

TZ = ZoneInfo("Europe/Madrid")


def _invite() -> ParsedInvite:
    start = datetime(2026, 9, 20, 15, 0, tzinfo=TZ)
    return ParsedInvite(
        title="Pricing sync",
        start=start,
        end=start.replace(hour=15, minute=30),
        attendees=[
            InviteAttendee(email="vitaly.alt@gmail.com", name="Vitaly", is_organizer=True),
            InviteAttendee(email="a.shambalev@gmail.com", name="Artem", is_organizer=False),
        ],
        topics=[
            TopicDraft(
                title="Pricing",
                budget_seconds=600,
                owner_name="Vitaly",
                must_hear_names=["Artem"],
            ),
            TopicDraft(title="Launch date", budget_seconds=1200, owner_name=None),
        ],
        description="Decide the numbers before the call with the investor.",
    )


def test_ics_round_trips_through_our_own_parser() -> None:
    invite = _invite()
    agenda = build_agenda(invite, "sess-1", {})

    attendee_pairs = [(a.name, a.email) for a in invite.attendees]
    ics_bytes = build_ics(
        session_id="sess-1",
        title=invite.title,
        start=invite.start,
        end=invite.end,
        agenda=agenda,
        attendees=attendee_pairs,
        organizer_email="vitaly.alt@gmail.com",
        organizer_name="Vitaly",
        discord_url="https://discordapp.com/channels/1/2",
        join_url="http://localhost:8790/m/sess-1",
    )

    reparsed = parse_ics(ics_bytes)
    agenda_again = build_agenda(reparsed, "sess-2", {})

    assert agenda_again["purpose"] == agenda["purpose"]
    assert agenda_again["totalSeconds"] == agenda["totalSeconds"]
    assert agenda_again["attendees"] == agenda["attendees"]
    assert agenda_again["topics"] == agenda["topics"]
    assert reparsed.start == invite.start
    assert reparsed.end == invite.end
    assert reparsed.title == invite.title


def test_ics_round_trip_with_uneven_split_and_no_must_hear() -> None:
    """The split that motivated the whole-minute rule: 3 topics, 2 with no
    stated duration, splitting 45 total minutes as 15/15/15 — every value a
    clean multiple of 60 seconds so `budgetSeconds // 60` never truncates.
    """
    start = datetime(2026, 9, 21, 9, 0, tzinfo=TZ)
    invite = ParsedInvite(
        title="Standup",
        start=start,
        end=start.replace(minute=45),
        attendees=[InviteAttendee(email="solo@example.com", name="Solo", is_organizer=True)],
        topics=[
            TopicDraft(title="A", budget_seconds=900, owner_name=None),
            TopicDraft(title="B", budget_seconds=None, owner_name=None),
            TopicDraft(title="C", budget_seconds=None, owner_name=None),
        ],
        description="Quick one.",
    )
    agenda = build_agenda(invite, "sess-3", {})
    assert [t["budgetSeconds"] for t in agenda["topics"]] == [900, 900, 900]

    ics_bytes = build_ics(
        session_id="sess-3",
        title=invite.title,
        start=invite.start,
        end=invite.end,
        agenda=agenda,
        attendees=[("Solo", "solo@example.com")],
        organizer_email="solo@example.com",
        organizer_name="Solo",
        discord_url="https://discordapp.com/channels/1/2",
        join_url="http://localhost:8790/m/sess-3",
    )
    reparsed = parse_ics(ics_bytes)
    agenda_again = build_agenda(reparsed, "sess-4", {})
    assert agenda_again["topics"] == agenda["topics"]
