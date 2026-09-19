"""Measures wall-clock latency of each lip-sync candidate for a 3s and 8s
utterance. Spends real fal credits — that is what they are for (see mission).

Usage: uv run python scripts/measure_latency.py
Prints a markdown table to stdout; paste it into README.md by hand so a
human reviews the numbers before they become documentation.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from chair_video.fal import FalClient, FalError  # noqa: E402
from chair_video.settings import get_settings  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
AUDIO_3S = ROOT / "scripts/fixtures/utterance-3s.wav"
AUDIO_8S = ROOT / "scripts/fixtures/utterance-8s.wav"
IDLE_VIDEO = ROOT / "avatars/idle.mp4"
AVATAR_IMAGE = ROOT / "avatars/chair-01.png"

# Models that animate an existing video (re-sync lips to new audio).
VIDEO_INPUT_MODELS = [
    "fal-ai/sync-lipsync/v2",
    "veed/lipsync/v2",
    "fal-ai/kling-video/lipsync/audio-to-video",
]
# Models that animate a still image directly.
IMAGE_INPUT_MODELS = [
    "fal-ai/longcat-single-avatar/image-audio-to-video",
]


def main() -> None:
    settings = get_settings()
    rows: list[tuple[str, str, str]] = []

    with FalClient(settings) as fal:
        print("uploading fixtures to fal CDN...", file=sys.stderr)
        audio_uris = {
            "3s": fal.upload(AUDIO_3S.read_bytes(), "audio/wav", "utterance-3s.wav"),
            "8s": fal.upload(AUDIO_8S.read_bytes(), "audio/wav", "utterance-8s.wav"),
        }
        video_uri = fal.upload(IDLE_VIDEO.read_bytes(), "video/mp4", "idle.mp4")
        image_uri = fal.upload(AVATAR_IMAGE.read_bytes(), "image/png", "chair-01.png")

        for model in VIDEO_INPUT_MODELS:
            for label, audio_uri in audio_uris.items():
                rows.append(_run(fal, model, label, {"video_url": video_uri, "audio_url": audio_uri}))
        for model in IMAGE_INPUT_MODELS:
            for label, audio_uri in audio_uris.items():
                rows.append(_run(fal, model, label, {"image_url": image_uri, "audio_url": audio_uri}))

    print("\n| model | utterance | latency |")
    print("|---|---|---|")
    for model, label, latency in rows:
        print(f"| `{model}` | {label} | {latency} |")


def _run(fal: FalClient, model: str, label: str, arguments: dict) -> tuple[str, str, str]:
    print(f"-> {model} ({label})", file=sys.stderr)
    try:
        result = fal.run(model, arguments)
    except FalError as exc:
        print(f"   FAILED: {exc}", file=sys.stderr)
        return (model, label, f"FAILED — {exc}")
    except Exception:  # the point of this script is a complete table, not a crash
        print("   FAILED (unexpected):", file=sys.stderr)
        traceback.print_exc()
        return (model, label, "FAILED — unexpected error, see stderr")
    seconds = result.latency_ms / 1000
    print(f"   {seconds:.1f}s", file=sys.stderr)
    return (model, label, f"{seconds:.1f}s")


if __name__ == "__main__":
    main()
