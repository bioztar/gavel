from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pytest_httpx import HTTPXMock

from gavel_calendar.app import app, ears, store

FIXTURE = Path(__file__).parent.parent / "fixtures" / "demo.ics"


@pytest.fixture(autouse=True)
def _clean_store() -> Iterator[None]:
    store._records.clear()
    yield
    store._records.clear()


def test_invite_then_join_page() -> None:
    with TestClient(app) as client:
        resp = client.post("/invite", files={"file": ("demo.ics", FIXTURE.read_bytes())})
        assert resp.status_code == 200
        body = resp.json()
        session_id = body["sessionId"]
        assert body["joinUrl"].endswith(f"/m/{session_id}")

        page = client.get(f"/m/{session_id}")
        assert page.status_code == 200
        assert "Launch readiness" in page.text
        assert "Where we actually are" in page.text
        assert "2 min" in page.text  # 120 seconds, shown to a human
        assert "Join" in page.text


def test_invite_rejects_garbage() -> None:
    with TestClient(app) as client:
        resp = client.post("/invite", files={"file": ("bad.ics", b"not an ics")})
        assert resp.status_code == 422


def test_join_calls_ears_once_and_is_idempotent(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{ears._base_url}/api/meetings",
        method="POST",
        json={"id": "meeting-1"},
    )
    httpx_mock.add_response(
        url=f"{ears._base_url}/api/sessions",
        method="POST",
        json={"sessionId": "ears-session-1"},
    )

    with TestClient(app) as client:
        invite_resp = client.post("/invite", files={"file": ("demo.ics", FIXTURE.read_bytes())})
        session_id = invite_resp.json()["sessionId"]

        join_resp = client.post(f"/m/{session_id}/join")
        assert join_resp.status_code == 200
        assert "ears-session-1" in join_resp.text

        # Clicking Join again must not call ears a second time.
        join_again = client.post(f"/m/{session_id}/join")
        assert join_again.status_code == 200

    requests = httpx_mock.get_requests()
    meeting_calls = [r for r in requests if r.url.path == "/api/meetings"]
    session_calls = [r for r in requests if r.url.path == "/api/sessions"]
    assert len(meeting_calls) == 1
    assert len(session_calls) == 1


def test_join_unknown_session_404s() -> None:
    with TestClient(app) as client:
        resp = client.post("/m/does-not-exist/join")
        assert resp.status_code == 404


def test_board_lists_pending_invites_with_join_buttons() -> None:
    with TestClient(app) as client:
        invite_resp = client.post("/invite", files={"file": ("demo.ics", FIXTURE.read_bytes())})
        session_id = invite_resp.json()["sessionId"]

        page = client.get("/board")
        assert page.status_code == 200
        assert "Launch readiness" in page.text
        assert f'action="/m/{session_id}/join"' in page.text


def test_health_reports_zero_feeds_when_unconfigured() -> None:
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["feeds"] == []
