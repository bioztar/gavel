"""Typed settings from the environment, then the repo-root `.env`.

stream-vonage is a git worktree of `gavel`, so the repo-root `.env` may live in a
sibling checkout rather than two directories up. `GAVEL_ENV_FILE` overrides the
search when that's the case; otherwise both the worktree-relative path and the
main checkout's absolute path are tried. Copied verbatim from
`packages/chair-video/src/chair_video/settings.py` per the mission brief.

Never log a setting's value — on a missing/invalid one, raise with its *name* only.
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            "../../.env",
            "/home/coder/DEV/gavel/.env",
            os.environ.get("GAVEL_ENV_FILE", ""),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
        # `.env.example` ships `KEY=` lines; blank means unset, not "".
        env_ignore_empty=True,
    )

    log_level: str = "INFO"

    # --- service ---------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8792

    # --- Vonage Video API credentials -------------------------------------
    # Current style: a Vonage Application, JWTs signed RS256 with the private key.
    vonage_application_id: str = ""
    # PEM contents. Env vars can't hold real newlines cleanly, so a literal
    # "\n" is accepted and normalized to a real newline — see `private_key_pem`.
    vonage_private_key: str = ""
    # Legacy TokBox/OpenTok project style: HS256 JWTs (X-OPENTOK-AUTH header)
    # and the classic "T1==" client token format, both signed with the secret.
    vonage_api_key: str = ""
    vonage_api_secret: str = ""

    # --- brain's live state (depth addition 1: session.signal relay) ------
    # Same-origin proxy target for GET /brain-state — see app.py. Inside
    # compose this is http://brain:8788/state; locally, brain's published
    # loopback port.
    brain_state_url: str = "http://127.0.0.1:8788/state"
    brain_state_poll_seconds: float = 2.0

    @property
    def vonage_private_key_pem(self) -> str:
        return self.vonage_private_key.replace("\\n", "\n")

    @property
    def has_jwt_credentials(self) -> bool:
        return bool(self.vonage_application_id and self.vonage_private_key)

    @property
    def has_api_key_credentials(self) -> bool:
        return bool(self.vonage_api_key and self.vonage_api_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
