"""POST /stream/start and /stream/stop against a `FakeVonage` — no network,
no credential, `VonageClient` mocked at the module boundary (see
`conftest.py`)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.unit.conftest import FakeVonage


def test_stream_start_returns_hls_url_and_session(
    client: TestClient, fake_vonage: FakeVonage
) -> None:
    r = client.post("/stream/start")
    assert r.status_code == 200
    body = r.json()
    assert body["hlsUrl"] == "https://example.invalid/hls.m3u8"
    assert body["sessionId"] == "sess-1"
    assert body["archiveId"] == "arc-1"
    assert body["broadcastId"] == "bcast-1"
    assert body["token"] == "tok-1"
    assert body["watchUrl"] == "/watch"
    assert body["applicationId"] == "app-1"
    assert body["apiKey"] is None

    r_stop = client.post("/stream/stop")
    assert r_stop.status_code == 200


def test_stream_start_order_is_session_then_archive_then_broadcast(
    client: TestClient, fake_vonage: FakeVonage
) -> None:
    client.post("/stream/start")
    assert fake_vonage.calls[:4] == [
        "create_session",
        "generate_token",
        "start_archive",
        "start_broadcast",
    ]
    client.post("/stream/stop")


def test_stream_start_twice_without_stop_is_conflict(
    client: TestClient, fake_vonage: FakeVonage
) -> None:
    first = client.post("/stream/start")
    assert first.status_code == 200
    second = client.post("/stream/start")
    assert second.status_code == 409
    client.post("/stream/stop")


def test_stream_stop_returns_archive_url(client: TestClient, fake_vonage: FakeVonage) -> None:
    client.post("/stream/start")
    r = client.post("/stream/stop")
    assert r.status_code == 200
    body = r.json()
    assert body["archiveId"] == "arc-1"
    assert body["archiveUrl"] == "https://example.invalid/archive.mp4"
    assert body["hlsUrl"] == "https://example.invalid/hls.m3u8"


def test_stream_stop_without_active_stream_is_conflict(client: TestClient) -> None:
    r = client.post("/stream/stop")
    assert r.status_code == 409


def test_stream_start_missing_credentials_names_the_setting(
    unconfigured_client: TestClient,
) -> None:
    r = unconfigured_client.post("/stream/start")
    assert r.status_code == 503
    assert "VONAGE_APPLICATION_ID" in r.json()["detail"]


def test_stream_start_vonage_rejection_is_502(client: TestClient, fake_vonage: FakeVonage) -> None:
    fake_vonage.fail_on = "create_session"
    r = client.post("/stream/start")
    assert r.status_code == 502


def test_broadcast_failure_rolls_back_the_archive(
    client: TestClient, fake_vonage: FakeVonage
) -> None:
    fake_vonage.fail_on = "start_broadcast"
    r = client.post("/stream/start")
    assert r.status_code == 502
    assert fake_vonage.calls == [
        "create_session",
        "generate_token",
        "start_archive",
        "start_broadcast",
        "stop_archive",
    ]

    # the failed start must not have left a stream "active"
    status = client.get("/stream/status")
    assert status.json()["active"] is False
