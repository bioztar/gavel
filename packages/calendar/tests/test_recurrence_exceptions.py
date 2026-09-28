"""Recurrence exceptions: cancelled instances, DURATION, UTC EXDATE, RDATE,
`RANGE=THISANDFUTURE` — every fixture straddles the Europe/Madrid DST change on
2026-03-29 so a wall-clock/UTC mix-up would show up as a missed exception.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from gavel_calendar.ics_parser import parse_ics_occurrences

FIXTURES = Path(__file__).parent / "fixtures"
WINDOW = (datetime(2026, 3, 16, tzinfo=UTC), datetime(2026, 4, 12, tzinfo=UTC))


def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def _occurrences(name: str) -> list:
    return parse_ics_occurrences(
        (FIXTURES / name).read_bytes(), window_start=WINDOW[0], window_end=WINDOW[1]
    )


def test_cancelled_override_drops_exactly_that_instance() -> None:
    # The cancelled Monday is the first one after the DST change (09:30 CEST =
    # 07:30Z); its neighbours on either side of the boundary survive.
    starts = [o.start for o in _occurrences("cancelled_instance.ics")]
    assert starts == [
        _utc(2026, 3, 16, 8, 30),
        _utc(2026, 3, 23, 8, 30),
        _utc(2026, 4, 6, 7, 30),
    ]


def test_cancelled_master_yields_no_occurrences() -> None:
    raw = (FIXTURES / "weekly_standup.ics").read_bytes().replace(
        b"SUMMARY:", b"STATUS:CANCELLED\nSUMMARY:"
    )
    assert parse_ics_occurrences(raw, window_start=WINDOW[0], window_end=WINDOW[1]) == []


def test_duration_sets_the_end_and_a_utc_exdate_hits_a_local_instance() -> None:
    occurrences = _occurrences("duration_exdate_utc.ics")
    assert [o.start for o in occurrences] == [
        _utc(2026, 3, 16, 8, 30),
        _utc(2026, 3, 23, 8, 30),
        _utc(2026, 4, 6, 7, 30),  # 2026-03-30 excluded via EXDATE:20260330T073000Z
    ]
    assert {o.duration_seconds for o in occurrences} == {45 * 60}


def test_rdate_adds_an_extra_instance_with_its_own_id() -> None:
    occurrences = _occurrences("rdate_extra.ics")
    extra = [o for o in occurrences if o.start == _utc(2026, 4, 1, 14, 0)]
    assert len(extra) == 1
    assert extra[0].occurrence_uid == "rdate-series@example.com::20260401T140000Z"
    assert extra[0].duration_seconds == 30 * 60
    assert [o.start for o in occurrences] == sorted(o.start for o in occurrences)


def test_this_and_future_shifts_the_named_instance_and_all_later_ones() -> None:
    occurrences = _occurrences("this_and_future.ics")
    assert [(o.start, o.title, o.duration_seconds) for o in occurrences] == [
        (_utc(2026, 3, 16, 8, 30), "Sync", 1800),
        (_utc(2026, 3, 23, 8, 30), "Sync", 1800),
        (_utc(2026, 3, 30, 9, 0), "Sync (later slot)", 2700),  # 11:00 CEST
        (_utc(2026, 4, 6, 9, 0), "Sync (later slot)", 2700),
    ]
    # Ids stay keyed on the generated instance the override replaced.
    assert [o.occurrence_uid.split("::")[1] for o in occurrences] == [
        "20260316T083000Z",
        "20260323T083000Z",
        "20260330T073000Z",
        "20260406T073000Z",
    ]
