"""Proof of end-to-end: a wav file in, a lip-synced video URL out.

Talks directly to fal (no running server needed) using the exact same pipeline
`POST /speak-video` uses — upload audio, upload/reuse the persona's idle loop,
run the configured lipsync_model, print the result.

Usage: uv run python scripts/demo.py path/to/audio.wav [--persona formal|funky]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from chair_video.fal import FalClient, FalError
from chair_video.settings import get_settings

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav_path", type=Path, help="wav file to speak")
    parser.add_argument("--persona", default="formal", choices=["formal", "funky"])
    args = parser.parse_args()

    if not args.wav_path.exists():
        print(f"no such file: {args.wav_path}", file=sys.stderr)
        raise SystemExit(1)

    settings = get_settings()
    persona = settings.normalize_persona(args.persona)
    idle_path = ROOT / settings.idle_video_path(persona)

    with FalClient(settings) as fal:
        print(f"uploading {args.wav_path.name}...", file=sys.stderr)
        audio_url = fal.upload(args.wav_path.read_bytes(), "audio/wav", args.wav_path.name)
        print(f"uploading {idle_path.name} (persona={persona})...", file=sys.stderr)
        video_url = fal.upload(idle_path.read_bytes(), "video/mp4", idle_path.name)

        print(f"running {settings.lipsync_model}...", file=sys.stderr)
        try:
            result = fal.run(
                settings.lipsync_model, {"video_url": video_url, "audio_url": audio_url}
            )
        except FalError as exc:
            print(f"FAILED: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

    video = result.data.get("video")
    out_url = video.get("url") if isinstance(video, dict) else video
    if not out_url:
        print(f"fal result had no video url: {result.data}", file=sys.stderr)
        raise SystemExit(1)

    print(f"latency: {result.latency_ms}ms")
    print(out_url)


if __name__ == "__main__":
    main()
