"""access.py: the seam secret on the brain's socket, basic auth on the console."""

from __future__ import annotations

import base64
from typing import Any

import bcrypt
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from ears.app import Ears
from ears.bus import Bus
from ears.db.store import Store
from ears.settings import Settings
from ears.wire import create_api

SECRET = "seam-test-secret"
# htpasswd -B output for user `karen`, low cost so the suite stays quick; `$$` is how
# scripts/set-console-auth.sh writes it into .env for compose.
HASH = bcrypt.hashpw(b"correct horse", bcrypt.gensalt(rounds=4)).decode()
USERS_LINE = f"karen:{HASH}".replace("$", "$$")


def make_client(**overrides: Any) -> TestClient:
    settings = Settings(_env_file=None, slng_api_key="k", stt_mode="http", **overrides)  # type: ignore[call-arg]
    return TestClient(create_api(Ears(settings, Store(None), Bus(None, "t", 10), None)))


def basic(user: str, password: str) -> dict[str, str]:
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()}


# --- the seam ---------------------------------------------------------------------------


def test_brain_socket_accepts_the_right_seam_secret() -> None:
    client = make_client(seam_shared_secret=SECRET, console_auth_required=False)
    with client.websocket_connect("/", headers={"X-Seam-Secret": SECRET}) as ws:
        assert ws.receive_json()["type"] == "voice"


@pytest.mark.parametrize("headers", [{}, {"X-Seam-Secret": "nope"}, {"X-Seam-Secret": ""}])
def test_brain_socket_refuses_a_missing_or_wrong_seam_secret(headers: dict[str, str]) -> None:
    client = make_client(seam_shared_secret=SECRET, console_auth_required=False)
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/", headers=headers):
        pass


def test_empty_seam_secret_is_not_enforced() -> None:
    client = make_client(console_auth_required=False)
    with client.websocket_connect("/") as ws:
        assert ws.receive_json()["type"] == "voice"


def test_the_brains_store_calls_pass_with_the_seam_secret() -> None:
    client = make_client(seam_shared_secret=SECRET, gavel_console_users=USERS_LINE)
    assert client.get("/api/status").status_code == 401
    assert client.get("/api/status", headers={"X-Seam-Secret": "nope"}).status_code == 401
    assert client.get("/api/status", headers={"X-Seam-Secret": SECRET}).status_code == 200


# --- the console ------------------------------------------------------------------------


def test_console_is_behind_basic_auth_by_default() -> None:
    client = make_client(gavel_console_users=USERS_LINE)
    resp = client.get("/api/status")
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"].startswith("Basic")
    assert client.get("/console").status_code == 401
    assert client.get("/api/status", headers=basic("karen", "wrong")).status_code == 401
    assert client.get("/api/status", headers=basic("nobody", "correct horse")).status_code == 401
    assert client.get("/api/status", headers=basic("karen", "correct horse")).status_code == 200
    assert client.get("/console", headers=basic("karen", "correct horse")).status_code == 200


def test_live_socket_takes_the_same_credentials() -> None:
    client = make_client(gavel_console_users=USERS_LINE)
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/live"):
        pass
    with client.websocket_connect("/live", headers=basic("karen", "correct horse")) as ws:
        assert ws.receive_json()["type"] == "console.hello"


def test_health_is_always_open() -> None:
    assert make_client(gavel_console_users=USERS_LINE).get("/health").status_code == 200
    assert make_client().get("/health").status_code == 200


def test_no_users_configured_fails_closed() -> None:
    resp = make_client().get("/api/status")
    assert resp.status_code == 503
    assert "GAVEL_CONSOLE_USERS" in resp.text


def test_explicit_opt_out_opens_the_console() -> None:
    assert make_client(console_auth_required=False).get("/api/status").status_code == 200
