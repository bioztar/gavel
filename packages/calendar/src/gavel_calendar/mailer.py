"""Resend, dry-run by design.

With no `RESEND_API_KEY` (or no `COMPOSE_FROM_EMAIL`), `send_invite` renders
nothing over the network and returns a non-fatal `MailResult` — this is the
mode tests run in. A live call that Resend rejects, or that the network
drops, degrades the same way. `compose.py` turns any `sent=False` into a
visible "invite email not sent: <reason>" notice; the meeting it is attached
to has already been created and is never rolled back for this.
"""

from __future__ import annotations

import base64
import logging

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_RESEND_URL = "https://api.resend.com/emails"


class MailResult(BaseModel):
    sent: bool
    reason: str | None = None


async def send_invite(
    *,
    api_key: str,
    from_email: str,
    to: list[str],
    subject: str,
    text_body: str,
    ics_bytes: bytes,
    timeout: float = 10.0,
) -> MailResult:
    if not api_key:
        return MailResult(sent=False, reason="not sent (no key)")
    if not from_email:
        return MailResult(sent=False, reason="not sent (COMPOSE_FROM_EMAIL unset)")

    body = {
        "from": from_email,
        "to": to,
        "subject": subject,
        "text": text_body,
        "attachments": [
            {
                "filename": "invite.ics",
                "content": base64.b64encode(ics_bytes).decode("ascii"),
                "content_type": "text/calendar; method=REQUEST",
            }
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(_RESEND_URL, json=body, headers=headers)
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # A status code is not a secret; Resend's response body might echo
        # request fields back — never pass it through.
        reason = f"Resend {exc.response.status_code}"
        logger.warning("compose.mail_failed error=%s", reason)
        return MailResult(sent=False, reason=reason)
    except httpx.HTTPError as exc:
        logger.warning("compose.mail_failed error=%s", type(exc).__name__)
        return MailResult(sent=False, reason=type(exc).__name__)
    return MailResult(sent=True)
