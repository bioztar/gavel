"""The three compose routes through the real app, exercised end to end.

`gavel_calendar.app` builds its `settings` once at import time from whatever
`.env` this machine has — real `NEBIUS_API_KEY` included. Each test patches
that already-built object in place (rather than the environment) so nothing
here can reach a real key or make a real network call; the routes read the
module attribute `settings` fresh on every request, so the patch takes effect
immediately. See `test_compose.py` for the same isolation at the unit level.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pytest_httpx import HTTPXMock

from gavel_calendar import app as app_module
from gavel_calendar.app import app, store


@pytest.fixture(autouse=True)
def _clean_store() -> Iterator[None]:
    store._records.clear()
    yield
    store._records.clear()


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_module.settings, "nebius_api_key", "")
    monkeypatch.setattr(app_module.settings, "nebius_base_url", "https://fake.test/v1")
    monkeypatch.setattr(app_module.settings, "resend_api_key", "")
    monkeypatch.setattr(app_module.settings, "compose_from_email", "")


def test_root_redirects_to_board() -> None:
    with TestClient(app, follow_redirects=False) as client:
        resp = client.get("/")
        assert resp.status_code == 307
        assert resp.headers["location"] == "/board"


def test_get_compose_renders_brief_form() -> None:
    with TestClient(app) as client:
        resp = client.get("/compose")
        assert resp.status_code == 200
        assert "<textarea" in resp.text


def test_compose_parse_falls_back_without_llm_configured() -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/compose/parse",
            data={"brief": "set up a meeting", "attendees": "Vitaly <vitaly@test.dev>"},
        )
        assert resp.status_code == 200
        assert "no agenda in" in resp.text.lower()


def test_compose_send_creates_meeting_with_working_join_link(httpx_mock: HTTPXMock) -> None:
    # `httpx_mock` with no registered response makes any unmocked network call
    # fail the test instead of silently escaping — the mailer must dry-run.
    # Creating the meeting hands it straight to ears, so those two calls are real.
    httpx_mock.add_response(
        url="http://localhost:8787/api/meetings", json={"id": "m-1"}
    )
    httpx_mock.add_response(
        url="http://localhost:8787/api/sessions", json={"sessionId": "s-1"}
    )
    with TestClient(app) as client:
        resp = client.post(
            "/compose/send",
            data={
                "title": "Pricing sync",
                "brief": "talk pricing",
                "attendees": "Vitaly <vitaly@test.dev>, Artem <artem@test.dev>",
                "start": "2026-09-20T15:00",
                "duration_minutes": "30",
                "topics_count": "1",
                "topic_title_0": "Pricing",
                "topic_minutes_0": "",
                "topic_owner_0": "Vitaly",
                "topic_must_hear_0": "Artem",
            },
        )
        assert resp.status_code == 200
        assert "not sent" in resp.text  # dry-run mailer, no RESEND_API_KEY

        assert "Karen is holding the room" in resp.text

        assert len(store._records) == 1
        session_id, record = next(iter(store._records.items()))
        # Handed to ears there and then: the chair is already on this meeting, and the
        # scheduler will not start a second session for it at the event's own time.
        assert record.started
        assert (record.ears_meeting_id, record.ears_session_id) == ("m-1", "s-1")

        join_resp = client.get(f"/m/{session_id}")
        assert join_resp.status_code == 200
        assert "Pricing sync" in join_resp.text


def test_compose_parse_uses_llm_when_configured(
    monkeypatch: pytest.MonkeyPatch, httpx_mock: HTTPXMock
) -> None:
    payload = {
        "title": "Pricing sync",
        "start": "2026-09-19T13:00:00+02:00",
        "duration_minutes": 15,
        "topics": [{"title": "Pricing", "minutes": 15, "owner": "Vitaly", "must_hear": []}],
    }
    httpx_mock.add_response(
        url="https://fake.test/v1/chat/completions",
        method="POST",
        json={"choices": [{"message": {"content": json.dumps(payload)}}]},
    )
    monkeypatch.setattr(app_module.settings, "nebius_api_key", "key123")
    with TestClient(app) as client:
        resp = client.post(
            "/compose/parse",
            data={"brief": "pricing in an hour", "attendees": "Vitaly <vitaly@test.dev>"},
        )
    assert resp.status_code == 200
    assert "Pricing sync" in resp.text
    assert 'name="enforcement"' in resp.text


def test_gate_asks_for_an_agenda_and_nothing_else(
    monkeypatch: pytest.MonkeyPatch, httpx_mock: HTTPXMock
) -> None:
    """A brief the model finds no topics in gets the refusal, not a topic grid.

    The gate is the demo's headline beat, so what it must *not* contain is as
    load-bearing as what it does: no topic rows to fill in, no send button.
    """
    payload = {
        "title": "Sync",
        "start": "2026-09-19T13:00:00+02:00",
        "duration_minutes": 30,
        "topics": [],
    }
    httpx_mock.add_response(
        url="https://fake.test/v1/chat/completions",
        method="POST",
        json={"choices": [{"message": {"content": json.dumps(payload)}}]},
    )
    monkeypatch.setattr(app_module.settings, "nebius_api_key", "key123")
    with TestClient(app) as client:
        resp = client.post(
            "/compose/parse",
            data={"brief": "meeting with Artem tomorrow", "attendees": ""},
        )
    assert resp.status_code == 200
    assert "no agenda in" in resp.text.lower()
    assert 'name="agenda"' in resp.text
    assert "topic_title_0" not in resp.text
    assert 'action="/compose/send"' not in resp.text


def test_a_typed_agenda_clears_the_gate(
    monkeypatch: pytest.MonkeyPatch, httpx_mock: HTTPXMock
) -> None:
    """The gate posts back with `agenda`; the brief and the agenda are re-parsed
    together, so a topic typed there arrives exactly like a dictated one."""
    payload = {
        "title": "Sync",
        "start": "2026-09-19T13:00:00+02:00",
        "duration_minutes": 30,
        "topics": [{"title": "Pricing", "minutes": 30, "owner": "Vitaly", "must_hear": []}],
    }
    httpx_mock.add_response(
        url="https://fake.test/v1/chat/completions",
        method="POST",
        json={"choices": [{"message": {"content": json.dumps(payload)}}]},
    )
    monkeypatch.setattr(app_module.settings, "nebius_api_key", "key123")
    with TestClient(app) as client:
        resp = client.post(
            "/compose/parse",
            data={
                "brief": "meeting with Artem tomorrow",
                "attendees": "",
                "agenda": "Pricing - Vitaly, 30 min",
            },
        )
    assert resp.status_code == 200
    assert 'action="/compose/send"' in resp.text
    assert "Pricing" in resp.text


def test_parse_accepts_an_empty_invitee_box():
    """Page one's invitee field is optional; leaving it blank must not 422."""
    with TestClient(app) as client:
        resp = client.post("/compose/parse", data={"brief": "Karen, meet Artem.", "attendees": ""})
    assert resp.status_code == 200
