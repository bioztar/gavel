"""/speak-video and /idle behavior end-to-end against the FastAPI app, with fal
mocked via pytest-httpx. No network, no real fal credits."""

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from chair_video.app import create_app
from chair_video.settings import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(fal_key="test-key", fal_poll_interval_s=0.0, fal_poll_timeout_s=5.0)


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


def _mock_fal_upload(httpx_mock, url: str) -> None:
    httpx_mock.add_response(
        url="https://rest.fal.ai/storage/auth/token?storage_type=fal-cdn-v3",
        json={"token": "tok", "token_type": "Bearer", "base_url": "https://v3.fal.media"},
    )
    httpx_mock.add_response(url="https://v3.fal.media/files/upload", json={"access_url": url})


def _mock_fal_run(httpx_mock, model: str, video_url: str) -> None:
    httpx_mock.add_response(
        url=f"https://queue.fal.run/{model}",
        json={
            "status": "COMPLETED",
            "status_url": "https://queue.fal.run/status",
            "response_url": "https://queue.fal.run/response",
        },
    )
    httpx_mock.add_response(url="https://queue.fal.run/response", json={"video": {"url": video_url}})


def test_idle_defaults_to_configured_persona(client: TestClient) -> None:
    r = client.get("/idle")
    assert r.status_code == 200
    assert r.headers["content-type"] == "video/mp4"


def test_idle_unknown_persona_falls_back_to_default(client: TestClient) -> None:
    default = client.get("/idle", params={"persona": "funky"})
    typo = client.get("/idle", params={"persona": "not-a-real-persona"})
    assert typo.status_code == 200
    assert typo.content == default.content


def test_speak_video_requires_audio(client: TestClient) -> None:
    r = client.post("/speak-video", json={})
    assert r.status_code == 422


def test_speak_video_uses_video_url_payload(httpx_mock, client: TestClient) -> None:
    # Two uploads: audio, then the persona idle loop.
    _mock_fal_upload(httpx_mock, "https://cdn/audio.wav")
    _mock_fal_upload(httpx_mock, "https://cdn/idle.mp4")
    _mock_fal_run(httpx_mock, "veed/lipsync/v2", "https://cdn/result.mp4")

    audio_b64 = base64.b64encode(b"fake-wav-bytes").decode()
    r = client.post(
        "/speak-video",
        json={"audioBase64": audio_b64, "format": "wav", "persona": "formal"},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["videoUrl"] == "https://cdn/result.mp4"

    run_request = next(
        req for req in httpx_mock.get_requests() if req.url.path == "/veed/lipsync/v2"
    )
    import json as _json

    payload = _json.loads(run_request.content)
    assert payload["video_url"] == "https://cdn/idle.mp4"
    assert "image_url" not in payload


def test_speak_video_cache_hit_skips_second_fal_run(httpx_mock, client: TestClient) -> None:
    _mock_fal_upload(httpx_mock, "https://cdn/audio.wav")
    _mock_fal_upload(httpx_mock, "https://cdn/idle.mp4")
    _mock_fal_run(httpx_mock, "veed/lipsync/v2", "https://cdn/result.mp4")

    audio_b64 = base64.b64encode(b"repeated-line").decode()
    body = {"audioBase64": audio_b64, "format": "wav"}

    first = client.post("/speak-video", json=body)
    assert first.status_code == 200
    requests_after_first = len(httpx_mock.get_requests())

    second = client.post("/speak-video", json=body)
    assert second.status_code == 200
    assert second.json()["videoUrl"] == first.json()["videoUrl"]
    assert second.json()["latencyMs"] == 0
    assert len(httpx_mock.get_requests()) == requests_after_first


def test_speak_video_unknown_persona_falls_back_not_422(httpx_mock, client: TestClient) -> None:
    _mock_fal_upload(httpx_mock, "https://cdn/audio.wav")
    _mock_fal_upload(httpx_mock, "https://cdn/idle.mp4")
    _mock_fal_run(httpx_mock, "veed/lipsync/v2", "https://cdn/result.mp4")

    audio_b64 = base64.b64encode(b"typo-persona-line").decode()
    r = client.post(
        "/speak-video",
        json={"audioBase64": audio_b64, "format": "wav", "persona": "not-a-real-persona"},
    )
    assert r.status_code == 200
