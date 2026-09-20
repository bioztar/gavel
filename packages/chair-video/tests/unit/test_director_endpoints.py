"""/director/* endpoints against the FastAPI app, fal mocked via pytest-httpx.
No network, no real fal credits, no real WebRTC — those are the stage page's
job (verified against real fal in the Phase 0 spike, see README/mission)."""

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from chair_video.app import create_app
from chair_video.settings import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(fal_key="test-key")


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


def _mock_fal_upload(httpx_mock, url: str) -> None:
    httpx_mock.add_response(
        url="https://rest.fal.ai/storage/auth/token?storage_type=fal-cdn-v3",
        json={"token": "tok", "token_type": "Bearer", "base_url": "https://v3.fal.media"},
    )
    httpx_mock.add_response(url="https://v3.fal.media/files/upload", json={"access_url": url})


def test_healthz_reports_inactive_director(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["director"] == {"active": False}


def test_session_start_then_healthz_reports_active(client: TestClient) -> None:
    r = client.post("/director/session/start", json={"persona": "funky"})
    assert r.status_code == 200
    assert r.json()["persona"] == "funky"

    health = client.get("/healthz").json()
    assert health["director"]["active"] is True
    assert health["director"]["persona"] == "funky"


def test_session_start_requires_fal_key() -> None:
    client = TestClient(create_app(Settings(fal_key="")))
    r = client.post("/director/session/start", json={})
    assert r.status_code == 500
    assert r.json()["detail"] == "FAL_KEY is not set"


def test_session_stop_clears_state(client: TestClient) -> None:
    client.post("/director/session/start", json={})
    r = client.post("/director/session/stop")
    assert r.status_code == 200
    assert client.get("/healthz").json()["director"] == {"active": False}


def test_speak_uploads_audio_and_returns_incremented_prompt_version(
    httpx_mock, client: TestClient
) -> None:
    _mock_fal_upload(httpx_mock, "https://cdn/audio.wav")
    audio_b64 = base64.b64encode(b"fake-wav-bytes").decode()

    r = client.post(
        "/director/speak", json={"audioBase64": audio_b64, "format": "wav", "persona": "funky"}
    )

    assert r.status_code == 200
    body = r.json()
    assert body["promptVersion"] == 2


def test_heartbeat_rejects_unknown_token(client: TestClient) -> None:
    r = client.post("/director/heartbeat", json={"token": "bogus", "state": "live"})
    assert r.status_code == 404


def test_heartbeat_accepts_valid_session_token(httpx_mock, client: TestClient) -> None:
    _mock_fal_upload(httpx_mock, "https://cdn/audio.wav")
    audio_b64 = base64.b64encode(b"fake-wav-bytes").decode()
    client.post("/director/speak", json={"audioBase64": audio_b64, "format": "wav"})

    director = client.app.state.director  # type: ignore[attr-defined]
    token = director._session.token

    r = client.post("/director/heartbeat", json={"token": token, "state": "live"})
    assert r.status_code == 200


def test_fal_proxy_rejects_missing_token(client: TestClient) -> None:
    r = client.post(
        "/director/fal-proxy",
        headers={"x-fal-target-url": "https://wma.fal.run/ice"},
        content=b"{}",
    )
    assert r.status_code == 401


def test_fal_proxy_rejects_non_allowlisted_host(httpx_mock, client: TestClient) -> None:
    _mock_fal_upload(httpx_mock, "https://cdn/audio.wav")
    audio_b64 = base64.b64encode(b"fake-wav-bytes").decode()
    client.post("/director/speak", json={"audioBase64": audio_b64, "format": "wav"})
    director = client.app.state.director  # type: ignore[attr-defined]
    token = director._session.token

    r = client.post(
        "/director/fal-proxy",
        headers={"x-fal-target-url": "https://evil.example.com/steal", "x-director-token": token},
        content=b"{}",
    )
    assert r.status_code == 403


def test_fal_proxy_forwards_allowlisted_request_with_key_attached(
    httpx_mock, client: TestClient
) -> None:
    _mock_fal_upload(httpx_mock, "https://cdn/audio.wav")
    audio_b64 = base64.b64encode(b"fake-wav-bytes").decode()
    client.post("/director/speak", json={"audioBase64": audio_b64, "format": "wav"})
    director = client.app.state.director  # type: ignore[attr-defined]
    token = director._session.token

    httpx_mock.add_response(url="https://wma.fal.run/ice", json={"iceServers": []})

    r = client.post(
        "/director/fal-proxy",
        headers={
            "x-fal-target-url": "https://wma.fal.run/ice",
            "x-director-token": token,
            "authorization": "Bearer client-supplied-should-be-stripped",
        },
        content=b"{}",
    )

    assert r.status_code == 200
    forwarded = next(req for req in httpx_mock.get_requests() if req.url.host == "wma.fal.run")
    assert forwarded.headers["authorization"] == "Key test-key"
