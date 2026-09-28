"""The two gates on the operator routes (access.py): token and per-IP budget.

Same isolation as `test_compose_routes.py`: the already-built `settings` object
is patched in place, so nothing here reads a real token or reaches a network.
"""

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from gavel_calendar import access
from gavel_calendar import app as app_module
from gavel_calendar.app import app

TOKEN = "test-operator-token"
OPERATOR_ROUTES = ["/compose", "/architecture", "/demo-script"]


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_module.settings, "nebius_api_key", "")
    monkeypatch.setattr(app_module.settings, "resend_api_key", "")
    monkeypatch.setattr(app_module.settings, "calendar_admin_token", TOKEN)
    monkeypatch.setattr(app_module.settings, "calendar_auth_required", True)
    monkeypatch.setattr(app_module.settings, "calendar_rate_limit", "1000/minute")
    access.limiter.reset()


@pytest.mark.parametrize("path", OPERATOR_ROUTES)
def test_operator_routes_reject_a_missing_token(path: str) -> None:
    with TestClient(app) as client:
        resp = client.get(path)
    assert resp.status_code == 401
    assert "Basic" in resp.headers["www-authenticate"]


@pytest.mark.parametrize("path", ["/compose/parse", "/compose/send"])
def test_compose_posts_reject_a_wrong_token(path: str) -> None:
    with TestClient(app) as client:
        resp = client.post(path, data={"brief": "x"}, headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401


def test_bearer_token_is_accepted() -> None:
    with TestClient(app) as client:
        resp = client.get("/compose", headers={"Authorization": f"Bearer {TOKEN}"})
    assert resp.status_code == 200


def test_basic_auth_with_the_token_as_password_is_accepted() -> None:
    creds = base64.b64encode(f"anyone:{TOKEN}".encode()).decode()
    with TestClient(app) as client:
        resp = client.get("/compose", headers={"Authorization": f"Basic {creds}"})
    assert resp.status_code == 200


def test_basic_auth_with_a_wrong_password_is_rejected() -> None:
    creds = base64.b64encode(b"anyone:nope").decode()
    with TestClient(app) as client:
        resp = client.get("/compose", headers={"Authorization": f"Basic {creds}"})
    assert resp.status_code == 401


def test_unset_token_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_module.settings, "calendar_admin_token", "")
    with TestClient(app) as client:
        resp = client.get("/compose")
    assert resp.status_code == 503
    assert "CALENDAR_ADMIN_TOKEN" in resp.text


def test_explicit_opt_out_opens_the_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_module.settings, "calendar_admin_token", "")
    monkeypatch.setattr(app_module.settings, "calendar_auth_required", False)
    with TestClient(app) as client:
        resp = client.get("/compose")
    assert resp.status_code == 200


def test_public_routes_need_no_token() -> None:
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/board").status_code == 200


def test_operator_routes_are_rate_limited_per_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_module.settings, "calendar_rate_limit", "2/minute")
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        assert client.get("/compose").status_code == 200
        assert client.get("/compose").status_code == 200
        resp = client.get("/compose")
    assert resp.status_code == 429
    assert "Rate limit exceeded" in resp.text


def test_rate_limit_throttles_a_wrong_token_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_module.settings, "calendar_rate_limit", "2/minute")
    with TestClient(app, headers={"Authorization": "Bearer nope"}) as client:
        assert client.get("/compose").status_code == 401
        assert client.get("/compose").status_code == 401
        assert client.get("/compose").status_code == 429


def test_token_compare_rejects_empty_and_mismatch() -> None:
    assert access.token_matches("abc", "abc")
    assert not access.token_matches("abd", "abc")
    assert not access.token_matches(None, "abc")
    assert not access.token_matches("", "")
