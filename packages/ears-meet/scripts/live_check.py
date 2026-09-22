"""Join a real Google Meet and print what ears-meet sees. For a human to run — not a test.

    uv run python scripts/live_check.py                    # ears must already be running
    uv run python scripts/live_check.py --launch           # start `python -m ears_meet` too
    uv run python scripts/live_check.py --launch --speak-after 20 --duration 180

Connects to the ears wire as a stand-in brain and prints every frame as it arrives, one
line each. After `--speak-after` seconds it sends one `speak` command (a 440 Hz tone, or
a WAV file via `--wav`) and reports the matching `spoken` frame — `error` set means the
audio did not verifiably reach the call. At the end it prints a scorecard: which people
were seen, who produced speaking events, whether captions gave attributed transcripts,
and the selector self-check from `/api/selfcheck`.

What to look for in the meeting:
  * the bot appears as a participant, unmuted, camera off;
  * when you speak, a `speaking.start` for your name arrives within ~200 ms and a
    `speaking.end` about 400 ms after you stop;
  * with captions on, `transcript` frames carry your name and words;
  * when the tone plays, the OTHER participants hear it. If they do not, the `spoken`
    frame should say so in `error`; if it does not, that is a bug to report.

Settings come from .env like the service itself (MEET_URL, MEET_PROFILE_DIR, WIRE_PORT...).
Credential values are never printed; a missing one is reported by name by the service.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import json
import math
import struct
import sys
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

import httpx
import websockets

from ears_meet.audio import wav_bytes
from ears_meet.settings import get_settings


def tone(seconds: float = 1.5, hz: float = 440.0, rate: int = 48_000) -> bytes:
    pcm = b"".join(
        struct.pack("<h", int(9000 * math.sin(2 * math.pi * hz * i / rate)))
        for i in range(int(rate * seconds))
    )
    return wav_bytes(pcm, rate=rate, channels=1)


def show(frame: dict[str, Any]) -> str:
    kind = frame.get("type", "?")
    who = frame.get("name") or frame.get("discordId", "")
    rest = {
        k: v
        for k, v in frame.items()
        if k not in {"type", "at", "atMs", "discordId", "name", "participants", "agenda"}
    }
    if "participants" in frame:
        rest["people"] = [p["name"] for p in frame["participants"]]
    if "agenda" in frame:
        rest["agenda"] = bool(frame["agenda"])
    return f"{str(frame.get('at', ''))[11:23]}  {kind:<15} {str(who)[:28]:<28} {json.dumps(rest)}"


class Scorecard:
    def __init__(self, bot_name: str) -> None:
        self.bot_name = bot_name
        self.types: Counter[str] = Counter()
        self.people: dict[str, str] = {}
        self.spoke: set[str] = set()
        self.captioned: set[str] = set()
        self.spoken: list[dict[str, Any]] = []
        self.self_check: dict[str, Any] | None = None

    def see(self, frame: dict[str, Any]) -> None:
        kind = str(frame.get("type"))
        self.types[kind] += 1
        for p in frame.get("participants", []) or []:
            self.people[p["discordId"]] = p["name"]
        if kind == "speaking.start":
            self.spoke.add(str(frame.get("discordId")))
        if kind == "transcript" and frame.get("final"):
            self.captioned.add(str(frame.get("discordId")))
        if kind == "spoken":
            self.spoken.append(frame)

    def render(self) -> str:
        lines = ["", "— scorecard —"]
        lines.append("frames: " + ", ".join(f"{k} x{v}" for k, v in sorted(self.types.items())))
        others = {i: n for i, n in self.people.items() if n != self.bot_name}
        lines.append(f"people seen: {sorted(self.people.values())}")
        heard = sorted(others[i] for i in self.spoke if i in others)
        lines.append(f"speaking events from: {heard or 'NOBODY — speaking indicator selector?'}")
        cap = sorted(others[i] for i in self.captioned if i in others)
        lines.append(f"attributed transcripts from: {cap or 'nobody (captions off or unmatched)'}")
        for s in self.spoken:
            verdict = "FAILED " + str(s["error"]) if s.get("error") else "reached the call"
            lines.append(f"speak {s['utteranceId'][:8]}: {verdict}")
        if self.self_check is not None:
            lines.append(
                f"self-check: ok={self.self_check.get('ok')} "
                f"missing_required={self.self_check.get('missing_required')} "
                f"missing_optional={self.self_check.get('missing_optional')}"
            )
        ok = bool(heard) and all(not s.get("error") for s in self.spoken)
        lines.append("verdict: " + ("LOOKS GOOD" if ok else "NOT PROVEN — see above"))
        return "\n".join(lines)


async def wait_for_wire(http_url: str, patience: float) -> None:
    deadline = time.monotonic() + patience
    async with httpx.AsyncClient() as http:
        while time.monotonic() < deadline:
            with contextlib.suppress(httpx.HTTPError):
                r = await http.get(f"{http_url}/health", timeout=2)
                if r.status_code == 200:
                    return
            await asyncio.sleep(1)
    raise SystemExit(f"ears did not come up on {http_url} within {patience:.0f}s")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--launch", action="store_true", help="start `python -m ears_meet` as a child"
    )
    parser.add_argument(
        "--duration", type=float, default=120, help="seconds to observe (0 = until Ctrl-C)"
    )
    parser.add_argument(
        "--speak-after", type=float, default=15, help="seconds before the test speak; 0 = never"
    )
    parser.add_argument("--wav", type=Path, help="a WAV file to speak instead of the tone")
    parser.add_argument("--raw", action="store_true", help="print frames as JSON lines")
    args = parser.parse_args()

    settings = get_settings()
    ws_url = f"ws://{settings.wire_host}:{settings.wire_port}"
    http_url = f"http://{settings.wire_host}:{settings.wire_port}"
    card = Scorecard(settings.meet_bot_name)

    child: asyncio.subprocess.Process | None = None
    if args.launch:
        child = await asyncio.create_subprocess_exec(sys.executable, "-m", "ears_meet")
    try:
        await wait_for_wire(http_url, patience=90 if args.launch else 10)
        audio = base64.b64encode(args.wav.read_bytes() if args.wav else tone()).decode()

        async with websockets.connect(ws_url, max_size=None) as ws:
            print(f"connected to {ws_url}; watching for {args.duration or '∞'}s")

            async def speak_once() -> None:
                if not args.speak_after:
                    return
                await asyncio.sleep(args.speak_after)
                uid = str(uuid.uuid4())
                await ws.send(
                    json.dumps(
                        {
                            "type": "speak",
                            "utteranceId": uid,
                            "audio": audio,
                            "format": "wav",
                            "text": "live_check test tone",
                        }
                    )
                )
                print(f"{'':12}  → speak          {uid}   (can the others hear a tone?)")

            async def listen() -> None:
                async for raw in ws:
                    frame = json.loads(raw)
                    card.see(frame)
                    print(raw if args.raw else show(frame))

            tasks = [asyncio.create_task(speak_once()), asyncio.create_task(listen())]
            try:
                if args.duration:
                    await asyncio.wait(tasks, timeout=args.duration)
                else:
                    await asyncio.gather(*tasks)
            except (KeyboardInterrupt, asyncio.CancelledError):
                pass
            finally:
                for t in tasks:
                    t.cancel()

        async with httpx.AsyncClient() as http:
            with contextlib.suppress(httpx.HTTPError):
                card.self_check = (await http.get(f"{http_url}/api/selfcheck", timeout=30)).json()
    finally:
        print(card.render())
        if child is not None:  # SIGTERM: the service leaves the call and tears down cleanly
            with contextlib.suppress(ProcessLookupError):
                child.terminate()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(child.wait(), 20)


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
