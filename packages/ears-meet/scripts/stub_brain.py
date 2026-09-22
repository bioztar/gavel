"""A stand-in brain: print every frame from ears-meet, and speak into the call.

    just stub-brain                 # print frames, speak a tone every 30s
    just stub-brain --every 0       # print frames only

Same shape as ears-discord/scripts/stub_brain.py, so the two surfaces can be watched the
same way. For a structured pass/fail run use scripts/live_check.py instead.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import math
import struct
import uuid

import websockets

from ears_meet.audio import wav_bytes
from ears_meet.settings import get_settings


def canned_audio() -> bytes:
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
        if k not in {"type", "at", "atMs", "discordId", "name", "participants", "agenda"}
    }
    if "participants" in frame:
        rest["people"] = [p["name"] for p in frame["participants"]]
    return f"{str(frame.get('at', ''))[11:23]}  {kind:<15} {str(who)[:28]:<28} {json.dumps(rest)}"


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--every", type=float, default=30, help="seconds between speaks; 0 = never")
    args = parser.parse_args()
    settings = get_settings()
    url = f"ws://{settings.wire_host}:{settings.wire_port}"
    audio = base64.b64encode(canned_audio()).decode() if args.every else ""

    async for ws in websockets.connect(url, max_size=None):
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
