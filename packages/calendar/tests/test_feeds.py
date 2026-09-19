"""The feed poller: fetch → walk VEVENTs → same ics_parser/agenda path as
POST /invite. No network — pytest-httpx stubs every httpx.AsyncClient call,
same technique test_scheduler.py uses for the ears calls.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
from icalendar import Calendar
from pytest_httpx import HTTPXMock

from gavel_calendar.feed_store import FeedRegistry
from gavel_calendar.ics_parser import parse_ics
from gavel_calendar.scheduler import _single_event_ics, poll_feeds_once
from gavel_calendar.store import InviteStore

WINDOW = timedelta(hours=24)
FEED_URL = "http://feed.test/private-abc123/basic.ics"


def _dt(value: datetime) -> str:
    return value.strftime("%Y%m%dT%H%M%SZ")


def _vevent(uid: str, sequence: int, start: datetime, summary: str, description: str) -> str:
    return (
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        "DTSTAMP:20260919T090000Z\r\n"
        f"SEQUENCE:{sequence}\r\n"
        f"DTSTART:{_dt(start)}\r\n"
        f"DTEND:{_dt(start + timedelta(minutes=30))}\r\n"
        f"SUMMARY:{summary}\r\n"
        f"DESCRIPTION:{description}\r\n"
        "END:VEVENT\r\n"
    )


def _feed(*vevents: str) -> str:
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n"
        + "".join(vevents)
        + "END:VCALENDAR\r\n"
    )


WITH_TOPIC = "Agenda:\\n- Pricing - 10m (owner: Ana)"


def _mock_feed(httpx_mock: HTTPXMock, body: str, *, url: str = FEED_URL) -> None:
    httpx_mock.add_response(url=url, method="GET", text=body)


async def test_first_ingest_creates_pending_record(httpx_mock: HTTPXMock) -> None:
    now = datetime.now(UTC)
    body = _feed(_vevent("ev1@feed", 0, now + timedelta(hours=1), "Pricing sync", WITH_TOPIC))
    _mock_feed(httpx_mock, body)

    store = InviteStore()
    registry = FeedRegistry()
    await poll_feeds_once(store, registry, [FEED_URL], {}, WINDOW)

    pending = store.pending()
    assert len(pending) == 1
    assert pending[0].title == "Pricing sync"
    assert pending[0].agenda["topics"][0]["title"] == "Pricing"

    health = registry.health_for(0)
    assert health.event_count == 1
    assert health.last_error is None
    assert health.last_success is not None


async def test_unchanged_repoll_is_a_noop(httpx_mock: HTTPXMock) -> None:
    now = datetime.now(UTC)
    body = _feed(_vevent("ev1@feed", 0, now + timedelta(hours=1), "Pricing sync", WITH_TOPIC))
    _mock_feed(httpx_mock, body)
    _mock_feed(httpx_mock, body)

    store = InviteStore()
    registry = FeedRegistry()
    await poll_feeds_once(store, registry, [FEED_URL], {}, WINDOW)
    first_id = store.pending()[0].session_id

    await poll_feeds_once(store, registry, [FEED_URL], {}, WINDOW)

    pending = store.pending()
    assert len(pending) == 1
    assert pending[0].session_id == first_id


async def test_sequence_bump_updates_in_place(httpx_mock: HTTPXMock) -> None:
    now = datetime.now(UTC)
    v0 = _feed(_vevent("ev1@feed", 0, now + timedelta(hours=1), "Pricing sync", WITH_TOPIC))
    v1 = _feed(
        _vevent(
            "ev1@feed",
            1,
            now + timedelta(hours=1),
            "Pricing sync (moved)",
            WITH_TOPIC,
        )
    )
    _mock_feed(httpx_mock, v0)
    _mock_feed(httpx_mock, v1)

    store = InviteStore()
    registry = FeedRegistry()
    await poll_feeds_once(store, registry, [FEED_URL], {}, WINDOW)
    session_id = store.pending()[0].session_id

    await poll_feeds_once(store, registry, [FEED_URL], {}, WINDOW)

    pending = store.pending()
    assert len(pending) == 1
    assert pending[0].session_id == session_id
    assert pending[0].title == "Pricing sync (moved)"


async def test_sequence_bump_does_not_restart_a_started_session(httpx_mock: HTTPXMock) -> None:
    now = datetime.now(UTC)
    v0 = _feed(_vevent("ev1@feed", 0, now + timedelta(hours=1), "Pricing sync", WITH_TOPIC))
    v1 = _feed(_vevent("ev1@feed", 1, now + timedelta(hours=1), "Pricing sync v2", WITH_TOPIC))
    _mock_feed(httpx_mock, v0)
    _mock_feed(httpx_mock, v1)

    store = InviteStore()
    registry = FeedRegistry()
    await poll_feeds_once(store, registry, [FEED_URL], {}, WINDOW)
    session_id = store.pending()[0].session_id
    store.mark_started(session_id, "meeting-1", "ears-session-1")

    await poll_feeds_once(store, registry, [FEED_URL], {}, WINDOW)

    record = store.get(session_id)
    assert record is not None
    assert record.title == "Pricing sync v2"
    assert record.started is True
    assert record.ears_meeting_id == "meeting-1"
    assert record.ears_session_id == "ears-session-1"
    assert store.pending() == []  # a started session is never pending again


async def test_event_without_topics_is_skipped_quietly(httpx_mock: HTTPXMock) -> None:
    now = datetime.now(UTC)
    body = _feed(
        _vevent("ev1@feed", 0, now + timedelta(hours=1), "No agenda here", "just chatting")
    )
    _mock_feed(httpx_mock, body)

    store = InviteStore()
    registry = FeedRegistry()
    await poll_feeds_once(store, registry, [FEED_URL], {}, WINDOW)

    assert store.pending() == []
    assert registry.health_for(0).last_error is None


async def test_event_outside_forward_window_is_skipped(httpx_mock: HTTPXMock) -> None:
    now = datetime.now(UTC)
    far_future = _vevent("ev1@feed", 0, now + timedelta(days=200), "Next year", WITH_TOPIC)
    past = _vevent("ev2@feed", 0, now - timedelta(hours=2), "Yesterday", WITH_TOPIC)
    body = _feed(far_future, past)
    _mock_feed(httpx_mock, body)

    store = InviteStore()
    registry = FeedRegistry()
    await poll_feeds_once(store, registry, [FEED_URL], {}, WINDOW)

    assert store.pending() == []


async def test_malformed_feed_records_error_without_crashing(httpx_mock: HTTPXMock) -> None:
    _mock_feed(httpx_mock, "this is not an ics file at all")

    store = InviteStore()
    registry = FeedRegistry()
    await poll_feeds_once(store, registry, [FEED_URL], {}, WINDOW)

    health = registry.health_for(0)
    assert health.last_error is not None
    assert FEED_URL not in health.last_error
    assert store.pending() == []


async def test_unreachable_feed_does_not_block_other_feeds(httpx_mock: HTTPXMock) -> None:
    other_url = "http://feed2.test/private-def456/basic.ics"
    now = datetime.now(UTC)
    ok_body = _feed(_vevent("ev1@feed2", 0, now + timedelta(hours=1), "Still works", WITH_TOPIC))

    httpx_mock.add_exception(httpx.ConnectError("boom"), url=FEED_URL, method="GET")
    _mock_feed(httpx_mock, ok_body, url=other_url)

    store = InviteStore()
    registry = FeedRegistry()
    await poll_feeds_once(store, registry, [FEED_URL, other_url], {}, WINDOW)

    down = registry.health_for(0)
    assert down.last_error is not None
    assert FEED_URL not in down.last_error

    up = registry.health_for(1)
    assert up.last_error is None
    assert up.event_count == 1

    pending = store.pending()
    assert len(pending) == 1
    assert pending[0].title == "Still works"


def _recurring_vevent(
    uid: str,
    sequence: int,
    start: datetime,
    summary: str,
    description: str,
    rrule: str,
) -> str:
    return (
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        "DTSTAMP:20260919T090000Z\r\n"
        f"SEQUENCE:{sequence}\r\n"
        f"DTSTART:{_dt(start)}\r\n"
        f"DTEND:{_dt(start + timedelta(minutes=30))}\r\n"
        f"RRULE:{rrule}\r\n"
        f"SUMMARY:{summary}\r\n"
        f"DESCRIPTION:{description}\r\n"
        "END:VEVENT\r\n"
    )


async def test_recurring_event_ingests_every_occurrence_in_the_window(
    httpx_mock: HTTPXMock,
) -> None:
    """The bug this guards: a series' DTSTART is its *first* occurrence, months
    in the past, so before expansion the standup never reached the board.
    """
    now = datetime.now(UTC)
    first_ever = now - timedelta(days=30) + timedelta(hours=1)
    body = _feed(
        _recurring_vevent("standup@feed", 0, first_ever, "Standup", WITH_TOPIC, "FREQ=DAILY")
    )
    _mock_feed(httpx_mock, body)

    store = InviteStore()
    registry = FeedRegistry()
    await poll_feeds_once(store, registry, [FEED_URL], {}, timedelta(hours=26))

    pending = sorted(store.pending(), key=lambda r: r.start)
    assert [r.title for r in pending] == ["Standup", "Standup"]
    assert pending[1].start - pending[0].start == timedelta(days=1)
    assert pending[0].session_id != pending[1].session_id


async def test_recurring_repoll_reuses_the_same_session_per_occurrence(
    httpx_mock: HTTPXMock,
) -> None:
    now = datetime.now(UTC)
    first_ever = now - timedelta(days=30) + timedelta(hours=1)
    body = _feed(
        _recurring_vevent("standup@feed", 0, first_ever, "Standup", WITH_TOPIC, "FREQ=DAILY")
    )
    _mock_feed(httpx_mock, body)
    _mock_feed(httpx_mock, body)

    store = InviteStore()
    registry = FeedRegistry()
    await poll_feeds_once(store, registry, [FEED_URL], {}, timedelta(hours=26))
    first_ids = sorted(r.session_id for r in store.pending())

    await poll_feeds_once(store, registry, [FEED_URL], {}, timedelta(hours=26))

    assert sorted(r.session_id for r in store.pending()) == first_ids  # no duplicates


def test_vtimezone_is_carried_into_the_single_event_ics() -> None:
    """A TZID= reference must still resolve once one VEVENT is pulled out of
    its feed — this is what `_single_event_ics` copying VTIMEZONE guards.
    """
    feed_text = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//test//EN\r\n"
        "BEGIN:VTIMEZONE\r\n"
        "TZID:Custom/Zone\r\n"
        "BEGIN:STANDARD\r\n"
        "DTSTART:19700101T000000\r\n"
        "TZOFFSETFROM:+0000\r\n"
        "TZOFFSETTO:+0200\r\n"
        "END:STANDARD\r\n"
        "END:VTIMEZONE\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:tz1@feed\r\n"
        "DTSTAMP:20260919T090000Z\r\n"
        "SEQUENCE:0\r\n"
        "DTSTART;TZID=Custom/Zone:20260920T090000\r\n"
        "DTEND;TZID=Custom/Zone:20260920T093000\r\n"
        f"SUMMARY:TZ meeting\r\n"
        f"DESCRIPTION:{WITH_TOPIC}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    feed_cal = Calendar.from_ical(feed_text)
    event = feed_cal.walk("VEVENT")[0]
    single = _single_event_ics(feed_cal, event)
    parsed = parse_ics(single)
    assert parsed.start.utcoffset() is not None  # resolved via the copied VTIMEZONE
    assert parsed.start.hour == 7  # 09:00 Custom/Zone (+02:00) -> 07:00 UTC
