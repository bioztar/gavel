"""One-off: generate 3 'Funky Karen' variants from the formal portrait via fal
image-to-image, keeping identity (face/hair) while changing wardrobe/background.

Usage: uv run python scripts/gen_funky_karen.py
Writes avatars/karen-funky-0{1..3}.png and appends prompts to avatars/PROMPTS.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from chair_video.fal import FalClient
from chair_video.settings import get_settings

AVATARS_DIR = Path(__file__).resolve().parents[1] / "avatars"
SOURCE_IMAGE = AVATARS_DIR / "karen-formal.png"
MODEL = "fal-ai/flux/dev/image-to-image"
# v1 (strength=0.6) and v2 (strength=0.8, funky-first prompt) both still read as
# formal Karen from a few meters away — black blazer, gray background survived
# both. v3 (below) is what actually worked: strength 0.9, specific colours and
# materials instead of vague words ("loud pattern" -> "red-and-orange
# floral-print"), and a short identity clause instead of a long one. Variant 2
# alone needed a step down to strength=0.82 because 0.9 turned her head away
# from the camera, breaking the front-facing/direct-eye-contact requirement
# the lip-sync model needs.
IDENTITY_SUFFIX = (
    "same identifiable woman's face, direct eye contact with camera, head and shoulders, "
    "mouth fully visible and unobstructed, photorealistic, no text, no watermark, no logo"
)

VARIANTS = [
    (
        "wearing a bright red-and-orange floral-print blazer over a bold striped top, "
        "big round tortoiseshell glasses with amber-tinted lenses, standing against a "
        "solid bright coral-orange wall",
        IDENTITY_SUFFIX,
        0.9,
    ),
    (
        "front-facing portrait, looking directly into the camera, head and shoulders, "
        "under dramatic nightclub lighting: intense hot-magenta light glowing across the "
        "left side of her face and hair, bright cyan light glowing across the right side, "
        "wearing a sparkling silver sequin jacket, dark navy background with soft neon glow",
        "same identifiable woman's face, mouth fully visible and unobstructed, "
        "photorealistic, no text, no watermark, no logo",
        0.82,
    ),
    (
        "wearing a bright mustard-yellow cardigan, hair pulled up in a messy bun with a "
        "yellow pencil stuck through it, large colourful geometric earrings, standing in "
        "front of a cork bulletin board covered edge to edge with colourful sticky notes",
        IDENTITY_SUFFIX,
        0.9,
    ),
]


def main() -> None:
    settings = get_settings()
    prompts_md = [
        "\n## Funky Karen\n",
        "chair-03 is now `karen-formal.png` (identical pixels, just renamed/copied so nothing\n"
        "that already points at `chair-03.png` breaks). The three funky candidates are\n"
        f"`{MODEL}` off `karen-formal.png` — same woman, same face,\n"
        "different wardrobe/lighting/background so a judge can tell the two personas apart\n"
        "from a few meters away.\n",
    ]

    with FalClient(settings) as fal, httpx.Client(timeout=60.0) as downloader:
        print("uploading source image...")
        image_url = fal.upload(SOURCE_IMAGE.read_bytes(), "image/png", "karen-formal.png")

        for i, (variant, suffix, strength) in enumerate(VARIANTS, start=1):
            prompt = f"{variant}, {suffix}"
            print(f"[{i}/3] generating: {variant}")
            result = fal.run(
                MODEL,
                {
                    "image_url": image_url,
                    "prompt": prompt,
                    "strength": strength,
                    "output_format": "png",
                },
            )
            images = result.data.get("images") or []
            if not images:
                raise RuntimeError(f"no images returned: {result.data}")
            out_url = images[0]["url"]
            image_bytes = downloader.get(out_url).content
            out_path = AVATARS_DIR / f"karen-funky-{i:02d}.png"
            out_path.write_bytes(image_bytes)
            print(f"  -> {out_path} ({len(image_bytes)} bytes, {result.latency_ms}ms)")
            prompts_md.append(
                f"### karen-funky-{i:02d}.png\n\n```\n{prompt}\n```\nstrength={strength}\n"
            )

    prompts_path = AVATARS_DIR / "PROMPTS.md"
    existing = prompts_path.read_text()
    head = existing.split("\n## Funky Karen\n", 1)[0].rstrip("\n")
    prompts_path.write_text(head + "\n" + "\n".join(prompts_md))
    print("done. Vitaly picks one of avatars/karen-funky-0{1..3}.png.")


if __name__ == "__main__":
    main()
