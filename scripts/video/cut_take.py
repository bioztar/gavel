"""Cut the real take into the submission video.

Everything here comes from one recording, so picture and sound cannot drift: each piece is
re-encoded with identical parameters and the pieces are concatenated with `-c copy`.
Timings come from the SLNG transcript in scripts/video/take-cuts.json.
"""
from __future__ import annotations
import json, pathlib, subprocess

SRC = pathlib.Path("/Users/alex/DEV/gavel/The AI Chair.mp4")
ROOT = pathlib.Path("/Users/alex/DEV/_assets/gavel-video")
OUT = ROOT / "take"; OUT.mkdir(parents=True, exist_ok=True)
CUTS = json.loads(pathlib.Path(__file__).with_name("take-cuts.json").read_text())
W, H, FPS = 1920, 960, 30


def piece(i: int, c: dict) -> pathlib.Path:
    dest = OUT / f"{i:02d}-{c['id']}.mp4"
    length = c["end"] - c["start"]
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", f"{c['start']:.3f}", "-i", str(SRC),
         "-t", f"{length:.3f}",
         "-vf", f"scale={W}:{H},fps={FPS},setsar=1",
         "-af", "aresample=48000,afade=t=in:st=0:d=0.04,"
                f"afade=t=out:st={max(length - 0.18, 0.05):.3f}:d=0.18",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", str(dest)], check=True)
    return dest


def dur(p: pathlib.Path) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", str(p)], capture_output=True,
                                text=True).stdout.strip())


if __name__ == "__main__":
    parts = []
    for i, c in enumerate(CUTS):
        p = piece(i, c)
        parts.append(p)
        print(f"{i:02d} {c['id']:22s} {c['start']:7.1f}-{c['end']:7.1f}  {dur(p):5.1f}s", flush=True)

    listing = OUT / "concat.txt"
    listing.write_text("".join(f"file '{p}'\n" for p in parts))
    final = ROOT / "gavel-take.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(final)],
                   check=True)
    v = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=duration", "-of", "csv=p=0", str(final)],
                       capture_output=True, text=True).stdout.strip()
    a = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                        "stream=duration", "-of", "csv=p=0", str(final)],
                       capture_output=True, text=True).stdout.strip()
    print(f"\nFINAL {final}  {dur(final)/60:.2f} min   video {v}s  audio {a}s")
