from __future__ import annotations

from fastapi.testclient import TestClient

from tests.unit.conftest import FakeVonage


def test_status_inactive_before_start(client: TestClient) -> None:
    r = client.get("/stream/status")
    assert r.json() == {"active": False, "sessionId": None, "hlsUrl": None, "archiveId": None}


def test_status_active_after_start(client: TestClient, fake_vonage: FakeVonage) -> None:
    client.post("/stream/start")
    r = client.get("/stream/status")
    body = r.json()
    assert body["active"] is True
    assert body["sessionId"] == "sess-1"
    assert body["hlsUrl"] == "https://example.invalid/hls.m3u8"
    assert body["archiveId"] == "arc-1"
    client.post("/stream/stop")


def test_status_inactive_again_after_stop(client: TestClient, fake_vonage: FakeVonage) -> None:
    client.post("/stream/start")
    client.post("/stream/stop")
    r = client.get("/stream/status")
    assert r.json()["active"] is False
