"""Build the v1 submission video from synthesized audio, live screenshots and Karen clips.

Every segment becomes its own 1920x1080 clip (slow Ken Burns over the shot, speaker
label, Karen picture-in-picture when she talks), then all of them are concatenated.
Shots that stand in for footage we have not captured yet carry a PLACEHOLDER badge.
"""
from __future__ import annotations
import json, pathlib, subprocess

ROOT = pathlib.Path("/Users/alex/DEV/_assets/gavel-video")
SHOTS, AUDIO, KAREN, OUT = ROOT / "shots", ROOT / "audio", ROOT / "karen", ROOT / "out"
OUT.mkdir(parents=True, exist_ok=True)
SCRIPT = json.loads(pathlib.Path(__file__).with_name("script.json").read_text())
FONT = "/tmp/claude-501/ArialBold.ttf"
FONT_R = "/tmp/claude-501/Arial.ttf"
# page screenshots put the content in a column; crop to it so the frame is not 40% whitespace
PAGE_CROP = "crop=1290:726:315:40"
LABEL = {"vitaly": "VITALY", "artem": "ARTEM", "karen": "KAREN  (the chair)"}

# segment id -> (shot, full-frame?, placeholder-for)
SHOT_MAP = {
    "01-open": ("arch1", True, None),
    "02-thin-brief": ("compose", False, None),
    "03-karen-gate": ("gate", False, None),
    "04-gate-note": ("gate", False, None),
    "05-real-brief": ("compose-empty", False, None),
    "06-confirm": ("confirm-table", False, None),
    "07-gauge": ("confirm-gauge", False, None),
    "08-send": ("invite-agenda", False, None),
    "09-join": ("invite", False, "calendar accept + join"),
    "10-karen-opens": ("arch1", True, "Discord call"),
    "11-opened-note": ("arch1", True, "Discord call"),
    "12-architecture": ("arch1", True, None),
    "13-drift": ("arch1", True, None),
    "14-karen-catch": ("arch1", True, None),
    "15-catch-note": ("arch2", True, "ears console"),
    "16-handoff-q": ("arch1", True, "Discord call"),
    "17-artem": ("arch1", True, "Discord call"),
    "18-karen-handover": ("arch1", True, None),
    "19-handover-note": ("confirm-gauge", False, "ears console"),
    "20-roadmap": ("arch3", True, None),
    "21-close": ("arch3", True, None),
}


def dur(path: pathlib.Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "")


def build(seg: dict) -> pathlib.Path:
    sid = seg["id"]
    shot, full, placeholder = SHOT_MAP[sid]
    audio = AUDIO / f"{sid}.mp3"
    dest = OUT / f"{sid}.mp4"
    TEMPO = 1.06  # deterministic trim to fit the 7:00 ceiling; minimax's own speed knob barely moved
    seconds = dur(audio) / TEMPO + 0.28
    frames = int(seconds * 30) + 2
    face = KAREN / f"{sid}.mp4"
    use_face = seg.get("face") and face.exists()

    base = f"[0:v]{'' if full else PAGE_CROP + ','}scale=1920:-2,crop=1920:1080"
    kb = ("" if full else
          f",zoompan=z='min(zoom+0.00035,1.09)':d={frames}:x='iw/2-(iw/zoom/2)'"
          f":y='ih/2-(ih/zoom/2)':s=1920x1080:fps=30")
    chain = base + kb + ",fps=30,setsar=1"

    overlay = ROOT / "overlays" / f"{sid}.png"
    cmd = ["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(SHOTS / f"{shot}.png"),
           "-i", str(audio), "-loop", "1", "-i", str(overlay)]
    if use_face:
        cmd += ["-i", str(face)]
        fc = (f"{chain}[bg];"
              f"[3:v]scale=440:440,setsar=1[pip];"
              f"[bg][pip]overlay=W-w-72:H-h-168[withface];"
              f"[withface][2:v]overlay=0:0[v]")
    else:
        fc = f"{chain}[bg];[bg][2:v]overlay=0:0[v]"
    fc += f";[1:a]atempo={TEMPO},loudnorm=I=-16:TP=-1.5:LRA=11[a]"
    cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]",
            "-t", f"{seconds:.2f}", "-r", "30", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
            str(dest)]
    subprocess.run(cmd, check=True)
    return dest


def card(name: str, seconds: float) -> pathlib.Path:
    dest = OUT / f"{name}.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(SHOTS / f"{name}.png"),
         "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", str(seconds),
         "-vf", "scale=1920:1080,setsar=1,fps=30", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", str(dest)],
        check=True)
    return dest


if __name__ == "__main__":
    parts = [card("card-title", 3.2)]
    for seg in SCRIPT["segments"]:
        parts.append(build(seg))
        print("built", seg["id"], flush=True)
    parts.append(card("card-end", 3.6))

    listing = OUT / "concat.txt"
    listing.write_text("".join(f"file '{p}'\n" for p in parts))
    final = ROOT / "gavel-v1.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", str(listing), "-c", "copy", str(final)], check=True)
    print(f"\nFINAL {final}  {dur(final)/60:.2f} min")
