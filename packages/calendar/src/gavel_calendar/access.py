"""Who may reach the operator routes, and how often.

`/compose*`, `/architecture` and `/demo-script` are for the host, not for a
meeting's attendees, and the compose lane spends LLM and email credit on every
post. Two gates, both configured in `settings.py`:

- **auth** — `Authorization: Bearer <CALENDAR_ADMIN_TOKEN>`, or HTTP Basic with
  the token as the password (any username) so a plain browser can prompt for it.
  Compared in constant time. Fail-closed: with `CALENDAR_AUTH_REQUIRED` true (the
  default) and no token set, the routes answer 503 rather than open up.
  `CALENDAR_AUTH_REQUIRED=false` is for a laptop only — never in compose.
- **rate limit** — per client IP via `slowapi`, `CALENDAR_RATE_LIMIT` (a `limits`
  string such as `30/minute`). The limit is checked before the token, so a
  wrong-password loop is throttled too.

Never log the token or the header that carries it.
"""

from __future__ import annotations

import base64
import binascii
import secrets

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .settings import Settings

limiter = Limiter(key_func=get_remote_address)


def rate_limited(_request: Request, exc: Exception) -> Response:
    """The 429. Typed on `Exception` so it fits Starlette's handler signature."""
    detail = exc.detail if isinstance(exc, RateLimitExceeded) else str(exc)
    return JSONResponse({"error": f"Rate limit exceeded: {detail}"}, status_code=429)


def presented_token(request: Request) -> str | None:
    """The credential in the request, whichever of the two forms carried it."""
    header = request.headers.get("authorization", "")
    scheme, _, rest = header.partition(" ")
    rest = rest.strip()
    if scheme.lower() == "bearer":
        return rest or None
    if scheme.lower() == "basic":
        try:
            decoded = base64.b64decode(rest, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            return None
        _user, sep, password = decoded.partition(":")
        return password if sep else None
    return None


def token_matches(presented: str | None, expected: str) -> bool:
    if presented is None or not expected:
        return False
    return secrets.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))


def require_operator(request: Request, settings: Settings) -> None:
    """Raise unless the request carries the admin token (or auth is switched off)."""
    if not settings.calendar_auth_required:
        return
    expected = settings.calendar_admin_token
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="CALENDAR_ADMIN_TOKEN is not set; set it, or CALENDAR_AUTH_REQUIRED=false "
            "for local development only",
        )
    if not token_matches(presented_token(request), expected):
        raise HTTPException(
            status_code=401,
            detail="operator token required",
            headers={"WWW-Authenticate": 'Basic realm="gavel compose", Bearer'},
        )
