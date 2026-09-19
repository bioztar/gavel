"""Typed settings from the environment, the repo-root `.env`, then a local `.env`.

Same pattern as `packages/ears-discord/src/ears/settings.py`. Never log a
setting's value — on a missing/invalid one, raise with its *name* only.
"""

from __future__ import annotations

from datetime import timedelta
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
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

    # --- attendee identity seam ------------------------------------------------
    # A calendar invite gives name + email, never a Discord id. Until there is a
    # real directory, an operator maps known emails to snowflakes here:
    #   CALENDAR_ATTENDEE_MAP="vitaly@x.com=100000000000000001,ana@y.com=...."
    # Unmapped attendees fall back to their email as `discordId` — stable, unique,
    # but it will not match a real speaker until mapped. Documented in the README.
    calendar_attendee_map: str = ""

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

    @property
    def ics_feed_urls(self) -> list[str]:
        return [u.strip() for u in self.calendar_ics_feeds.split(",") if u.strip()]

    @property
    def feed_window(self) -> timedelta:
        return timedelta(hours=self.calendar_feed_window_hours)

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
