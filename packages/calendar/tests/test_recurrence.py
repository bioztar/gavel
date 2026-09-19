"""Recurrence expansion: `RRULE`/`RDATE`/`EXDATE` inside a query window.

Every case reads a local fixture under `tests/fixtures/` — no network, and no
real feed URL anywhere (a feed URL is a credential; see the package README).
Windows and expected datetimes are fixed dates, never "now", so the assertions
are exact.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from gavel_calendar.ics_parser import (
    MAX_OCCURRENCES_PER_EVENT,
    parse_ics,
    parse_ics_occurrences,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def _occurrences(
    name: str,
    window_start: datetime,
    window_end: datetime,
    **kwargs: int,
) -> list:
    raw = (FIXTURES / name).read_bytes()
    return parse_ics_occurrences(raw, window_start=window_start, window_end=window_end, **kwargs)


def _starts(name: str, window_start: datetime, window_end: datetime) -> list[datetime]:
    return [o.start for o in _occurrences(name, window_start, window_end)]


def test_weekly_byday_standup_expands_inside_the_window() -> None:
    # DTSTART is 2026-01-05, months before the window — the bug this fixes is
    # that only that first occurrence was ever visible.
    starts = _starts("weekly_standup.ics", _utc(2026, 3, 2), _utc(2026, 3, 8, 23, 59))
    assert starts == [
        _utc(2026, 3, 2, 8, 30),  # Mon 09:30 CET (+01:00)
        _utc(2026, 3, 4, 8, 30),  # Wed
    ]


def test_weekly_standup_keeps_local_wall_time_across_a_dst_change() -> None:
    # Europe/Madrid goes to CEST on 2026-03-29: 09:30 local is 08:30Z before it
    # and 07:30Z after. The wall time is what stays fixed, not the UTC offset.
    starts = _starts("weekly_standup.ics", _utc(2026, 3, 23), _utc(2026, 4, 2))
    assert starts == [
        _utc(2026, 3, 23, 8, 30),
        _utc(2026, 3, 25, 8, 30),
        _utc(2026, 3, 30, 7, 30),
        _utc(2026, 4, 1, 7, 30),
    ]


def test_weekly_standup_occurrence_carries_the_series_details() -> None:
    occurrence = _occurrences("weekly_standup.ics", _utc(2026, 3, 2), _utc(2026, 3, 3))[0]
    assert occurrence.title == "Daily-ish standup"
    assert occurrence.duration_seconds == 900  # 15 minutes, same as the master
    assert [t.title for t in occurrence.topics] == ["Blockers", "Demo prep"]
    assert {a.email for a in occurrence.attendees} == {"vitaly@example.com", "ana@example.com"}


def test_monthly_expands_one_occurrence_per_month() -> None:
    starts = _starts("monthly_review.ics", _utc(2026, 3, 1), _utc(2026, 6, 1))
    assert starts == [
        _utc(2026, 3, 15, 13, 0),  # 14:00 CET
        _utc(2026, 4, 15, 12, 0),  # 14:00 CEST
        _utc(2026, 5, 15, 12, 0),
    ]


def test_count_and_interval_stop_the_series() -> None:
    # FREQ=DAILY;INTERVAL=2;COUNT=3 from a floating DTSTART (read as UTC).
    starts = _starts("count_interval.ics", _utc(2026, 3, 1), _utc(2026, 4, 1))
    assert starts == [
        _utc(2026, 3, 2, 10, 0),
        _utc(2026, 3, 4, 10, 0),
        _utc(2026, 3, 6, 10, 0),
    ]


def test_until_is_utc_anchored_against_a_tzid_dtstart() -> None:
    # UNTIL=20260304T080000Z is exactly the 2026-03-04 09:00 CET instance, which
    # is inclusive — and the series stops there even though the window is wider.
    starts = _starts("until_utc.ics", _utc(2026, 3, 1), _utc(2026, 4, 1))
    assert starts == [
        _utc(2026, 3, 2, 8, 0),
        _utc(2026, 3, 3, 8, 0),
        _utc(2026, 3, 4, 8, 0),
    ]


def test_exdate_removes_exactly_that_occurrence() -> None:
    starts = _starts("exdate_series.ics", _utc(2026, 3, 1), _utc(2026, 4, 1))
    assert starts == [
        _utc(2026, 3, 2, 12, 0),
        _utc(2026, 3, 3, 12, 0),
        # 2026-03-04 is the EXDATE
        _utc(2026, 3, 5, 12, 0),
        _utc(2026, 3, 6, 12, 0),
    ]


def test_recurrence_id_override_replaces_the_generated_instance() -> None:
    occurrences = _occurrences(
        "recurrence_id_override.ics", _utc(2026, 3, 2), _utc(2026, 3, 16, 23, 59)
    )
    # Mondays Mar 2, 9, 16 — but the Mar 9 one was moved to Tue Mar 10 15:00
    # CET, and must appear once, there, not twice.
    assert [o.start for o in occurrences] == [
        _utc(2026, 3, 2, 10, 0),
        _utc(2026, 3, 10, 14, 0),
        _utc(2026, 3, 16, 10, 0),
    ]
    moved = occurrences[1]
    assert moved.title == "Weekly planning (moved to Tuesday)"
    assert moved.duration_seconds == 3600  # the override's own DTEND, not the series'
    assert [t.title for t in moved.topics] == ["Next week", "Moved-day catch-up"]
    # Keyed on the instance's original start, so it is the same meeting as the
    # generated occurrence it replaced.
    assert moved.occurrence_uid == "override-series@example.com::20260309T100000Z"


def test_all_day_recurring_lands_on_utc_midnight() -> None:
    occurrences = _occurrences("all_day_recurring.ics", _utc(2026, 3, 1), _utc(2026, 4, 1))
    assert [o.start for o in occurrences] == [
        _utc(2026, 3, 2),
        _utc(2026, 3, 9),
        _utc(2026, 3, 16),
        _utc(2026, 3, 23),
    ]
    assert occurrences[0].duration_seconds == 86400  # DTEND is the exclusive next date


def test_non_recurring_event_still_yields_itself_once() -> None:
    occurrences = _occurrences("single_event.ics", _utc(2026, 3, 1), _utc(2026, 4, 1))
    assert len(occurrences) == 1
    assert occurrences[0].start == _utc(2026, 3, 2, 14, 0)
    # The old single-event path is unchanged, and agrees with the new one.
    single = parse_ics((FIXTURES / "single_event.ics").read_bytes())
    assert single.start == occurrences[0].start
    assert single.occurrence_uid == occurrences[0].occurrence_uid == "single-event@example.com"


def test_non_recurring_event_outside_the_window_yields_nothing() -> None:
    assert _occurrences("single_event.ics", _utc(2026, 4, 1), _utc(2026, 4, 2)) == []


def test_occurrence_ids_are_distinct_deterministic_and_repeatable() -> None:
    window = (_utc(2026, 3, 2), _utc(2026, 3, 8, 23, 59))
    first = _occurrences("weekly_standup.ics", *window)
    again = _occurrences("weekly_standup.ics", *window)

    ids = [o.occurrence_uid for o in first]
    assert ids == [
        "standup@example.com::20260302T083000Z",
        "standup@example.com::20260304T083000Z",
    ]
    assert len(set(ids)) == len(ids)
    assert ids == [o.occurrence_uid for o in again]  # same poll twice, same ids
    assert all(o.uid == "standup@example.com" for o in first)


def test_endless_rrule_is_bounded_by_the_window() -> None:
    # FREQ=DAILY with no COUNT and no UNTIL, running since January.
    starts = _starts("infinite_daily.ics", _utc(2026, 3, 2), _utc(2026, 3, 4, 23, 59))
    assert starts == [
        _utc(2026, 3, 2, 6, 0),
        _utc(2026, 3, 3, 6, 0),
        _utc(2026, 3, 4, 6, 0),
    ]


def test_endless_rrule_is_also_bounded_by_the_per_event_cap() -> None:
    # A window far wider than any sane poll: the cap, not the window, is what
    # stops generation.
    occurrences = _occurrences(
        "infinite_daily.ics",
        _utc(2026, 3, 2),
        _utc(2126, 3, 2),
        max_occurrences=5,
    )
    assert len(occurrences) == 5
    assert occurrences[-1].start == _utc(2026, 3, 6, 6, 0)

    default_capped = _occurrences("infinite_daily.ics", _utc(2026, 3, 2), _utc(2126, 3, 2))
    assert len(default_capped) == MAX_OCCURRENCES_PER_EVENT


def test_window_bounds_are_inclusive_on_both_ends() -> None:
    starts = _starts("infinite_daily.ics", _utc(2026, 3, 2, 6, 0), _utc(2026, 3, 3, 6, 0))
    assert starts == [_utc(2026, 3, 2, 6, 0), _utc(2026, 3, 3, 6, 0)]

    just_inside = _starts(
        "infinite_daily.ics",
        _utc(2026, 3, 2, 6, 0) + timedelta(seconds=1),
        _utc(2026, 3, 3, 6, 0) - timedelta(seconds=1),
    )
    assert just_inside == []
