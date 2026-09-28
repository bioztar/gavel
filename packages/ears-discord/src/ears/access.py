"""Who may reach ears: the brain over the seam, operators at the console.

Two credentials, both from settings, neither ever logged:

- ``SEAM_SHARED_SECRET`` — the ears<->brain seam (docs/CONTRACT.md §2). The brain
  presents it as an ``X-Seam-Secret`` header on the WebSocket handshake and on
  every store call. Set: a missing or wrong header is refused, compared in
  constant time. Empty: no check — a laptop with both halves on loopback.
- ``GAVEL_CONSOLE_USERS`` — htpasswd bcrypt lines, the same value the Traefik
  route uses (``scripts/set-console-auth.sh`` writes it; ``$$`` is accepted as
  ``$``). HTTP Basic on the console page, ``/live`` and every ``/api/`` route.
  A request carrying the seam secret passes too: that is the brain's store.

``CONSOLE_AUTH_REQUIRED`` is true by default. With it on and no users configured
the console answers 503 rather than open up; ``false`` is for a developer's own
machine only. ``/health`` is always open — it is docker's healthcheck.
"""

from __future__ import annotations

import base64
import binascii
import secrets
from collections.abc import Awaitable, Callable, Mapping

import bcrypt
from fastapi import FastAPI, Request, Response, WebSocket
from fastapi.responses import JSONResponse

from .logging import get_logger
from .settings import Settings

logger = get_logger(__name__)

SEAM_HEADER = "x-seam-secret"
OPEN_PATHS = frozenset({"/health"})
CHALLENGE = {"WWW-Authenticate": 'Basic realm="gavel console"'}


def seam_ok(settings: Settings, headers: Mapping[str, str]) -> bool:
    """True when no secret is configured, or the request carries the right one."""
    expected = settings.seam_shared_secret
    if not expected:
        return True
    presented = headers.get(SEAM_HEADER)
    if presented is None:
        return False
    return secrets.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))


def console_users(settings: Settings) -> dict[str, bytes]:
    """`user: bcrypt hash` from htpasswd lines separated by commas or newlines."""
    users: dict[str, bytes] = {}
    for line in settings.gavel_console_users.replace("$$", "$").replace("\n", ",").split(","):
        user, sep, digest = line.strip().partition(":")
        if sep and user and digest:
            users[user] = digest.encode("utf-8")
    return users


def basic_ok(users: Mapping[str, bytes], headers: Mapping[str, str]) -> bool:
    scheme, _, rest = headers.get("authorization", "").partition(" ")
    if scheme.lower() != "basic":
        return False
    try:
        decoded = base64.b64decode(rest.strip(), validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False
    user, sep, password = decoded.partition(":")
    digest = users.get(user)
    if not sep or digest is None:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), digest)
    except ValueError:  # not a bcrypt hash at all
        return False


def refuse_operator(settings: Settings, headers: Mapping[str, str]) -> Response | None:
    """None when the request may reach the console; otherwise the response to send."""
    if settings.seam_shared_secret and headers.get(SEAM_HEADER) is not None:
        if seam_ok(settings, headers):
            return None
        return JSONResponse({"detail": "wrong seam secret"}, status_code=401)
    if not settings.console_auth_required:
        return None
    users = console_users(settings)
    if not users:
        return JSONResponse(
            {
                "detail": "console auth is not configured: set GAVEL_CONSOLE_USERS "
                "(scripts/set-console-auth.sh), or CONSOLE_AUTH_REQUIRED=false for "
                "local development only"
            },
            status_code=503,
        )
    if basic_ok(users, headers):
        return None
    return JSONResponse({"detail": "console credentials required"}, 401, headers=CHALLENGE)


async def admit_brain(ws: WebSocket, settings: Settings) -> bool:
    """Accept the brain's socket, or refuse the handshake (policy violation, 1008)."""
    if not seam_ok(settings, ws.headers):
        logger.warning("access.seam_refused", path=ws.url.path)
        await ws.close(code=1008)
        return False
    await ws.accept()
    return True


async def admit_operator(ws: WebSocket, settings: Settings) -> bool:
    if refuse_operator(settings, ws.headers) is not None:
        logger.warning("access.console_refused", path=ws.url.path)
        await ws.close(code=1008)
        return False
    await ws.accept()
    return True


def install(api: FastAPI, settings: Settings) -> None:
    """Gate every HTTP route but `/health`; the sockets call `admit_*` themselves."""
    if not settings.seam_shared_secret:
        logger.warning("access.seam_open", reason="SEAM_SHARED_SECRET unset")
    if not settings.console_auth_required:
        logger.warning("access.console_open", reason="CONSOLE_AUTH_REQUIRED=false")

    @api.middleware("http")
    async def console_gate(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in OPEN_PATHS:
            return await call_next(request)
        refused = refuse_operator(settings, request.headers)
        return refused if refused is not None else await call_next(request)
