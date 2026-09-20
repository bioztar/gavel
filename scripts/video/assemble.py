"""Build the submission video from synthesized audio, live screenshots and Karen clips.

The audio is built as **one continuous PCM track** and muxed against the video at the end.
It is not 23 separately-encoded AAC clips stitched together: every clip carries its own
encoder delay, each segment's video ran ~0.25s past its own audio, and concat had to patch
a hole at all 23 joins — 5.8s of accumulated gap, audible as the sound cutting in and out
worse and worse as the video went on.

Two other things here were learned the hard way:

* Speed comes from the TTS, never from `atempo`. Time-stretching the cloned voice broke it up.
* Levels are two-pass `loudnorm` in linear mode. Single-pass pumped; a static peak gain left
  the three engines several dB apart.
"""
from __future__ import annotations
import json, pathlib, subprocess

ROOT = pathlib.Path("/Users/alex/DEV/_assets/gavel-video")
SHOTS, AUDIO, KAREN, OUT = ROOT / "shots", ROOT / "audio", ROOT / "karen", ROOT / "out"
WAVS = ROOT / "wav"
for d in (OUT, WAVS):
    d.mkdir(parents=True, exist_ok=True)
SCRIPT = json.loads(pathlib.Path(__file__).with_name("script.json").read_text())
MEASURED = ROOT / "loudness.json"
LABEL = {"vitaly": "VITALY", "artem": "ARTEM", "karen": "KAREN  ·  the chair"}
PAGE_CROP = "crop=1290:726:315:40"
TAIL = 0.30      # breathing room after each line — silence, but real silence
END_CARD = 3.6

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


def probe(path: pathlib.Path, entries: str, stream: str | None = None) -> str:
    cmd = ["ffprobe", "-v", "error"]
    if stream:
        cmd += ["-select_streams", stream]
    cmd += ["-show_entries", entries, "-of", "csv=p=0", str(path)]
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()


def dur(path: pathlib.Path) -> float:
    return float(probe(path, "format=duration"))


def loudness_filter(audio: pathlib.Path) -> str:
    """Two-pass EBU R128 to -16 LUFS: measure once, then one static gain."""
    cache = json.loads(MEASURED.read_text()) if MEASURED.exists() else {}
    if audio.name not in cache:
        err = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostats", "-i", str(audio),
             "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
            capture_output=True, text=True).stderr
        cache[audio.name] = json.loads(err[err.rindex("{"):err.rindex("}") + 1])
        MEASURED.write_text(json.dumps(cache, indent=2))
    m = cache[audio.name]
    return (f"loudnorm=I=-16:TP=-1.5:LRA=11:linear=true:measured_I={m['input_i']}"
            f":measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
            f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}")


def make_wav(seg: dict) -> pathlib.Path:
    """One normalised 48k stereo PCM clip per line, with its own tail of real silence."""
    dest = WAVS / f"{seg['id']}.wav"
    src = AUDIO / f"{seg['id']}.mp3"
    body = dur(src)
    af = (f"{loudness_filter(src)},aresample=48000,afade=t=in:st=0:d=0.05,"
          f"afade=t=out:st={max(body - 0.22, 0.05):.3f}:d=0.2,"
          f"apad=pad_dur={TAIL}")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af", af,
                    "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le",
                    "-t", f"{body + TAIL:.3f}", str(dest)], check=True)
    return dest


def build_video(seg: dict, seconds: float) -> pathlib.Path:
    """Silent video for one line, exactly as long as that line's audio."""
    sid = seg["id"]
    shot, full, _ = SHOTS_BY_NAME[seg["shot"]]
    dest = OUT / f"{sid}.mp4"
    face = KAREN / f"{sid}.mp4"
    use_face = seg.get("face") and face.exists()

    if shot.startswith("focus-"):
        chain = ("[0:v]scale=w=1640:h=860:force_original_aspect_ratio=decrease,"
                 "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0xf7f8fa")
    else:
        chain = f"[0:v]{'' if full else PAGE_CROP + ','}scale=1920:-2,crop=1920:1080"
    chain += ",fps=30,setsar=1"

    cmd = ["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(SHOTS / f"{shot}.png"),
           "-loop", "1", "-i", str(ROOT / "overlays" / f"{sid}.png")]
    if use_face:
        cmd += ["-stream_loop", "-1", "-i", str(face)]
        if shot == "room-live":
            r = json.loads((SHOTS / "room-stage.json").read_text())
            x, y, w, h = r["x"], r["y"], r["width"], r["height"]
        else:
            x, y, w, h = 1180, 250, 580, 580
        # cover then centre-crop: a square clip stretched into a 16:9 panel squashes her face
        fc = (f"{chain}[bg];"
              f"[2:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1[pip];"
              f"[bg][pip]overlay={x}:{y}[withface];[withface][1:v]overlay=0:0[v]")
    else:
        fc = f"{chain}[bg];[bg][1:v]overlay=0:0[v]"

    cmd += ["-filter_complex", fc, "-map", "[v]", "-an", "-t", f"{seconds:.3f}",
            "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", str(dest)]
    subprocess.run(cmd, check=True)
    return dest


def end_card() -> tuple[pathlib.Path, pathlib.Path]:
    vid = OUT / "card-end.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1",
                    "-i", str(SHOTS / "card-end.png"), "-t", str(END_CARD),
                    "-vf", "scale=1920:1080,setsar=1,fps=30", "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                    "-an", str(vid)], check=True)
    wav = WAVS / "card-end.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "anullsrc=r=48000:cl=stereo", "-t", str(END_CARD),
                    "-c:a", "pcm_s16le", str(wav)], check=True)
    return vid, wav


def concat(parts: list[pathlib.Path], listing: pathlib.Path, dest: pathlib.Path) -> None:
    listing.write_text("".join(f"file '{p}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", str(listing), "-c", "copy", str(dest)], check=True)


if __name__ == "__main__":
    vids, wavs = [], []
    for seg in SCRIPT["segments"]:
        wav = make_wav(seg)
        length = dur(wav)                       # the video is cut to the audio, never the reverse
        vids.append(build_video(seg, length))
        wavs.append(wav)
        print(f"built {seg['id']:18s} {length:6.2f}s", flush=True)
    v, w = end_card()
    vids.append(v); wavs.append(w)

    concat(vids, OUT / "concat-v.txt", OUT / "track.mp4")
    concat(wavs, OUT / "concat-a.txt", OUT / "track.wav")

    final = ROOT / "gavel-v1.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(OUT / "track.mp4"),
                    "-i", str(OUT / "track.wav"), "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                    "-ac", "2", "-movflags", "+faststart", str(final)], check=True)

    vd = float(probe(final, "stream=duration", "v:0"))
    ad = float(probe(final, "stream=duration", "a:0"))
    print(f"\nFINAL {final}  {dur(final)/60:.2f} min")
    print(f"video {vd:.3f}s  audio {ad:.3f}s  drift {ad - vd:+.3f}s")
