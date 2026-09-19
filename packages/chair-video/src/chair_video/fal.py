"""Thin client for fal's queue API and its CDN upload.

Queue: POST to `https://queue.fal.run/<model>` starts a job and returns a
`status_url` and a `response_url`. Poll the former until `status ==
"COMPLETED"`, then GET the latter for the result. See
https://fal.ai/docs for the model-specific input/output shapes.

Upload: fal's `*_url` input fields validate as URLs (~2KB max) — a base64
data URI works only for trivial payloads, so any real image/audio/video goes
through fal's CDN first. Two calls, confirmed against the official
`fal-client` package's implementation (`fal_client/client.py`, functions
`CDNTokenManager._refresh_token` and `_upload_v3`), since fal's own docs
don't spell out the raw REST contract:
  1. POST {REST_URL}/storage/auth/token?storage_type=fal-cdn-v3 with the
     `FAL_KEY` header, body `{}` -> {"token", "token_type", "base_url", ...}
  2. POST {CDN_URL}/files/upload with `Authorization: <token_type> <token>`,
     `Content-Type: <content_type>`, `X-Fal-File-Name: <file_name>`, and the
     raw bytes as the body -> {"access_url": "..."}
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from chair_video.settings import Settings

REST_URL = "https://rest.fal.ai"
CDN_URL = "https://v3.fal.media"


class FalError(RuntimeError):
    """A fal queue job failed, timed out, or fal itself errored."""


@dataclass(frozen=True)
class FalResult:
    data: dict[str, Any]
    latency_ms: int


class FalClient:
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        if not settings.fal_configured:
            raise FalError("FAL_KEY is not set")
        self._settings = settings
        self._client = client or httpx.Client(timeout=30.0)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> FalClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Key {self._settings.fal_key}",
            "Content-Type": "application/json",
        }

    def submit(self, model: str, arguments: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._settings.fal_base_url}/{model}"
        response = self._client.post(url, json=arguments, headers=self._headers())
        response.raise_for_status()
        return response.json()

    def poll_status(self, status_url: str) -> dict[str, Any]:
        response = self._client.get(status_url, headers=self._headers())
        response.raise_for_status()
        return response.json()

    def upload(self, data: bytes, content_type: str, file_name: str) -> str:
        """Upload bytes to fal's CDN, returns the `access_url` to pass as a
        `*_url` model input. See module docstring for the two-step flow."""
        token_response = self._client.post(
            f"{REST_URL}/storage/auth/token?storage_type=fal-cdn-v3",
            headers={
                "Authorization": f"Key {self._settings.fal_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={},
        )
        token_response.raise_for_status()
        token = token_response.json()

        upload_response = self._client.post(
            f"{CDN_URL}/files/upload",
            content=data,
            headers={
                "Authorization": f"{token['token_type']} {token['token']}",
                "Content-Type": content_type,
                "X-Fal-File-Name": file_name,
            },
        )
        upload_response.raise_for_status()
        return upload_response.json()["access_url"]

    def fetch_result(self, response_url: str) -> dict[str, Any]:
        response = self._client.get(response_url, headers=self._headers())
        response.raise_for_status()
        return response.json()

    def run(self, model: str, arguments: dict[str, Any]) -> FalResult:
        """Submit a job and block until it completes. Returns the result payload
        plus the measured submit-to-result wall-clock latency."""
        started = time.monotonic()
        queued = self.submit(model, arguments)
        status_url = queued.get("status_url")
        response_url = queued.get("response_url")
        if not status_url or not response_url:
            raise FalError(f"fal submit response missing status_url/response_url: {queued}")

        deadline = started + self._settings.fal_poll_timeout_s
        status = queued.get("status", "IN_QUEUE")
        while status not in ("COMPLETED", "ERROR"):
            if time.monotonic() > deadline:
                raise FalError(f"fal job timed out after {self._settings.fal_poll_timeout_s}s")
            time.sleep(self._settings.fal_poll_interval_s)
            polled = self.poll_status(status_url)
            status = polled.get("status", status)

        if status == "ERROR":
            raise FalError(f"fal job failed: {self.fetch_result(response_url)}")

        data = self.fetch_result(response_url)
        latency_ms = int((time.monotonic() - started) * 1000)
        return FalResult(data=data, latency_ms=latency_ms)
