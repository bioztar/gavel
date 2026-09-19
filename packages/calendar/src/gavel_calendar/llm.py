"""Free-text brief → strict JSON via Nebius Token Factory (OpenAI-compatible
chat/completions) → a validated, editable `ParsedBrief`.

Never raises on a bad response: an unreachable endpoint, a non-JSON reply, or
JSON that fails validation all return `None`, and the caller (`compose.py`)
renders the confirm form with the raw brief and empty fields instead of a
500 — Vitaly can type the agenda himself and the demo continues.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

import httpx
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

# Winner of the brain's own bake-off for short, latency-bound JSON calls
# (packages/brain/config/models.yaml, `profiles.fast`) — reused here rather
# than re-run, since this is the same kind of call. `NEBIUS_MODEL` in `.env`
# is unset on purpose; this is pinned in code, not settings.
MODEL = "Qwen/Qwen3-30B-A3B-Instruct-2507"

_SYSTEM_PROMPT = """You turn a short, spoken-style meeting brief into strict JSON. \
Reply with ONLY a JSON object — no prose, no markdown code fences — matching exactly \
this shape:
{{"title": string, "start": ISO-8601 datetime with a UTC offset, "duration_minutes": \
integer, "topics": [{{"title": string, "minutes": integer or null, "owner": string \
or null, "must_hear": [string, ...]}}]}}

The current date and time is {now}, timezone {timezone}. Resolve every relative time \
in the brief ("in one hour", "tomorrow at 10", "half an hour") against that clock, \
and always emit "start" with the {timezone} UTC offset — you have no other clock. \
Known attendees: {attendees}. Use their names, never their emails, for "owner" and \
"must_hear" when the brief names them. If duration is unstated, use 30. If no topics \
are stated, use an empty list. If minutes for a topic are unstated, use null rather \
than guessing."""


class BriefTopic(BaseModel):
    title: str
    minutes: int | None = None
    owner: str | None = None
    must_hear: list[str] = Field(default_factory=list)


class ParsedBrief(BaseModel):
    title: str
    start: datetime
    duration_minutes: int = Field(gt=0)
    topics: list[BriefTopic] = Field(default_factory=list)


def _strip_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        stripped = stripped.removeprefix("json").strip()
    return stripped


class NebiusClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 15.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    async def parse_brief(
        self,
        brief: str,
        *,
        now: datetime,
        timezone: str,
        attendees: list[str],
    ) -> ParsedBrief | None:
        if not self.configured:
            logger.warning("compose.llm_skipped reason=nebius_api_key_unset")
            return None

        system = _SYSTEM_PROMPT.format(
            now=now.isoformat(timespec="minutes"),
            timezone=timezone,
            attendees=", ".join(attendees) or "none listed",
        )
        body = {
            "model": MODEL,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": brief},
            ],
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
                resp = await client.post("/chat/completions", json=body, headers=headers)
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            logger.warning("compose.llm_call_failed error=%s", type(exc).__name__)
            return None

        try:
            data = json.loads(_strip_fences(content))
            return ParsedBrief.model_validate(data)
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            logger.warning("compose.llm_parse_failed error=%s", type(exc).__name__)
            return None
