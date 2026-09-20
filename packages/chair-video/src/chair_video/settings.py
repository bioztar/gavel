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
    # Winner of the measured latency table (see README): the only two models
    # that completed reliably both take video_url (re-sync an existing clip),
    # not image_url. veed/lipsync/v2 was fastest of the two that worked, so
    # /speak-video re-syncs the persona's idle loop rather than animating a
    # still. Kept overridable so a faster model found later is a config
    # change, not a redeploy.
    lipsync_model: str = "veed/lipsync/v2"
    avatar_model: str = "fal-ai/flux/schnell"

    # --- service ---------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8790
    # Wall-clock budget for a queue job (submit -> COMPLETED) before we give up.
    fal_poll_timeout_s: float = 120.0
    fal_poll_interval_s: float = 1.0

    # Persona -> asset mapping. `packages/brain/config/personas.yaml` (owned by
    # a different crewmate) is the source of truth for a persona's tone and
    # template lines; this is the source of truth for which *file* a persona
    # renders with, since that's this service's own concern. karen-funky-01
    # is a placeholder pending Vitaly's pick among the three funky candidates
    # in avatars/ — swap it here, nothing else needs to change.
    avatar_image_by_persona: dict[str, str] = {
        "formal": "avatars/karen-formal.png",
        "funky": "avatars/karen-funky-01.png",
    }
    idle_video_by_persona: dict[str, str] = {
        "formal": "avatars/idle-formal.mp4",
        "funky": "avatars/idle-funky.mp4",
    }
    default_persona: str = "funky"

    # --- director (live WebRTC stream) ------------------------------------
    # Confirmed against real fal in the Phase 0 spike (see README's Director
    # section): transport is one-shot-SDP WebRTC to wma.fal.run, no LiveKit
    # SDK required. This is the only host the browser proxy is allowed to
    # forward to — narrower than "*.fal.run" on purpose, since the browser
    # never needs anything else (audio upload happens server-side).
    director_endpoint_id: str = "fal-ai/minimax-h3-max-director"
    director_proxy_host: str = "wma.fal.run"
    director_resolution: str = "480p"
    director_aspect_ratio: str = "16:9"
    # A short prompt per persona, sent once as the session's `configure`
    # message. Not the chair's script — just what the model should look like.
    director_prompt_by_persona: dict[str, str] = {
        "formal": (
            "Photorealistic medium close-up of one composed professional woman in her forties "
            "seated at a desk, chairing a meeting on camera. Locked-off static camera, fixed "
            "framing, head and shoulders centred, eyes level with the lens. Plain softly lit "
            "office wall behind her. She looks straight into the lens, blinks and breathes "
            "naturally, and moves only her head and face. No zoom, no pan, no dolly, no cuts, "
            "no camera shake, no scene changes. Her face, hair, clothing and background stay "
            "identical the whole time. Consistent identity, natural skin texture, realistic "
            "lighting. Not a cartoon, not stylised, no morphing, no warping, no dissolving or "
            "blending between shots."
        ),
        "funky": (
            "Photorealistic medium close-up of one warm, playful woman in her forties seated at "
            "a desk, chairing a meeting on camera with a bright smile. Locked-off static camera, "
            "fixed framing, head and shoulders centred, eyes level with the lens. Colourful but "
            "plain wall behind her. She looks straight into the lens, blinks and breathes "
            "naturally, and moves only her head and face. No zoom, no pan, no dolly, no cuts, no "
            "camera shake, no scene changes. Her face, hair, clothing and background stay "
            "identical the whole time. Consistent identity, natural skin texture, realistic "
            "lighting. Not a cartoon, not stylised, no morphing, no warping, no dissolving or "
            "blending between shots."
        ),
    }
    # Three missed heartbeats (stage page pings every 5s) and /healthz stops
    # claiming the chair is visible — Python cannot close the browser's own
    # peer connection, so this only affects reporting, not billing.
    director_heartbeat_timeout_s: float = 15.0
    # A fresh generative session periodically replaces the current one before
    # temporal drift can "cook" the image. The browser uses make-before-break,
    # keeping the previous scene visible until the new one has media. Five
    # minutes is also safely below fal's own ~15-minute session cap.
    director_scene_duration_s: float = 5 * 60.0
    # How often the background sweeper checks whether a scene needs rotating.
    director_sweep_interval_s: float = 5.0

    def avatar_image_path(self, persona: str) -> str:
        return self.avatar_image_by_persona.get(
            persona, self.avatar_image_by_persona[self.default_persona]
        )

    def idle_video_path(self, persona: str) -> str:
        return self.idle_video_by_persona.get(
            persona, self.idle_video_by_persona[self.default_persona]
        )

    def normalize_persona(self, persona: str | None) -> str:
        """Unknown/missing persona falls back to the configured default rather than erroring —
        on stage a typo must not silence the chair."""
        if persona in self.avatar_image_by_persona:
            return persona
        return self.default_persona

    @property
    def fal_configured(self) -> bool:
        return bool(self.fal_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
