"""Lip-sync Karen's idle loop to each of her lines via fal (veed/lipsync/v2)."""
from __future__ import annotations
import json, os, pathlib, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, "/Users/alex/DEV/gavel/packages/chair-video/src")
os.environ.setdefault("GAVEL_ENV_FILE", "/Users/alex/DEV/gavel/.env")
from chair_video.settings import get_settings  # noqa: E402
from chair_video.fal import FalClient  # noqa: E402
import httpx  # noqa: E402

ROOT = pathlib.Path("/Users/alex/DEV/_assets/gavel-video")
OUT = ROOT / "karen"; OUT.mkdir(parents=True, exist_ok=True)
# kling image-to-video gives her head and shoulder movement; the old idle loop was
# nearly a still, which read as a photo with a moving mouth.
IDLE = pathlib.Path("/Users/alex/DEV/_assets/gavel-video/karen/_live-kling-video.mp4")
SCRIPT = json.loads(pathlib.Path(__file__).with_name("script.json").read_text())
S = get_settings()


def looped_idle(seconds: float) -> bytes:
    """veed re-syncs an existing clip; give it one at least as long as the audio."""
    tmp = OUT / f"_idle-{int(seconds)+1}.mp4"
    if not tmp.exists():
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", str(IDLE),
                        "-t", str(seconds + 1.0), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-an", str(tmp)], check=True)
    return tmp.read_bytes()


def one(seg: dict) -> str:
    dest = OUT / f"{seg['id']}.mp4"
    if dest.exists() and dest.stat().st_size > 10000:
        return f"cached {seg['id']}"
    audio = ROOT / "audio" / f"{seg['id']}.mp3"
    secs = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", str(audio)], capture_output=True, text=True,
                                check=True).stdout.strip())
    with FalClient(S) as fal:
        video_url = fal.upload(looped_idle(secs), "video/mp4", f"idle-{seg['id']}.mp4")
        audio_url = fal.upload(audio.read_bytes(), "audio/mpeg", f"{seg['id']}.mp3")
        res = fal.run("veed/lipsync/v2", {"video_url": video_url, "audio_url": audio_url})
        url = res.data.get("video", {}).get("url") or res.data.get("url")
        dest.write_bytes(httpx.get(url, timeout=300).content)
    return f"ok {seg['id']} {res.latency_ms/1000:.0f}s"


if __name__ == "__main__":
    faces = [s for s in SCRIPT["segments"] if s.get("face")]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for line in pool.map(one, faces):
            print(line, flush=True)
