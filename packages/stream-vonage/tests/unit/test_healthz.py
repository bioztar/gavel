from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from stream_vonage.app import create_app
from stream_vonage.settings import Settings

# All four credential fields are always passed explicitly (init kwargs are
# pydantic-settings' highest-priority source) so these tests see exactly the
# credential state under test, regardless of the host's real environment/.env.
_BLANK: dict[str, Any] = {
    "vonage_application_id": "",
    "vonage_private_key": "",
    "vonage_api_key": "",
    "vonage_api_secret": "",
}


def _settings(**overrides: str) -> Settings:
    return Settings(**{**_BLANK, **overrides})


def test_healthz_absent_when_no_credentials() -> None:
    client = TestClient(create_app(_settings()))
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"credentials": "absent", "authStyle": None}


def test_healthz_present_jwt_style() -> None:
    settings = _settings(vonage_application_id="app-1", vonage_private_key="key")
    client = TestClient(create_app(settings))
    r = client.get("/healthz")
    assert r.json() == {"credentials": "present", "authStyle": "jwt"}


def test_healthz_present_api_key_style() -> None:
    settings = _settings(vonage_api_key="key-1", vonage_api_secret="secret")
    client = TestClient(create_app(settings))
    r = client.get("/healthz")
    assert r.json() == {"credentials": "present", "authStyle": "api_key"}


def test_healthz_prefers_jwt_when_both_present() -> None:
    settings = _settings(
        vonage_application_id="app-1",
        vonage_private_key="key",
        vonage_api_key="key-1",
        vonage_api_secret="secret",
    )
    client = TestClient(create_app(settings))
    r = client.get("/healthz")
    assert r.json()["authStyle"] == "jwt"
