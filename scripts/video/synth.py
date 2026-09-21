"""Synthesize Karen's lines in script.json with SLNG; narrator mp3s are supplied in audio/."""
from __future__ import annotations
import json, pathlib, subprocess
from concurrent.futures import ThreadPoolExecutor

import httpx

ROOT = pathlib.Path("/Users/alex/DEV/_assets/gavel-video")
AUDIO = ROOT / "audio"
AUDIO.mkdir(parents=True, exist_ok=True)
SCRIPT = json.loads(pathlib.Path(__file__).with_name("script.json").read_text())


def _slng_key() -> str:
    for line in pathlib.Path("/Users/alex/DEV/gavel/.env").read_text().splitlines():
        if line.startswith("SLNG_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("SLNG_API_KEY missing")


def duration(path: pathlib.Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def synth(seg: dict) -> tuple[str, float]:
    dest = AUDIO / f"{seg['id']}.mp3"
    if dest.exists() and dest.stat().st_size > 2000:
        return seg["id"], duration(dest)
    voice = SCRIPT["voices"][seg["speaker"]]
    if voice["engine"] == "slng":
        r = httpx.post(
            "https://eu-west.api.slng.ai/v1/tts/slng/fish/tts:s2.1-pro",
            headers={"Authorization": f"Bearer {_slng_key()}"},
            json={"text": seg["text"], "reference_id": voice["voice"]}, timeout=120)
        r.raise_for_status()
        dest.write_bytes(r.content)
    else:
        raise SystemExit(
            f"{seg['id']}: no synth for engine {voice['engine']!r} — narrator lines are "
            f"produced outside the repo; drop the mp3 into {AUDIO}")
    return seg["id"], duration(dest)


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(synth, SCRIPT["segments"]))
    total = 0.0
    for sid, secs in results:
        total += secs
        print(f"{sid:22s} {secs:6.1f}s")
    print(f"{'TOTAL':22s} {total:6.1f}s  ({total/60:.2f} min)")
    (ROOT / "durations.json").write_text(json.dumps(dict(results), indent=2))
