"""Build the submission video from synthesized audio, live screenshots and Karen clips.

Each segment becomes its own 1920x1080 clip and they are concatenated. Three things here
were learned the hard way and should not be undone:

* Every clip is **stereo**. Mixing mono segments with a stereo card makes `concat -c copy`
  pin the whole track to the first stream's layout, and players go silent.
* Speed comes from the TTS, never from `atempo`. Time-stretching the cloned voice by 1.5
  made it break up.
* Levels are a fixed per-file gain, not `loudnorm`. Single-pass loudnorm pumped.
"""
from __future__ import annotations
import json, pathlib, subprocess

ROOT = pathlib.Path("/Users/alex/DEV/_assets/gavel-video")
SHOTS, AUDIO, KAREN, OUT = ROOT / "shots", ROOT / "audio", ROOT / "karen", ROOT / "out"
OUT.mkdir(parents=True, exist_ok=True)
SCRIPT = json.loads(pathlib.Path(__file__).with_name("script.json").read_text())
LABEL = {"vitaly": "VITALY", "artem": "ARTEM", "karen": "KAREN  ·  the chair"}
TARGET_MEAN_DB, PEAK_CEILING_DB = -20.0, -1.5
PAGE_CROP = "crop=1290:726:315:40"

# logical shot -> (file, full-bleed?, what it stands in for)
SHOTS_BY_NAME = {
    "card": ("card-title", True, None),
    "arch1": ("arch1", True, None),
    "arch3": ("arch3", True, None),
    "compose": ("compose", False, None),
    "gate": ("focus-gate", False, None),
    "confirm": ("focus-agenda", False, None),
    "gauge": ("focus-gauge", False, None),
    "invite": ("invite-agenda", False, None),
    "invite-top": ("invite", False, "calendar accept"),
    "room": ("room-live", True, None),
}


def probe(path: pathlib.Path, entries: str) -> str:
    return subprocess.run(["ffprobe", "-v", "error", "-show_entries", entries,
                           "-of", "csv=p=0", str(path)],
                          capture_output=True, text=True, check=True).stdout.strip()


def dur(path: pathlib.Path) -> float:
    return float(probe(path, "format=duration"))


def gain_db(audio: pathlib.Path) -> float:
    """Fixed gain to a common speaking level, clamped so nothing clips.

    The cloned voice comes back ~20 dB under the other two engines, because it
    inherited the level of the quiet sample it was cloned from.
    """
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(audio),
                          "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    mean = peak = None
    for line in out.splitlines():
        if "mean_volume:" in line:
            mean = float(line.split("mean_volume:")[1].split("dB")[0])
        elif "max_volume:" in line:
            peak = float(line.split("max_volume:")[1].split("dB")[0])
    if mean is None or peak is None:
        return 0.0
    return round(min(TARGET_MEAN_DB - mean, PEAK_CEILING_DB - peak), 2)


def build(seg: dict) -> pathlib.Path:
    sid = seg["id"]
    shot, full, placeholder = SHOTS_BY_NAME[seg["shot"]]
    audio, dest = AUDIO / f"{sid}.mp3", OUT / f"{sid}.mp4"
    seconds = dur(audio) + 0.30
    face = KAREN / f"{sid}.mp4"
    use_face = seg.get("face") and face.exists()

    if shot.startswith("focus-"):
        chain = ("[0:v]scale=w=1640:h=860:force_original_aspect_ratio=decrease,"
                 "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0xf7f8fa")
    else:
        chain = f"[0:v]{'' if full else PAGE_CROP + ','}scale=1920:-2,crop=1920:1080"
    chain += ",fps=30,setsar=1"

    cmd = ["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(SHOTS / f"{shot}.png"),
           "-i", str(audio), "-loop", "1", "-i", str(ROOT / "overlays" / f"{sid}.png")]

    if use_face:
        cmd += ["-i", str(face)]
        if shot == "room-live":  # into the room's own video panel
            r = json.loads((SHOTS / "room-stage.json").read_text())
            box = (r["x"], r["y"], r["width"], r["height"])
        else:                    # a large card-side portrait
            box = (1150, 168, 660, 660)
        x, y, w, h = box
        # cover, then centre-crop: scaling a square clip into a 16:9 panel squashes her face
        fit = (f"[3:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
               f"crop={w}:{h},setsar=1[pip]")
        fc = f"{chain}[bg];{fit};[bg][pip]overlay={x}:{y}[withface];[withface][2:v]overlay=0:0[v]"
    else:
        fc = f"{chain}[bg];[bg][2:v]overlay=0:0[v]"

    # gain to a common level, then short fades so the cuts between clips do not click
    fc += (f";[1:a]volume={gain_db(audio)}dB,afade=t=in:st=0:d=0.05,"
           f"afade=t=out:st={max(seconds - 0.30, 0.1):.2f}:d=0.25[a]")

    cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", f"{seconds:.2f}",
            "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
            str(dest)]
    subprocess.run(cmd, check=True)
    return dest


def card(name: str, seconds: float) -> pathlib.Path:
    dest = OUT / f"{name}.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(SHOTS / f"{name}.png"),
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", str(seconds),
                    "-vf", "scale=1920:1080,setsar=1,fps=30", "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", str(dest)],
                   check=True)
    return dest


if __name__ == "__main__":
    parts = []
    for seg in SCRIPT["segments"]:
        parts.append(build(seg))
        print("built", seg["id"], flush=True)
    parts.append(card("card-end", 3.6))

    listing = OUT / "concat.txt"
    listing.write_text("".join(f"file '{p}'\n" for p in parts))
    final = ROOT / "gavel-v1.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", str(listing), "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                    "-ar", "48000", "-ac", "2", str(final)], check=True)
    print(f"\nFINAL {final}  {dur(final)/60:.2f} min")
