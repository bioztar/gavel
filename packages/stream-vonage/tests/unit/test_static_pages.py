from __future__ import annotations

from fastapi.testclient import TestClient


def test_publisher_page_serves_and_interpolates_poll_interval(client: TestClient) -> None:
    r = client.get("/publisher")
    assert r.status_code == 200
    assert "__BRAIN_POLL_MS__" not in r.text
    assert "1000000" in r.text  # brain_state_poll_seconds=1000.0 (fixture) * 1000
    assert "audioSource" in r.text


def test_watch_page_serves(client: TestClient) -> None:
    r = client.get("/watch")
    assert r.status_code == 200
    assert "hls.js" in r.text.lower() or "Hls" in r.text
