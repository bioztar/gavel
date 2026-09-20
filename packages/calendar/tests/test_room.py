from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from pytest_httpx import HTTPXMock

from gavel_calendar import room
from gavel_calendar.app import app, settings, store
from gavel_calendar.store import InviteRecord

FIXTURE = Path(__file__).parent.parent / "fixtures" / "demo.ics"


@pytest.fixture(autouse=True)
def _clean_store() -> Iterator[None]:
    store._records.clear()
    yield
    store._records.clear()


def _save(record: InviteRecord) -> None:
    """These tests drive the app through the sync `TestClient`, so there is no
    running loop to await the store's now-async writes on. The store is
    memory-only here (no DSN), so this is just the write, not a database."""
    asyncio.run(store.save(record))


def _record(**kw: Any) -> InviteRecord:
    record = InviteRecord(
        session_id="abc123",
        title="Launch readiness",
        start=datetime.now(UTC) + timedelta(hours=1),
        end=datetime.now(UTC) + timedelta(hours=1, minutes=30),
        agenda={
            "purpose": "Ship on Tuesday",
            "attendees": [{"name": "Ana", "role": "host", "discordId": "1"}],
            "topics": [{"title": "Where we actually are", "budgetSeconds": 120, "owner": "1"}],
        },
    )
    for key, value in kw.items():
        setattr(record, key, value)
    return record


def _brain(session_id: str = "ears-1", **kw: Any) -> dict[str, Any]:
    state: dict[str, Any] = {
        "sessionId": session_id,
        "phase": "active",
        "chairName": "Karen",
        "topic": {
            "index": 0,
            "title": "Where we actually are",
            "budgetSeconds": 120,
            "elapsedSeconds": 150,
        },
        "topics": [{"title": "Where we actually are", "budgetSeconds": 120, "done": False}],
        "people": [
            {"name": "Vitaly", "role": "host", "totalSeconds": 180, "speaking": True},
            {"name": "Ana", "role": "attendee", "totalSeconds": 60},
        ],
        "interventions": [
            {"at": 1, "kind": "startMeeting", "line": "Here is the agenda."},
            {"at": 2, "kind": "floorHog", "line": "Vitaly, you've had eight of the last ten."},
        ],
        "digest": {
            "facts": ["Staging is green"],
            "decisions": ["Ship Tuesday"],
            "openItems": ["Ana to confirm the copy"],
            "parked": [{"name": "Vitaly", "summary": "the hiring plan"}],
        },
    }
    state.update(kw)
    return state


def test_before_the_meeting_the_room_shows_the_invites_own_agenda() -> None:
    state = room.room_state(_record(), None)
    assert state["phase"] == "before"
    assert [t["title"] for t in state["topics"]] == ["Where we actually are"]
    assert state["purpose"] == "Ship on Tuesday"


def test_live_state_is_human_readable() -> None:
    record = _record(started=True, ears_session_id="ears-1")
    state = room.room_state(record, _brain())

    assert state["phase"] == "live"
    # Karen's own log, newest first, named in words rather than trigger ids.
    assert [h["label"] for h in state["headlines"]] == ["Balanced the floor", "Opened the meeting"]
    # The floor, loudest first, as a share of what was actually said.
    assert [(p["name"], p["share"]) for p in state["people"]] == [("Vitaly", 0.75), ("Ana", 0.25)]
    assert state["people"][0]["speaking"] is True
    assert state["notes"]["decisions"] == ["Ship Tuesday"]
    assert state["notes"]["parked"] == [{"name": "Vitaly", "summary": "the hiring plan"}]
    assert state["topic"]["elapsedSeconds"] == 150


def test_another_meetings_session_is_never_shown_under_this_link() -> None:
    """One brain, one live session. A state belonging to the next meeting must
    not render under this one's URL — that would show the wrong room's numbers."""
    record = _record(started=True, ears_session_id="ears-1")
    assert room.is_live(record, _brain("ears-2")) is False
    assert room.room_state(record, _brain("ears-2"))["phase"] == "before"


def test_after_the_meeting_the_banked_state_is_the_report() -> None:
    record = _record(started=True, ears_session_id="ears-1", last_state=_brain(phase="finished"))
    state = room.room_state(record, _brain("ears-2"))  # the brain has moved on

    assert state["phase"] == "after"
    assert state["notes"]["decisions"] == ["Ship Tuesday"]
    assert state["notes"]["openItems"] == ["Ana to confirm the copy"]
    assert state["headlines"][0]["label"] == "Balanced the floor"


def test_state_route_banks_what_it_sees_so_the_report_outlives_the_session(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(url=settings.brain_state_url, json=_brain())
    httpx_mock.add_response(url=settings.brain_state_url, json=_brain("ears-2"))
    _save(_record(started=True, ears_session_id="ears-1"))

    with TestClient(app) as client:
        live = client.get("/m/abc123/state").json()
        assert live["phase"] == "live"

        # Next poll: the brain is chairing somebody else's meeting now.
        after = client.get("/m/abc123/state").json()
        assert after["phase"] == "after"
        assert after["notes"]["decisions"] == ["Ship Tuesday"]


def test_state_route_survives_an_unreachable_brain(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(httpx.ConnectError("no brain"), url=settings.brain_state_url)
    _save(_record())

    with TestClient(app) as client:
        resp = client.get("/m/abc123/state")
        assert resp.status_code == 200
        assert resp.json()["phase"] == "before"


def test_room_page_carries_the_chair_video_stage_and_the_agenda() -> None:
    _save(_record())
    with TestClient(app) as client:
        page = client.get("/m/abc123")

    assert page.status_code == 200
    assert settings.chair_video_stage_url in page.text
    assert "Where we actually are" in page.text
    assert "Join the call" in page.text
