"""Typed settings from the environment, the repo-root `.env`, then a local `.env`.

Same pattern as `packages/ears-discord/src/ears/settings.py`. Never log a
setting's value — on a missing/invalid one, raise with its *name* only.

`packages/calendar` is itself sometimes checked out as a git worktree (see
`packages/chair-video/src/chair_video/settings.py`, same fix): the repo-root
`.env` may then live in a sibling checkout rather than two directories up, so
both the worktree-relative path and the main checkout's absolute path are
tried, with `GAVEL_ENV_FILE` as an explicit override.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import timedelta
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            "../../.env",
            ".env",
            "/home/coder/DEV/gavel/.env",
            os.environ.get("GAVEL_ENV_FILE", ""),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
        # `.env.example` ships `KEY=` lines; blank means unset, not "".
        env_ignore_empty=True,
    )

    log_level: str = "INFO"

    # --- this service --------------------------------------------------------
    calendar_host: str = "127.0.0.1"
    calendar_port: int = 8790
    # Base URL the join page and /invite responses use to build join links.
    calendar_public_url: str = "http://localhost:8790"

    # --- ears-discord, the only session entry point we call ------------------
    # HTTP, not the `ws://` wire URL — same host/port, see packages/ears-discord's
    # POST /api/meetings + POST /api/sessions (docs/CONTRACT.md, wire.py).
    ears_api_url: str = "http://localhost:8787"

    # --- the meeting room page (room.py) ----------------------------------------
    # The brain's read-only state endpoint (`packages/brain/src/main.ts`,
    # STAGE_PORT). Fetched server-side so the browser never needs the brain's
    # address and the console's HTTP auth is left alone. Unreachable is not an
    # error: the room page then shows its banked report, or the agenda.
    brain_state_url: str = "http://localhost:8788/state"
    # The chair-video stage embedded as Karen's face. Relative by default: on
    # the deployed host Traefik routes /stage/ to chair-video, so this works
    # without knowing the domain. Point it at http://localhost:8791/stage/ to
    # run the two services side by side.
    chair_video_stage_url: str = "/stage/"

    # --- attendee identity seam ------------------------------------------------
    # A calendar invite gives name + email, never a Discord id. Until there is a
    # real directory, an operator maps known emails to snowflakes here:
    #   CALENDAR_ATTENDEE_MAP="vitaly@x.com=100000000000000001,ana@y.com=...."
    # Unmapped attendees fall back to their email as `discordId` — stable, unique,
    # but it will not match a real speaker until mapped. Documented in the README.
    calendar_attendee_map: str = ""

    # Per-session policy overrides for meetings this service creates, as a JSON
    # object of the keys in schema.EARS_DEFAULT_POLICY, e.g.
    #   CALENDAR_POLICY_OVERRIDES={"offAgendaGraceSeconds": 8, "requireStart": false}
    # Empty (the default) sends no `policy` at all, so ears uses its own table.
    # Only the keys named here change; `agenda.build_agenda` merges the rest.
    calendar_policy_overrides: str = ""

    # How often the scheduler re-checks for the next event to start, at most.
    # Also the poll interval for CALENDAR_ICS_FEEDS below.
    scheduler_poll_seconds: float = 30.0

    # --- Google Calendar secret iCal feed, read-only ------------------------
    # A calendar's "Secret address in iCal format" (Settings > Integrate
    # calendar). This is a credential — anyone holding it can read the whole
    # calendar. Never logged, never echoed in an error or /health response;
    # code that needs to name a feed uses its index, never its value.
    # Comma-separated; zero, one, or many. Empty means the manual `POST
    # /invite` path is the only way an invite arrives — unchanged behavior.
    calendar_ics_feeds: str = ""

    # How far ahead of "now" a polled feed event may start to be ingested.
    # A feed carries a year of history; without this every poll would try
    # to build a session for last March's standup.
    calendar_feed_window_hours: float = 24.0

    # --- compose: the "create a meeting" front door -------------------------
    # Nebius Token Factory, OpenAI-compatible chat/completions. Already used by
    # `packages/brain`; the model id is pinned in `llm.py` from
    # `packages/brain/config/models.yaml`'s `fast` profile, not read from here —
    # `NEBIUS_MODEL` in `.env` is a leftover, unused on purpose.
    nebius_api_key: str = ""
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1"

    # A secret; empty means the mailer runs in dry-run mode (see mailer.py).
    resend_api_key: str = ""
    # Must be on a Resend-verified sending domain. Empty fails loudly with the
    # setting's name at send time, never silently.
    compose_from_email: str = ""
    # "Name <email>, Name <email>, ..." (RFC 5322 address list) — prefills
    # GET /compose's attendees field. The three people already on this demo;
    # kept distinct even where two share a first name, since `agenda.py`
    # matches an owner/must-hear name case-insensitively and a collision would
    # silently resolve to the wrong attendee.
    compose_default_attendees: str = (
        "Vitaly <vitaly.alt@gmail.com>, Artem <a.shambalev@gmail.com>, "
        "Vitaly P <vitaly@pro7ocol.com>"
    )
    # The meeting's .ics LOCATION and the success page's Discord link.
    discord_meeting_url: str = (
        "https://discordapp.com/channels/1550819764258213909/1550820239564996608"
    )
    # IANA name. Venue is Barcelona; also what "in one hour" / "tomorrow at
    # 10" resolve against — see llm.py.
    compose_timezone: str = "Europe/Madrid"

    @property
    def ics_feed_urls(self) -> list[str]:
        return [u.strip() for u in self.calendar_ics_feeds.split(",") if u.strip()]

    @property
    def feed_window(self) -> timedelta:
        return timedelta(hours=self.calendar_feed_window_hours)

    @property
    def policy_overrides(self) -> dict[str, float | bool | str]:
        """Parsed CALENDAR_POLICY_OVERRIDES. Malformed JSON is logged and
        ignored — a typo in an override must never stop an invite going out."""
        raw = self.calendar_policy_overrides.strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except ValueError:
            logger.warning("settings.policy_overrides_unparsable")
            return {}
        if not isinstance(parsed, dict):
            logger.warning("settings.policy_overrides_not_an_object")
            return {}
        return {k: v for k, v in parsed.items() if isinstance(v, (int, float, bool, str))}

    @property
    def attendee_map(self) -> dict[str, str]:
        pairs = (p.strip() for p in self.calendar_attendee_map.split(",") if p.strip())
        out: dict[str, str] = {}
        for pair in pairs:
            email, _, discord_id = pair.partition("=")
            if email and discord_id:
                out[email.strip().lower()] = discord_id.strip()
        return out


@lru_cache
def get_settings() -> Settings:
    return Settings()
