"""GET /brain-state — a same-origin proxy of brain's GET /state, mocked via
pytest-httpx (the one endpoint that makes a real httpx call, to an address
that's `http://127.0.0.1:8788/state` by default and never leaves the mock)."""

from __future__ import annotations

import httpx
from fastapi.testclient import TestClient
from pytest_httpx import HTTPXMock


def test_brain_state_proxies_brain_response(client: TestClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="http://127.0.0.1:8788/state", json={"agenda": ["item-1"], "interventions": []}
    )
    r = client.get("/brain-state")
    assert r.status_code == 200
    assert r.json() == {"agenda": ["item-1"], "interventions": []}


def test_brain_state_unreachable_is_502(client: TestClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(httpx.ConnectError("connection refused"))
    r = client.get("/brain-state")
    assert r.status_code == 502
