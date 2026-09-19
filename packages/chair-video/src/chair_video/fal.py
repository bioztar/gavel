"""Thin client for fal's queue API.

POST to `https://queue.fal.run/<model>` starts a job and returns a
`status_url` and a `response_url`. Poll the former until `status ==
"COMPLETED"`, then GET the latter for the result. See
https://fal.ai/docs for the model-specific input/output shapes.
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from typing import Any

import httpx

from chair_video.settings import Settings


class FalError(RuntimeError):
    """A fal queue job failed, timed out, or fal itself errored."""


@dataclass(frozen=True)
class FalResult:
    data: dict[str, Any]
    latency_ms: int


def to_data_uri(content: bytes, content_type: str) -> str:
    """Inline a small file as a data URI — fal accepts these anywhere a `*_url`
    field is documented, so short audio clips need no separate upload step."""
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


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
