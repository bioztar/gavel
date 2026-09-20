"""Combo cut: the live screen capture as picture, the synthetic narration as sound.

The take has the real product being driven — every page, the Discord call, the deck — but
its live audio is a hackathon floor with stumbles and a dropped call. So the picture comes
from the recording and the sound is the scripted, normalised track built by assemble.py.
When Karen speaks, her lip-synced clip replaces the webcam panel in the recording.
"""
from __future__ import annotations
import json, pathlib, subprocess

SRC = pathlib.Path("/Users/alex/DEV/gavel/The AI Chair.mp4")
ROOT = pathlib.Path("/Users/alex/DEV/_assets/gavel-video")
WAVS, KAREN, OUT = ROOT / "wav", ROOT / "karen", ROOT / "combo"
OUT.mkdir(parents=True, exist_ok=True)
SCRIPT = json.loads(pathlib.Path(__file__).with_name("script.json").read_text())
W, H, FPS = 1920, 960, 30
SCREEN_W = 1420                      # the shared screen occupies the left of the recording
FACE = (1448, 70, 440, 820)          # where the webcam panel sat; Karen takes that column

# segment -> where in the take that screen is on show
LIVE = {
    "00-karen-open":    (388, 404),   # architecture, slide 1
    "01-open":          (404, 424),
    "02-thin-brief":    (28, 42),     # /compose, the thin brief typed
    "03-karen-gate":    (46, 62),     # the refusal page
    "04-gate-note":     (62, 82),
    "05-real-brief":    (30, 46),
    "06-confirm":       (88, 114),    # the agenda table
    "07-send":          (118, 150),   # the invite in the mailbox
    "08-room":          (192, 208),   # the meeting room page
    "09-karen-opens":   (226, 246),   # the Discord call
    "10-architecture":  (290, 340),   # slide 1
    "11-drift":         (406, 430),
    "12-karen-catch":   (430, 446),
    "13-catch-note":    (446, 462),   # slide 2
    "14-karen-next":    (466, 482),   # slide 3, roadmap
    "15-handoff-q":     (482, 496),
    "16-artem":         (496, 556),
    "17-karen-handover": (540, 556),
    "18-roadmap":       (466, 502),
    "19-close":         (520, 556),
}


def dur(p: pathlib.Path) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", str(p)], capture_output=True,
                                text=True).stdout.strip())


def build(seg: dict) -> pathlib.Path:
    sid = seg["id"]
    wav = WAVS / f"{sid}.wav"
    length = dur(wav)
    start, end = LIVE[sid]
    dest = OUT / f"{sid}.mp4"
    face = KAREN / f"{sid}.mp4"
    use_face = seg.get("face") and face.exists()

    # Extract the span first, then loop the extracted file. `-stream_loop` with `-t` as an
    # *input* option caps the total read instead of looping, which left the picture short.
    span = OUT / f"_span-{start}-{end}.mp4"
    if not span.exists():
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(start), "-to", str(end),
                        "-i", str(SRC), "-an",
                        # drop the webcam: the recorded mouth does not match this narration
                        "-vf", (f"crop={SCREEN_W}:{H}:0:0,scale={SCREEN_W}:{H},"
                                f"pad={W}:{H}:0:0:color=0x0d0f12,fps={FPS},setsar=1"),
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-pix_fmt", "yuv420p", str(span)], check=True)
    cmd = ["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", str(span)]
    chain = f"[0:v]fps={FPS},setsar=1"
    if use_face:
        x, y, w, h = FACE
        cmd += ["-stream_loop", "-1", "-i", str(face)]
        fc = (f"{chain}[bg];"
              f"[1:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
              f"setsar=1[pip];[bg][pip]overlay={x}:{y}[v]")
    else:
        fc = f"{chain}[v]"

    cmd += ["-filter_complex", fc, "-map", "[v]", "-an", "-t", f"{length:.3f}",
            "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", str(dest)]
    subprocess.run(cmd, check=True)
    return dest


if __name__ == "__main__":
    vids, wavs = [], []
    for seg in SCRIPT["segments"]:
        vids.append(build(seg))
        wavs.append(WAVS / f"{seg['id']}.wav")
        print(f"built {seg['id']:20s} {dur(vids[-1]):6.2f}s", flush=True)

    lv, la = OUT / "v.txt", OUT / "a.txt"
    lv.write_text("".join(f"file '{p}'\n" for p in vids))
    la.write_text("".join(f"file '{p}'\n" for p in wavs))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lv),
                    "-c", "copy", str(OUT / "track.mp4")], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(la),
                    "-c", "copy", str(OUT / "track.wav")], check=True)

    final = ROOT / "gavel-combo.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(OUT / "track.mp4"),
                    "-i", str(OUT / "track.wav"), "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                    "-movflags", "+faststart", str(final)], check=True)
    print(f"\nFINAL {final}  {dur(final)/60:.2f} min")
