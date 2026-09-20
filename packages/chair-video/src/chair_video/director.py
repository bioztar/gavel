"""Session coordinator for the persistent Director WebRTC stream.

The stage page (a browser) owns the actual `RTCPeerConnection` — Python cannot
open one, and can't close one either. This module is the other half: it holds
`FAL_KEY` (via `app.py`'s proxy, not here), decides when a session starts,
rotates, and stops, tracks the strictly-increasing `prompt_version` the fal bridge requires
(see README — a stale or repeated value is silently dropped), and pushes "do
this" commands to the stage page over Server-Sent Events. The stage page
reports back via `heartbeat()`; losing that heartbeat is the only signal this
side has that the browser died, since it can't see the peer connection.

No fal/network calls happen in this module — `app.py` uploads audio and owns
the httpx clients. That keeps this file's tests pure logic, no mocking.
"""

from __future__ import annotations

import asyncio
import json
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from chair_video.settings import Settings

# Pushed to every SSE queue on shutdown; the generator treats it as "stop".
_SHUTDOWN = "__shutdown__"


@dataclass
class DirectorSession:
    session_id: str
    token: str
    persona: str
    prompt_version: int
    scene_number: int
    started_at: float
    last_heartbeat_at: float | None = None
    stage_state: str = "starting"


class DirectorManager:
    """One active session at a time — gavel chairs one meeting at a time."""

    def __init__(self, settings: Settings, now: Callable[[], float] = time.monotonic) -> None:
        self._settings = settings
        self._now = now
        self._session: DirectorSession | None = None
        self._subscribers: list[asyncio.Queue[str]] = []

    # --- lifecycle -----------------------------------------------------

    def start(self, persona: str) -> DirectorSession:
        """Idempotent: a second start() while one is already active just
        returns it, on the same persona/session — restarting mid-meeting
        would cost another session minimum and interrupt the live avatar."""
        if self._session is not None:
            return self._session
        persona = self._settings.normalize_persona(persona)
        session = self._new_session(
            persona,
            scene_number=1,
        )
        self._session = session
        self._broadcast(self._start_event(session))
        return session

    def _new_session(self, persona: str, scene_number: int) -> DirectorSession:
        return DirectorSession(
            session_id=secrets.token_hex(8),
            token=secrets.token_urlsafe(24),
            persona=persona,
            prompt_version=1,
            scene_number=scene_number,
            started_at=self._now(),
        )

    def rotate_scene(self) -> DirectorSession | None:
        """Replace the live generative session without publishing an idle event.

        The stage performs a make-before-break handoff: it keeps the current
        MediaStream visible until the replacement produces its first frame.
        """
        current = self._session
        if current is None:
            return None
        replacement = self._new_session(current.persona, current.scene_number + 1)
        self._session = replacement
        self._broadcast(self._start_event(replacement))
        return replacement

    def stop(self) -> None:
        if self._session is None:
            return
        session_id = self._session.session_id
        self._session = None
        self._broadcast({"type": "stop", "sessionId": session_id})

    def speak(self, audio_url: str, persona: str) -> DirectorSession:
        """Send speech to the active scene, lazily starting only as a fallback."""
        session = self.start(persona)
        session.prompt_version += 1
        self._broadcast(
            {
                "type": "speak",
                "sessionId": session.session_id,
                "promptVersion": session.prompt_version,
                "audioUrl": audio_url,
            }
        )
        return session

    def heartbeat(self, token: str, state: str) -> bool:
        if self._session is None or not secrets.compare_digest(token, self._session.token):
            return False
        self._session.last_heartbeat_at = self._now()
        self._session.stage_state = state
        return True

    def verify_token(self, token: str | None) -> bool:
        """Used by the fal-proxy route: only the stage page holding the
        current session's token may forward requests through it."""
        return (
            token is not None
            and self._session is not None
            and secrets.compare_digest(token, self._session.token)
        )

    # --- SSE -------------------------------------------------------------

    def subscribe(self) -> asyncio.Queue[str]:
        """A (re)connecting stage page gets the current state immediately —
        `start` if a session is live (so a page reload rejoins), `idle`
        otherwise — then streams whatever happens next."""
        queue: asyncio.Queue[str] = asyncio.Queue()
        hello: dict[str, Any] = (
            self._start_event(self._session) if self._session else {"type": "idle"}
        )
        queue.put_nowait(json.dumps(hello))
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def _broadcast(self, event: dict[str, Any]) -> None:
        payload = json.dumps(event)
        for queue in list(self._subscribers):
            queue.put_nowait(payload)

    def _start_event(self, session: DirectorSession) -> dict[str, Any]:
        prompt_by_persona = self._settings.director_prompt_by_persona
        return {
            "type": "start",
            "sessionId": session.session_id,
            "token": session.token,
            "endpointId": self._settings.director_endpoint_id,
            "promptVersion": session.prompt_version,
            "sceneNumber": session.scene_number,
            "prompt": prompt_by_persona.get(
                session.persona, prompt_by_persona[self._settings.default_persona]
            ),
            "resolution": self._settings.director_resolution,
            "aspectRatio": self._settings.director_aspect_ratio,
        }

    # --- housekeeping ------------------------------------------------------

    def sweep(self) -> str | None:
        """Rotate an ageing scene while keeping the meeting's stage active.

        Meeting start/stop is explicit. Silence is normal during a meeting and
        must never be interpreted as the meeting ending. Rotation bounds how
        long the generative model can accumulate visual drift in one session.
        """
        session = self._session
        if session is None:
            return None
        now = self._now()
        if now - session.started_at <= self._settings.director_scene_duration_s:
            return None
        self.rotate_scene()
        return "scene_rotation"

    def close_subscribers(self) -> None:
        """Unblock every SSE generator so uvicorn can actually shut down.

        `/director/events` awaits `queue.get()` forever; on shutdown uvicorn
        waits for those responses to finish, gets nothing, and docker SIGKILLs
        the container ten seconds later (exit 137). A sentinel releases them.
        """
        for queue in list(self._subscribers):
            queue.put_nowait(_SHUTDOWN)
        self._subscribers.clear()

    # --- reporting ---------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """What `/healthz` reports. `state` reflects heartbeat freshness, not
        just what the stage page last claimed — a stage page that vanished
        (crashed tab, yanked wifi) stops sending heartbeats, and this is the
        only way Python notices, since it can't see the peer connection."""
        session = self._session
        if session is None:
            return {"active": False}
        age_s = self._now() - session.started_at
        if session.last_heartbeat_at is None:
            heartbeat_age_s = None
            state = (
                "starting" if age_s < self._settings.director_heartbeat_timeout_s else "degraded"
            )
        else:
            heartbeat_age_s = self._now() - session.last_heartbeat_at
            state = (
                "degraded"
                if heartbeat_age_s > self._settings.director_heartbeat_timeout_s
                else session.stage_state
            )
        return {
            "active": True,
            "sessionId": session.session_id,
            "persona": session.persona,
            "promptVersion": session.prompt_version,
            "sceneNumber": session.scene_number,
            "ageSeconds": round(age_s, 1),
            "heartbeatAgeSeconds": round(heartbeat_age_s, 1)
            if heartbeat_age_s is not None
            else None,
            "state": state,
        }
