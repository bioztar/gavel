"""access.py: the seam secret on the brain's socket, basic auth on /live and /api."""

from __future__ import annotations

import base64
from typing import Any

import bcrypt
import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

from conftest import Harness, make_settings
from ears_meet.wire import create_api

SECRET = "seam-test-secret"
HASH = bcrypt.hashpw(b"correct horse", bcrypt.gensalt(rounds=4)).decode()
# `$$` is how scripts/set-console-auth.sh writes the hash into .env for compose.
USERS_LINE = f"karen:{HASH}".replace("$", "$$")


def make_client(**overrides: Any) -> TestClient:
    return TestClient(create_api(Harness(make_settings(**overrides)).ears))


def basic(user: str, password: str) -> dict[str, str]:
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()}


def test_brain_socket_accepts_the_right_seam_secret() -> None:
    client = make_client(seam_shared_secret=SECRET)
    with client.websocket_connect("/", headers={"X-Seam-Secret": SECRET}) as ws:
        assert ws.receive_json()["type"] == "voice"


@pytest.mark.parametrize("headers", [{}, {"X-Seam-Secret": "nope"}, {"X-Seam-Secret": ""}])
def test_brain_socket_refuses_a_missing_or_wrong_seam_secret(headers: dict[str, str]) -> None:
    client = make_client(seam_shared_secret=SECRET)
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/", headers=headers):
        pass


def test_empty_seam_secret_is_not_enforced() -> None:
    with make_client().websocket_connect("/") as ws:
        assert ws.receive_json()["type"] == "voice"


def test_the_brains_store_calls_pass_with_the_seam_secret() -> None:
    client = make_client(
        seam_shared_secret=SECRET, console_auth_required=True, gavel_console_users=USERS_LINE
    )
    assert client.get("/api/status").status_code == 401
    assert client.get("/api/status", headers={"X-Seam-Secret": "nope"}).status_code == 401
    assert client.get("/api/status", headers={"X-Seam-Secret": SECRET}).status_code == 200


def test_api_and_live_are_behind_basic_auth_by_default() -> None:
    client = make_client(console_auth_required=True, gavel_console_users=USERS_LINE)
    resp = client.get("/api/status")
    assert resp.status_code == 401 and resp.headers["www-authenticate"].startswith("Basic")
    assert client.get("/api/status", headers=basic("karen", "wrong")).status_code == 401
    assert client.get("/api/status", headers=basic("karen", "correct horse")).status_code == 200
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/live"):
        pass
    with client.websocket_connect("/live", headers=basic("karen", "correct horse")) as ws:
        assert ws.receive_json()["type"] == "console.hello"


def test_health_is_always_open_and_no_users_fails_closed() -> None:
    client = make_client(console_auth_required=True)
    assert client.get("/health").status_code == 200
    resp = client.get("/api/status")
    assert resp.status_code == 503 and "GAVEL_CONSOLE_USERS" in resp.text


def test_explicit_opt_out_opens_the_api() -> None:
    assert make_client(console_auth_required=False).get("/api/status").status_code == 200
