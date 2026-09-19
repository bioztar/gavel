"""Typed settings from the environment, the repo-root `.env`, then a local `.env`.

Same pattern as `packages/ears-discord/src/ears/settings.py`. Never log a
setting's value — on a missing/invalid one, raise with its *name* only.
"""

from __future__ import annotations

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
    scheduler_poll_seconds: float = 30.0

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
