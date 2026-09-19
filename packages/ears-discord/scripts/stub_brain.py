"""A stand-in brain: print every frame from ears, and speak into the call.

    just stub-brain                 # print frames, speak every 30s
    just stub-brain --every 0       # print frames only

Speaks a line synthesized with macOS `say` (a tone elsewhere), so you can hear
the playback path work without the real brain or TTS.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import math
import struct
import subprocess
import tempfile
import uuid
from pathlib import Path

import websockets

from ears.audio import wav_bytes
from ears.settings import get_settings

LINE = "This is gavel. I can hear you."


def canned_audio() -> bytes:
    try:
        out = Path(tempfile.mkdtemp()) / "line.wav"
        subprocess.run(
            ["say", "-o", str(out), "--data-format=LEI16@48000", LINE], check=True, timeout=10
        )
        return out.read_bytes()
    except (OSError, subprocess.SubprocessError):
        rate = 48_000
        tone = b"".join(
            struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / rate)))
            for i in range(int(rate * 0.6))
        )
        return wav_bytes(tone, rate=rate)


def show(frame: dict) -> str:
    kind = frame.get("type", "?")
    who = frame.get("name") or frame.get("discordId", "")
    rest = {
        k: v
        for k, v in frame.items()
        if k not in {"type", "at", "atMs", "discordId", "name", "participants"}
    }
    if "participants" in frame:
        rest["people"] = [p["name"] for p in frame["participants"]]
    return f"{frame.get('at', '')[11:23]}  {kind:<15} {who:<20} {json.dumps(rest)}"


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--every", type=float, default=30, help="seconds between speaks; 0 = never")
    args = parser.parse_args()
    settings = get_settings()
    url = f"ws://{settings.wire_host}:{settings.wire_port}"
    audio = base64.b64encode(canned_audio()).decode() if args.every else ""

    async for ws in websockets.connect(url):
        print(f"connected to {url}")
        try:

            async def speak_loop(ws=ws) -> None:
                while args.every:
                    await asyncio.sleep(args.every)
                    uid = str(uuid.uuid4())
                    await ws.send(
                        json.dumps(
                            {"type": "speak", "utteranceId": uid, "audio": audio, "format": "wav"}
                        )
                    )
                    print(f"{'':12}  → speak          {uid}")

            speaker = asyncio.create_task(speak_loop())
            async for raw in ws:
                print(show(json.loads(raw)))
            speaker.cancel()
        except websockets.ConnectionClosed:
            print("disconnected, retrying")


if __name__ == "__main__":
    asyncio.run(main())
