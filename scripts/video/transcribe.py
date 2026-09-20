"""Timestamped transcript of a take, through the same SLNG route the chair uses."""
from __future__ import annotations
import json, pathlib, subprocess, sys

import httpx

WAV = pathlib.Path(sys.argv[1])
OUT = pathlib.Path(sys.argv[2])
KEY = next(l.split("=", 1)[1].strip()
           for l in pathlib.Path("/Users/alex/DEV/gavel/.env").read_text().splitlines()
           if l.startswith("SLNG_API_KEY="))
CHUNK = 120.0

total = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "csv=p=0", str(WAV)], capture_output=True, text=True).stdout)
words: list[dict] = []
offset = 0.0
while offset < total:
    part = pathlib.Path("/tmp/_stt_part.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(offset), "-t", str(CHUNK),
                    "-i", str(WAV), "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(part)],
                   check=True)
    r = httpx.post("https://eu-west.api.slng.ai/v1/stt/deepgram/nova:3",
                   headers={"Authorization": f"Bearer {KEY}"},
                   files={"audio": ("chunk.wav", part.read_bytes(), "audio/wav")},
                   data={"language": "en", "punctuate": "true", "smart_format": "true",
                         "keyterm": ["Karen", "gavel", "Artem", "Vitaly", "Discord", "agenda"]},
                   timeout=180)
    r.raise_for_status()
    body = r.json()
    alt = body["results"]["channels"][0]["alternatives"][0]
    for w in alt.get("words", []):
        words.append({"w": w["word"], "s": round(w["start"] + offset, 2),
                      "e": round(w["end"] + offset, 2)})
    print(f"{offset:6.0f}s  {alt.get('transcript','')[:110]}", flush=True)
    offset += CHUNK

OUT.write_text(json.dumps(words, indent=1))
print(f"\n{len(words)} words -> {OUT}")
