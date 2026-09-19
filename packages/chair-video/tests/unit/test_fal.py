"""Queue submit/poll/fetch logic, fal mocked via pytest-httpx. No network."""

from __future__ import annotations

import pytest

from chair_video.fal import FalClient, FalError
from chair_video.settings import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(fal_key="test-key", fal_poll_interval_s=0.0, fal_poll_timeout_s=5.0)


def test_run_polls_until_completed(httpx_mock, settings: Settings) -> None:
    httpx_mock.add_response(
        url="https://queue.fal.run/some/model",
        json={
            "status": "IN_QUEUE",
            "status_url": "https://queue.fal.run/status",
            "response_url": "https://queue.fal.run/response",
        },
    )
    httpx_mock.add_response(url="https://queue.fal.run/status", json={"status": "IN_PROGRESS"})
    httpx_mock.add_response(url="https://queue.fal.run/status", json={"status": "COMPLETED"})
    httpx_mock.add_response(
        url="https://queue.fal.run/response", json={"video": {"url": "https://cdn/out.mp4"}}
    )

    with FalClient(settings) as fal:
        result = fal.run("some/model", {"video_url": "https://cdn/in.mp4"})

    assert result.data["video"]["url"] == "https://cdn/out.mp4"
    assert result.latency_ms >= 0


def test_run_raises_on_error_status(httpx_mock, settings: Settings) -> None:
    httpx_mock.add_response(
        url="https://queue.fal.run/some/model",
        json={
            "status": "IN_QUEUE",
            "status_url": "https://queue.fal.run/status",
            "response_url": "https://queue.fal.run/response",
        },
    )
    httpx_mock.add_response(url="https://queue.fal.run/status", json={"status": "ERROR"})
    httpx_mock.add_response(url="https://queue.fal.run/response", json={"error": "boom"})

    with FalClient(settings) as fal, pytest.raises(FalError, match="fal job failed"):
        fal.run("some/model", {})


def test_run_times_out(httpx_mock) -> None:
    # timeout=0 means the deadline is already past by the time the poll loop
    # checks it, so this only ever needs the submit response.
    settings = Settings(fal_key="test-key", fal_poll_interval_s=0.0, fal_poll_timeout_s=0.0)
    httpx_mock.add_response(
        url="https://queue.fal.run/some/model",
        json={
            "status": "IN_QUEUE",
            "status_url": "https://queue.fal.run/status",
            "response_url": "https://queue.fal.run/response",
        },
    )

    with FalClient(settings) as fal, pytest.raises(FalError, match="timed out"):
        fal.run("some/model", {})


def test_run_missing_status_url_raises(httpx_mock, settings: Settings) -> None:
    httpx_mock.add_response(url="https://queue.fal.run/some/model", json={"status": "IN_QUEUE"})

    with FalClient(settings) as fal, pytest.raises(FalError, match="missing status_url"):
        fal.run("some/model", {})


def test_upload_two_step_flow(httpx_mock, settings: Settings) -> None:
    httpx_mock.add_response(
        url="https://rest.fal.ai/storage/auth/token?storage_type=fal-cdn-v3",
        json={"token": "tok", "token_type": "Bearer", "base_url": "https://v3.fal.media"},
    )
    httpx_mock.add_response(
        url="https://v3.fal.media/files/upload", json={"access_url": "https://cdn/file.wav"}
    )

    with FalClient(settings) as fal:
        url = fal.upload(b"raw-bytes", "audio/wav", "speak.wav")

    assert url == "https://cdn/file.wav"


def test_missing_fal_key_raises_without_key_in_message() -> None:
    settings = Settings(fal_key="")
    with pytest.raises(FalError) as exc_info:
        FalClient(settings)
    assert str(exc_info.value) == "FAL_KEY is not set"
