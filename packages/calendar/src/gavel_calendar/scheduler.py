"""One asyncio task that wakes at the next event's start time and starts it.

Clicking Join calls `service.start` directly, early. This task calls the
same function when nobody clicked it — both paths end in the same call
(`service.start`), so there is exactly one way a session actually starts.

Also holds the feed poller (`poll_feeds`/`poll_feeds_once`): it fetches each
`CALENDAR_ICS_FEEDS` URL, walks its `VEVENT`s, and feeds new/changed ones
through the same `ics_parser.parse_ics` → `agenda.build_agenda` path
`POST /invite` uses — see `_single_event_ics` for how one `VEVENT` becomes
the bytes that parser expects, without a second parser.
"""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from icalendar import Calendar

from . import service
from .agenda import build_agenda
from .ears_client import EarsClient
from .feed_store import FeedRegistry
from .ics_parser import InvalidInvite, parse_ics
from .store import InviteRecord, InviteStore

logger = logging.getLogger(__name__)


async def run(store: InviteStore, ears: EarsClient, poll_seconds: float) -> None:
    while True:
        now = datetime.now(UTC)
        due = [r for r in store.pending() if r.start <= now]
        for record in due:
            try:
                await service.start(store, ears, record.session_id)
                logger.info("scheduler.started session_id=%s", record.session_id)
            except Exception:
                logger.exception("scheduler.start_failed session_id=%s", record.session_id)

        upcoming = [r.start for r in store.pending()]
        sleep_for = poll_seconds
        if upcoming:
            delta = (min(upcoming) - datetime.now(UTC)).total_seconds()
            sleep_for = 0.1 if delta <= 0 else min(delta, poll_seconds)
        await asyncio.sleep(sleep_for)


# --- feed polling ------------------------------------------------------------------


def _session_id_for(feed_index: int, uid: str) -> str:
    """Deterministic from (feed_index, uid) alone — a re-poll of the same
    event, changed or not, always lands on the same `InviteRecord`, so an
    operator's join link never goes stale and a bumped `SEQUENCE` updates in
    place instead of spawning a second session.
    """
    digest = hashlib.sha256(f"{feed_index}:{uid}".encode()).hexdigest()
    return digest[:12]


def _single_event_ics(feed_cal: Calendar, event: Any) -> bytes:
    """Re-serializes one `VEVENT` — plus any `VTIMEZONE` the feed defines, so
    a `TZID=` reference still resolves — as its own `.ics`. This is what lets
    `ics_parser.parse_ics` (the one place that knows how to read a `VEVENT`)
    handle a feed's events one at a time; it is not a second parser.
    """
    single = Calendar()
    single.add("prodid", "-//gavel-calendar//feed-extract//EN")
    single.add("version", "2.0")
    for tzcomp in feed_cal.walk("VTIMEZONE"):
        single.add_component(tzcomp)
    single.add_component(event)
    return single.to_ical()


async def _poll_one_feed(
    store: InviteStore,
    registry: FeedRegistry,
    feed_index: int,
    url: str,
    attendee_map: dict[str, str],
    window: timedelta,
) -> None:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # A status code is not a secret; the URL that produced it is — never
        # pass the exception's own str() through, it echoes the request URL.
        error = f"HTTPStatusError {exc.response.status_code}"
        registry.record_error(feed_index, error)
        logger.warning("feed[%d].fetch_failed error=%s", feed_index, error)
        return
    except httpx.HTTPError as exc:
        registry.record_error(feed_index, type(exc).__name__)
        logger.warning("feed[%d].fetch_failed error=%s", feed_index, type(exc).__name__)
        return

    # icalendar raises several different error types for a malformed feed; this is a
    # per-feed isolation boundary (never re-raised), not a swallowed specific error.
    try:
        feed_cal = Calendar.from_ical(resp.text)
    except Exception as exc:  # noqa: BLE001
        error = f"malformed feed ({type(exc).__name__})"
        registry.record_error(feed_index, error)
        logger.warning("feed[%d].malformed error=%s", feed_index, type(exc).__name__)
        return

    now = datetime.now(UTC)
    ingested = 0
    for event in feed_cal.walk("VEVENT"):
        uid = str(event.get("uid") or "").strip()
        if not uid:
            continue  # no UID: nothing stable to dedupe or key a session on
        sequence = int(event.get("sequence", 0) or 0)
        session_id = _session_id_for(feed_index, uid)

        if registry.seen_sequence(feed_index, uid) == sequence:
            ingested += 1  # unchanged since the last poll — a no-op, not a re-fetch
            continue

        try:
            parsed = parse_ics(_single_event_ics(feed_cal, event))
        except InvalidInvite:
            continue  # this one VEVENT was unusable; the rest of the feed still is

        if not (now <= parsed.start <= now + window):
            continue  # outside the forward window — a year of history, not ingested

        if not parsed.topics:
            # No topic lines in the description: skipped quietly, not crashed
            # on. Still marked seen so an unchanged re-poll stays a no-op.
            registry.mark_seen(feed_index, uid, sequence)
            continue

        agenda = build_agenda(parsed, session_id, attendee_map)
        existing = store.get(session_id)
        # A bumped SEQUENCE on an already-started session must update the
        # display fields only — never reset `started`/the ears ids, or the
        # scheduler would pick it back up as pending and start a second ears
        # session for the same meeting.
        record = (
            dataclasses.replace(
                existing,
                title=parsed.title,
                start=parsed.start,
                end=parsed.end,
                agenda=agenda,
                context=parsed.description,
            )
            if existing is not None
            else InviteRecord(
                session_id=session_id,
                title=parsed.title,
                start=parsed.start,
                end=parsed.end,
                agenda=agenda,
                context=parsed.description,
            )
        )
        store.save(record)
        registry.mark_seen(feed_index, uid, sequence)
        ingested += 1

    registry.record_success(feed_index, at=now, event_count=ingested)


async def poll_feeds_once(
    store: InviteStore,
    registry: FeedRegistry,
    feed_urls: list[str],
    attendee_map: dict[str, str],
    window: timedelta,
) -> None:
    """One pass over every feed. A feed that fails — down, malformed,
    whatever — only marks its own health; the rest still get polled.
    """
    for feed_index, url in enumerate(feed_urls):
        try:
            await _poll_one_feed(store, registry, feed_index, url, attendee_map, window)
        except Exception:
            # Isolation of last resort: a bug in this feed's handling must
            # not stop the others, or take the auto-start loop down with it.
            logger.exception("feed[%d].poll_failed", feed_index)


async def poll_feeds(
    store: InviteStore,
    registry: FeedRegistry,
    feed_urls: list[str],
    attendee_map: dict[str, str],
    poll_seconds: float,
    window: timedelta,
) -> None:
    while True:
        await poll_feeds_once(store, registry, feed_urls, attendee_map, window)
        await asyncio.sleep(poll_seconds)
