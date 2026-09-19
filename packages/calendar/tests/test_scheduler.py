"""Exercises the actual auto-start path (scheduler.run), not just the parser
or the Join button. Both must end in the same `service.start` call.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from pytest_httpx import HTTPXMock

from gavel_calendar.ears_client import EarsClient
from gavel_calendar.scheduler import run
from gavel_calendar.store import InviteRecord, InviteStore

EMPTY_AGENDA = {
    "sessionId": "s1",
    "purpose": "p",
    "totalSeconds": 60,
    "attendees": [],
    "topics": [],
    "policy": {},
}


async def test_scheduler_auto_starts_due_session(httpx_mock: HTTPXMock) -> None:
    ears = EarsClient("http://ears.test")
    httpx_mock.add_response(
        url="http://ears.test/api/meetings", method="POST", json={"id": "meeting-1"}
    )
    httpx_mock.add_response(
        url="http://ears.test/api/sessions", method="POST", json={"sessionId": "ears-session-1"}
    )

    store = InviteStore()
    past = datetime.now(UTC) - timedelta(seconds=1)
    store.save(
        InviteRecord(
            session_id="s1",
            title="Due now",
            start=past,
            end=past,
            agenda=EMPTY_AGENDA,
        )
    )

    task = asyncio.create_task(run(store, ears, poll_seconds=30))
    try:
        for _ in range(100):
            record = store.get("s1")
            assert record is not None
            if record.started:
                break
            await asyncio.sleep(0.02)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    record = store.get("s1")
    assert record is not None
    assert record.started
    assert record.ears_session_id == "ears-session-1"

    requests = httpx_mock.get_requests()
    assert len([r for r in requests if r.url.path == "/api/meetings"]) == 1
    assert len([r for r in requests if r.url.path == "/api/sessions"]) == 1


async def test_scheduler_ignores_future_session(httpx_mock: HTTPXMock) -> None:
    ears = EarsClient("http://ears.test")
    store = InviteStore()
    future = datetime.now(UTC) + timedelta(hours=1)
    store.save(
        InviteRecord(
            session_id="s2",
            title="Not yet",
            start=future,
            end=future,
            agenda=EMPTY_AGENDA,
        )
    )

    task = asyncio.create_task(run(store, ears, poll_seconds=30))
    await asyncio.sleep(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    record = store.get("s2")
    assert record is not None
    assert not record.started
    # No calls to ears at all — nothing was due.
    assert httpx_mock.get_requests() == []
