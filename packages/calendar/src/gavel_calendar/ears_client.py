"""The one call into `ears-discord`: create its meeting, then start a session
on it. This is the existing entry point (`packages/ears-discord/src/ears/wire.py`,
`POST /api/meetings` + `POST /api/sessions`) — see the mission's own rule: read
`ears`, never edit it, never invent a second session concept.
"""

from __future__ import annotations

from typing import Any

import httpx


class EarsError(RuntimeError):
    """ears-discord rejected or could not be reached for the call."""


class EarsClient:
    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def create_meeting(self, title: str, context: str, agenda: dict[str, Any]) -> str:
        body = {"title": title, "context": context, "agenda": agenda}
        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
            try:
                resp = await client.post("/api/meetings", json=body)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise EarsError(f"POST /api/meetings failed: {exc}") from exc
        return resp.json()["id"]

    async def start_session(self, meeting_id: str) -> str:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
            try:
                resp = await client.post("/api/sessions", json={"meetingId": meeting_id})
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise EarsError(f"POST /api/sessions failed: {exc}") from exc
        return resp.json()["sessionId"]
