"""Typed settings from the environment, the repo-root `.env`, then a local `.env`.

Postgres and Redis are optional: when unreachable, ears keeps running and the
brain still gets every frame over the wire. Only the Discord token is required
to join a call.
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
    log_json: bool = False

    # --- discord -----------------------------------------------------------
    discord_ears_token: str = ""
    discord_guild_id: int | None = None
    # Unset: join whichever voice channel has humans in it.
    discord_voice_channel_id: int | None = None
    # Stay briefly after the last person leaves, in case they reconnect or switch device.
    discord_leave_grace_seconds: float = 10.0
    # py-cord does not find Homebrew's libopus on its own.
    opus_lib: str = "/opt/homebrew/lib/libopus.dylib"

    # --- wire to the brain -------------------------------------------------
    wire_host: str = "127.0.0.1"
    wire_port: int = 8787
    # Read-only live state exposed by brain; proxied to the operator console.
    brain_state_url: str = "http://127.0.0.1:8788/state"

    # --- data --------------------------------------------------------------
    postgres_dsn: str = "postgresql+asyncpg://gavel:gavel@localhost:5432/gavel"
    redis_dsn: str = "redis://localhost:6379/0"
    redis_prefix: str = "gavel:ears"
    # Redis stream length cap (approximate, XADD MAXLEN ~).
    redis_stream_maxlen: int = 50_000

    # --- SLNG speech-to-text -----------------------------------------------
    slng_api_key: str = ""
    slng_base_url: str = "https://eu-west.api.slng.ai"
    # `stream` (default): one WebSocket per speaker, diarization on — models:
    # `deepgram/nova:3` or `soniox/speech-ai:rt-v5`. `http`: per-utterance chunks, Nova 3 only.
    stt_mode: str = "stream"
    slng_stt_model: str = "deepgram/nova:3"
    slng_stt_language: str = "en"
    slng_timeout_seconds: float = 10.0
    # TTS for the console's say-box. Fish on eu-west was the fastest route measured
    # from Barcelona (~1.2s to first byte). Aura: model `deepgram/aura:2`, voice
    # `aura-2-thalia-en`.
    slng_tts_model: str = "slng/fish/tts:s2.1-pro"
    slng_tts_voice: str = "16cabdb7f8d240569aff36c9e480d783"

    # --- signal shaping ----------------------------------------------------
    # Silence that closes a turn — one person holding the floor.
    turn_gap_ms: int = 1500
    # A `turn.tick` fires this often while someone keeps talking.
    turn_tick_ms: int = 10_000
    # Silence that closes an utterance and sends it to STT.
    utterance_gap_ms: int = 800
    # A monologue is cut into chunks of at most this, so transcripts keep flowing.
    chunk_max_ms: int = 15_000
    # Shorter chunks are coughs and clicks, not worth an STT call.
    chunk_min_ms: int = 400
    # Streaming: silence that counts as a pause, how much silence to send so the model
    # finalizes (Discord sends none), and when an idle socket is closed.
    stt_flush_ms: int = 400
    stt_flush_silence_ms: int = 1200
    stt_idle_close_s: float = 45.0
    # Chunks quieter than this (16-bit RMS) are silence frames, not speech. Speech sits
    # in the hundreds to thousands.
    silence_rms: float = 60.0

    @property
    def stt_enabled(self) -> bool:
        return bool(self.slng_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
