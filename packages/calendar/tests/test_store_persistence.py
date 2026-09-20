"""The durable copy of an invite.

Every test here answers one of the three things that used to die with the
process. They run against SQLite (`aiosqlite`) rather than Postgres so the
suite needs no database; `test_compose.py` and friends still exercise the
memory-only store, which is the fallback path when Postgres is unreachable.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine

from gavel_calendar.db.models import Base
from gavel_calendar.store import InviteRecord, InviteStore

AGENDA = {
    "sessionId": "abc123",
    "purpose": "Ship on Tuesday",
    "topics": [{"id": "t1", "title": "Where we are", "budgetSeconds": 120}],
}


@pytest_asyncio.fixture
async def dsn(tmp_path) -> AsyncIterator[str]:
    """A file, not `:memory:` — the whole point is that a *second* store, with
    its own engine, reads what the first one wrote."""
    url = f"sqlite+aiosqlite:///{tmp_path / 'calendar.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    yield url


def _record(**kw) -> InviteRecord:
    record = InviteRecord(
        session_id="abc123",
        title="Launch readiness",
        start=datetime(2026, 9, 20, 10, 0, tzinfo=UTC),
        end=datetime(2026, 9, 20, 10, 30, tzinfo=UTC),
        agenda=dict(AGENDA),
        context="the full brief",
    )
    for key, value in kw.items():
        setattr(record, key, value)
    return record


async def _reopen(dsn: str) -> InviteStore:
    """What a restart looks like: a brand-new store on the same database."""
    store = InviteStore()
    assert await store.attach(dsn) is True
    return store


async def test_an_invite_outlives_the_process_that_took_it(dsn: str) -> None:
    """A `/m/{id}` link used to 404 after `docker compose up -d --build
    calendar`, which the handover treats as routine — including for links
    already emailed to attendees."""
    first = await _reopen(dsn)
    await first.save(_record())
    await first.close()

    second = await _reopen(dsn)
    record = second.get("abc123")
    assert record is not None
    assert record.title == "Launch readiness"
    assert record.start == datetime(2026, 9, 20, 10, 0, tzinfo=UTC)
    assert record.agenda == AGENDA
    assert record.context == "the full brief"
    await second.close()


async def test_a_rehydrated_start_time_is_still_comparable_to_now(dsn: str) -> None:
    """The scheduler's due check is `record.start <= datetime.now(UTC)`. A
    driver that hands back a naive datetime makes that raise TypeError, which
    would take down the auto-start loop for every meeting, not just this one."""
    first = await _reopen(dsn)
    await first.save(_record(start=datetime.now(UTC) - timedelta(seconds=1)))
    await first.close()

    second = await _reopen(dsn)
    record = second.get("abc123")
    assert record is not None
    assert record.start.tzinfo is not None
    assert record.start <= datetime.now(UTC)  # the comparison itself is the assertion
    await second.close()


async def test_a_started_session_is_not_started_again_after_a_restart(dsn: str) -> None:
    """`started` is what stops the scheduler opening a *second* ears session
    for a meeting already under way. In-process state could never do that job:
    the guard in `scheduler._ingest_occurrence` only held while the process did.
    """
    first = await _reopen(dsn)
    await first.save(_record(start=datetime.now(UTC) - timedelta(minutes=5)))
    await first.mark_started("abc123", "meeting-1", "ears-session-1")
    assert first.pending() == []
    await first.close()

    second = await _reopen(dsn)
    record = second.get("abc123")
    assert record is not None
    assert record.started is True
    assert record.ears_meeting_id == "meeting-1"
    assert record.ears_session_id == "ears-session-1"
    # Due by wall-clock, but never pending again — so `scheduler.run` skips it.
    assert second.pending() == []
    await second.close()


async def test_the_banked_report_outlives_the_process(dsn: str) -> None:
    """The brain forgets a session when the next one starts, so the banked
    snapshot is the only copy the report can be rendered from."""
    state = {"sessionId": "ears-1", "notes": {"decisions": ["Ship Tuesday"]}}
    first = await _reopen(dsn)
    await first.save(_record(started=True, ears_session_id="ears-1"))
    await first.bank_state("abc123", state)
    await first.close()

    second = await _reopen(dsn)
    record = second.get("abc123")
    assert record is not None
    assert record.last_state == state
    await second.close()


async def test_banking_an_identical_snapshot_does_not_rewrite_the_row(dsn: str) -> None:
    """Every viewer polls `/m/{id}/state` every 2s and banks what it sees.
    Between two polls the snapshot is usually byte-identical."""
    store = await _reopen(dsn)
    await store.save(_record())
    state = {"sessionId": "ears-1", "phase": "live"}
    await store.bank_state("abc123", state)

    writes: list[str] = []
    original = store._persist

    async def counting(record: InviteRecord) -> None:
        writes.append(record.session_id)
        await original(record)

    store._persist = counting  # type: ignore[method-assign]
    await store.bank_state("abc123", dict(state))
    assert writes == []
    await store.bank_state("abc123", {"sessionId": "ears-1", "phase": "after"})
    assert writes == ["abc123"]
    await store.close()


async def test_an_edited_feed_event_updates_in_place(dsn: str) -> None:
    """A bumped SEQUENCE re-saves the same `sessionId`; the row is updated, not
    duplicated, and the public link stays the one already in someone's inbox."""
    store = await _reopen(dsn)
    await store.save(_record())
    await store.save(_record(title="Launch readiness v2"))
    await store.close()

    second = await _reopen(dsn)
    assert len(second._records) == 1
    record = second.get("abc123")
    assert record is not None
    assert record.title == "Launch readiness v2"
    await second.close()


async def test_an_unreachable_database_costs_durability_not_the_invite(tmp_path) -> None:
    """ears' own store disables itself rather than refusing to run, and this
    one has to as well: an invite that cannot be written down is still an
    invite, and a calendar that will not boot is not a calendar."""
    store = InviteStore()
    attached = await store.attach("postgresql+asyncpg://nobody@127.0.0.1:1/nope")
    assert attached is False
    assert store.durable is False

    await store.save(_record())
    assert store.get("abc123") is not None  # the meeting exists regardless
    assert len(store.pending()) == 1


async def test_a_write_that_fails_still_leaves_the_invite_in_memory(dsn: str) -> None:
    """`compose.handle_send` promises the meeting exists from the save onward,
    'no matter what happens next'. A database that dies mid-demo must not turn
    that promise into a 500 on the page that was about to email a link out."""
    store = await _reopen(dsn)

    def boom():
        raise RuntimeError("database is gone")

    store._factory = boom  # type: ignore[assignment]
    await store.save(_record())  # must not raise

    record = store.get("abc123")
    assert record is not None
    assert record.title == "Launch readiness"


async def test_no_dsn_is_the_old_memory_only_store(dsn: str) -> None:
    store = InviteStore()
    assert await store.attach("") is False
    assert store.durable is False
    await store.save(_record())
    assert store.get("abc123") is not None
