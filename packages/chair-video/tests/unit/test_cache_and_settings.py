"""Cache keying and persona-normalization logic. No network."""

from __future__ import annotations

from chair_video.cache import SpeakVideoCache, audio_key
from chair_video.settings import Settings


def test_audio_key_differs_by_persona() -> None:
    audio = b"same-audio-bytes"
    assert audio_key(audio, "formal") != audio_key(audio, "funky")


def test_audio_key_stable_for_same_input() -> None:
    audio = b"same-audio-bytes"
    assert audio_key(audio, "formal") == audio_key(audio, "formal")


def test_cache_roundtrip() -> None:
    cache = SpeakVideoCache()
    key = audio_key(b"abc", "formal")
    assert cache.get(key) is None
    cache.set(key, {"videoUrl": "https://cdn/x.mp4", "durationMs": 3000})
    assert cache.get(key) == {"videoUrl": "https://cdn/x.mp4", "durationMs": 3000}
    assert len(cache) == 1


def test_normalize_persona_known_values_pass_through() -> None:
    settings = Settings(fal_key="x")
    assert settings.normalize_persona("formal") == "formal"
    assert settings.normalize_persona("funky") == "funky"


def test_normalize_persona_unknown_falls_back_to_default() -> None:
    # Settings.default_persona is "funky" (see settings.py) — this used to
    # assert "formal", which was wrong for the same reason test_app.py's
    # idle-persona test was wrong.
    settings = Settings(fal_key="x")
    assert settings.normalize_persona("typo") == "funky"
    assert settings.normalize_persona(None) == "funky"


def test_idle_video_path_and_avatar_image_path_per_persona() -> None:
    settings = Settings(fal_key="x")
    assert settings.idle_video_path("funky") == "avatars/idle-funky.mp4"
    assert settings.avatar_image_path("formal") == "avatars/karen-formal.png"
    # Unknown persona resolves via the default ("funky"), never a KeyError.
    assert settings.idle_video_path("typo") == settings.idle_video_path("funky")
