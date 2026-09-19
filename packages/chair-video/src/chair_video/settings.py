"""Typed settings from the environment, then the repo-root `.env`.

chair-video is a git worktree of `gavel`, so the repo-root `.env` may live in a
sibling checkout rather than two directories up. `GAVEL_ENV_FILE` overrides the
search when that's the case; otherwise both the worktree-relative path and the
main checkout's absolute path are tried.
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

    # --- fal -----------------------------------------------------------
    fal_key: str = ""
    fal_base_url: str = "https://queue.fal.run"
    # Winner of the measured latency table (see README). Kept overridable so a
    # faster model found later is a config change, not a redeploy.
    lipsync_model: str = "fal-ai/longcat-single-avatar/image-audio-to-video"
    avatar_model: str = "fal-ai/flux/schnell"

    # --- service ---------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8790
    # Wall-clock budget for a queue job (submit -> COMPLETED) before we give up.
    fal_poll_timeout_s: float = 120.0
    fal_poll_interval_s: float = 1.0

    # The chair's committed portrait and idle loop, served by GET /idle.
    avatar_image_path: str = "avatars/chair-01.png"
    idle_video_path: str = ""

    @property
    def fal_configured(self) -> bool:
        return bool(self.fal_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
