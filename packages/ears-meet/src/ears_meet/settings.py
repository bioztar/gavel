"""Typed settings from the environment, the repo-root `.env`, then a local `.env`.

Same style as ears-discord/src/ears/settings.py. Nothing here is ever logged: the
credential settings are only ever referred to by NAME (see `require_auth`).

Two things are required to join a call: `MEET_URL` and a way to be signed in —
`MEET_PROFILE_DIR` holding a pre-authenticated Chromium profile (preferred), or
`MEET_BOT_EMAIL` + `MEET_BOT_PASSWORD` for the scripted sign-in fallback.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class MissingSetting(RuntimeError):
    """Raised at startup with the NAME of what is missing — never a value."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        # `.env.example` ships `KEY=` lines; blank means unset, not "".
        env_ignore_empty=True,
    )

    log_level: str = "INFO"
    log_json: bool = False

    # --- google meet -------------------------------------------------------
    # The call to join: https://meet.google.com/xxx-yyyy-zzz
    meet_url: str = ""
    # The name shown on the bot's tile. Also what Meet's own captions call the chair, so
    # the captions miner can tell the chair's lines from the room's.
    meet_bot_name: str = "Karen (gavel)"
    # A Chromium user-data directory that is already signed in to the bot's Google account
    # (see docs/EARS-MEET.md: sign in once by hand on a desktop, copy the directory in).
    # This is the implemented, preferred way in: no login form is scripted against.
    meet_profile_dir: str = ""
    # Scripted sign-in, used only when the profile above is not signed in. Google's
    # login form fights automation (captcha, "verify it's you"), so this is best effort;
    # the setting NAMES appear in errors, the values never do.
    # SecretStr: repr/str/log output shows '**********', never the value.
    meet_bot_email: SecretStr = SecretStr("")
    meet_bot_password: SecretStr = SecretStr("")
    # How long to wait in the lobby for a host to admit the bot before giving up.
    meet_admit_timeout_s: float = 180.0
    # Ask Meet for its own live captions and mine them for attributed text.
    meet_captions: bool = True
    # Where `transcript` frames come from: `auto` mines Meet captions when they are showing
    # and falls back to SLNG STT on the mixed audio otherwise; `captions` / `stt` force one;
    # `none` emits no transcripts (speaking events and turns still flow).
    transcript_source: Literal["auto", "captions", "stt", "none"] = "auto"
    # Leave once the bot has been alone in the call this long (0 = stay until stopped).
    meet_leave_when_alone_s: float = 120.0

    # --- browser -----------------------------------------------------------
    # An explicit Chromium/Chrome binary; empty uses Playwright's bundled Chromium.
    meet_chromium_path: str = ""
    # Xvfb: start one on this display, or attach to an existing one (`xvfb_manage=false`).
    display: str = ":99"
    xvfb_manage: bool = True
    xvfb_size: str = "1280x720x24"
    # Say "yes" to Playwright's page.on('dialog') prompts, keep the window big enough that
    # Meet lays participant tiles out (it collapses to a phone layout below ~700 px wide).
    window_width: int = 1280
    window_height: int = 720

    # --- stage (screen share) ----------------------------------------------
    # packages/stage's live status page; presented into the call from a second tab when
    # reachable. Empty or unreachable: join anyway, present nothing.
    stage_url: str = ""
    stage_tab_title: str = "gavel-stage"
    stage_timeout_s: float = 10.0

    # --- pulseaudio --------------------------------------------------------
    # Two null sinks: Chromium plays the room into `pulse_sink_out`, we record its monitor
    # (ingress); we play the chair into `pulse_sink_in` and Chromium's mic is its monitor
    # (egress). Names only — created at startup unless `pulse_manage=false`.
    pulse_manage: bool = True
    pulse_sink_out: str = "gavel_out"
    pulse_sink_in: str = "gavel_in"
    # Ingress capture: 20 ms frames, matching what Discord's decoder produced.
    pulse_frame_ms: int = 20

    # --- wire to the brain -------------------------------------------------
    wire_host: str = "127.0.0.1"
    wire_port: int = 8787
    brain_state_url: str = "http://127.0.0.1:8788/state"
    # Append every emitted frame as JSONL here (empty: off). This is how the conformance
    # fixtures were recorded, and what `just record` sets.
    frames_file: str = ""

    # --- session -----------------------------------------------------------
    # A contract agenda (docs/CONTRACT.md §1) as JSON, sent in `session.started` on join.
    # Empty: a session starts with no agenda; POST /api/sessions can start one later.
    agenda_file: str = ""
    meeting_title: str = ""
    meeting_context: str = ""

    # --- SLNG speech-to-text -----------------------------------------------
    slng_api_key: str = ""
    slng_base_url: str = "https://eu-west.api.slng.ai"
    stt_mode: str = "stream"
    slng_stt_model: str = "deepgram/nova:3"
    slng_stt_language: str = "en"
    slng_timeout_seconds: float = 10.0
    slng_tts_model: str = "deepgram/aura:2"
    slng_tts_voice: str = "aura-2-thalia-en"

    # --- signal shaping ----------------------------------------------------
    # Meet's speaking indicator flickers on every syllable. A start is announced once the
    # indicator has been on for `speaking_on_ms`; an end once it has been off for
    # `speaking_off_ms`. Both are in DOM time, so a flicker never reaches the wire.
    speaking_on_ms: int = 150
    speaking_off_ms: int = 400
    # Silence that closes a turn — one person holding the floor.
    turn_gap_ms: int = 1500
    # A `turn.tick` fires this often while someone keeps talking.
    turn_tick_ms: int = 10_000
    # A monologue is cut into chunks of at most this, so transcripts keep flowing.
    chunk_max_ms: int = 15_000
    # Streaming STT pause/flush/idle, as in ears-discord.
    stt_flush_ms: int = 400
    stt_flush_silence_ms: int = 1200
    stt_idle_close_s: float = 45.0
    # Mixed-audio frames quieter than this (16-bit RMS) are silence: not sent to STT, and
    # they mark the room as quiet for `speak`'s pause gate.
    silence_rms: float = 60.0
    # A caption line is final once Meet has not edited it for this long.
    caption_settle_ms: int = 1500

    @property
    def stt_enabled(self) -> bool:
        return bool(self.slng_api_key)

    @property
    def has_profile(self) -> bool:
        return bool(self.meet_profile_dir)

    @property
    def has_password_login(self) -> bool:
        return bool(self.meet_bot_email.get_secret_value()) and bool(
            self.meet_bot_password.get_secret_value()
        )

    def require_auth(self) -> None:
        """Fail before opening a browser, naming the missing setting(s) — never a value."""
        if not self.meet_url:
            raise MissingSetting("MEET_URL is not set")
        if self.has_profile or self.has_password_login:
            return
        missing = [
            name
            for name, value in (
                ("MEET_BOT_EMAIL", self.meet_bot_email),
                ("MEET_BOT_PASSWORD", self.meet_bot_password),
            )
            if not value.get_secret_value()
        ]
        raise MissingSetting(
            "no Google sign-in: set MEET_PROFILE_DIR to a signed-in Chromium profile, "
            f"or set {' and '.join(missing)}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
