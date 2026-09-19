"""One-off: generate the 4 candidate portraits for the chair via fal text-to-image.

Usage: uv run python scripts/gen_avatars.py
Writes avatars/chair-0{1..4}.png and avatars/PROMPTS.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from chair_video.fal import FalClient
from chair_video.settings import get_settings

AVATARS_DIR = Path(__file__).resolve().parents[1] / "avatars"

BASE_PROMPT = (
    "Studio portrait photo of a calm, professional meeting chairperson, {variant}, "
    "front-facing, direct eye contact with camera, head and shoulders, "
    "neutral plain gray background, even soft studio lighting, sharp focus, "
    "photorealistic, high detail, 85mm lens, no text, no watermark, no logo"
)

VARIANTS = [
    "a woman in her 40s with short dark hair, wearing a simple navy blazer",
    "a man in his 50s with gray hair and glasses, wearing a light gray sweater",
    "a woman in her 30s with shoulder-length black hair, wearing a charcoal blazer",
    "a man in his 40s with short black hair and a beard, wearing a dark blue shirt",
]


def main() -> None:
    settings = get_settings()
    AVATARS_DIR.mkdir(exist_ok=True)
    prompts_md = ["# Avatar prompts\n", "Generated with `fal-ai/flux/schnell`, 1024x1024.\n"]

    with FalClient(settings) as fal, httpx.Client(timeout=60.0) as downloader:
        for i, variant in enumerate(VARIANTS, start=1):
            prompt = BASE_PROMPT.format(variant=variant)
            print(f"[{i}/4] generating: {variant}")
            result = fal.run(
                settings.avatar_model,
                {
                    "prompt": prompt,
                    "image_size": {"width": 1024, "height": 1024},
                    "num_images": 1,
                    "output_format": "png",
                },
            )
            images = result.data.get("images") or []
            if not images:
                raise RuntimeError(f"no images returned: {result.data}")
            image_url = images[0]["url"]
            image_bytes = downloader.get(image_url).content
            out_path = AVATARS_DIR / f"chair-{i:02d}.png"
            out_path.write_bytes(image_bytes)
            print(f"  -> {out_path} ({len(image_bytes)} bytes, {result.latency_ms}ms)")
            prompts_md.append(f"## chair-{i:02d}.png\n\n```\n{prompt}\n```\n")

    (AVATARS_DIR / "PROMPTS.md").write_text("\n".join(prompts_md))
    print("done. Vitaly picks one of avatars/chair-0{1..4}.png.")


if __name__ == "__main__":
    main()
