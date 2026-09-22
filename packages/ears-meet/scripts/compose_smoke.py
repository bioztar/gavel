"""Bring up `docker compose --profile meet` and prove the ears-meet container works, no account.

    just smoke-compose              # up --wait stage + ears-meet, run the checks, leave it running
    just smoke-compose --down       # ...then `compose down` the two services afterwards
    just smoke-compose --no-up      # only check an already-running stack

Runs with MEET_URL forced empty, so ears-meet starts in standby: no Meet is joined and no
Google sign-in is attempted. Each check prints the terminal output it is based on (this is
what goes into a PR description) and the script exits nonzero on the first one that fails.
No setting *values* are read or printed; only names of settings appear in the output.

Checks, all from inside the ears-meet container:
  1. Xvfb is running on DISPLAY=:99 (process + X socket)
  2. PulseAudio is running and `pactl list short sinks` has gavel_in and gavel_out
  3. the wire answers GET /health on 127.0.0.1:8787
  4. Chromium is up and has a tab at STAGE_URL titled exactly `gavel-stage` (via /api/browser)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SERVICES = ["stage", "ears-meet"]
STAGE_TITLE = "gavel-stage"
STAGE_URL = "http://stage:8793/"
WIRE = "http://127.0.0.1:8787"


def sh(*args: str, check: bool = True) -> str:
    print(f"$ {' '.join(args)}")
    proc = subprocess.run(args, cwd=REPO, capture_output=True, text=True)
    out = (proc.stdout + proc.stderr).rstrip()
    print(out)
    if check and proc.returncode != 0:
        raise SystemExit(f"FAIL: exit {proc.returncode}")
    return proc.stdout


def compose(*args: str) -> str:
    return sh("docker", "compose", "--profile", "meet", *args)


def in_meet(*args: str) -> str:
    return sh("docker", "compose", "--profile", "meet", "exec", "-T", "ears-meet", *args)


def expect(cond: bool, what: str) -> None:
    if not cond:
        raise SystemExit(f"FAIL: {what}")
    print(f"ok: {what}\n")


def wait_for_health(timeout: float = 180) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while True:
        proc = subprocess.run(
            [
                "docker",
                "compose",
                "--profile",
                "meet",
                "exec",
                "-T",
                "ears-meet",
                "curl",
                "-fsS",
                f"{WIRE}/health",
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            print(f"$ curl -fsS {WIRE}/health\n{proc.stdout.strip()}")
            return json.loads(proc.stdout)
        if time.monotonic() > deadline:
            print(proc.stdout + proc.stderr)
            raise SystemExit("FAIL: wire never answered /health")
        time.sleep(2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-up", action="store_true", help="check a stack that is already up")
    parser.add_argument("--down", action="store_true", help="compose down the services afterwards")
    parser.add_argument("--build", action="store_true", help="pass --build to compose up")
    args = parser.parse_args()

    # Standby, never a call: an empty MEET_URL wins over whatever .env says, without reading it.
    os.environ["MEET_URL"] = ""

    try:
        if not args.no_up:
            print("== up ==")
            up = ["up", "-d", "--wait", "--wait-timeout", "300"]
            if args.build:
                up.append("--build")
            compose(*up, *SERVICES)
            print()

        print("== (a) Xvfb on DISPLAY=:99 ==")
        procs = in_meet("sh", "-c", "pgrep -a Xvfb; echo DISPLAY=$DISPLAY; ls /tmp/.X11-unix/")
        expect("Xvfb :99" in procs, "Xvfb process serving :99")
        expect("DISPLAY=:99" in procs, "DISPLAY=:99 in the container")
        expect("X99" in procs, "X socket /tmp/.X11-unix/X99 exists")

        print("== (b) PulseAudio + null sinks ==")
        pulse = in_meet("sh", "-c", "pgrep -a pulseaudio; pactl list short sinks")
        expect("pulseaudio" in pulse, "pulseaudio process")
        sinks = {line.split("\t")[1] for line in pulse.splitlines() if "\tmodule-null-sink" in line}
        expect(
            {"gavel_in", "gavel_out"} <= sinks,
            f"null sinks gavel_in + gavel_out (saw {sorted(sinks)})",
        )

        print("== (c) wire GET /health on 127.0.0.1:8787 ==")
        health = wait_for_health()
        expect(
            health.get("status") == "standby", "wire is in standby (no MEET_URL, nothing joined)"
        )
        expect(health.get("inCall") is False, "not in a call")

        print("== (d) Chromium has the stage tab ==")
        deadline = time.monotonic() + 120
        while True:
            browser = json.loads(in_meet("curl", "-fsS", f"{WIRE}/api/browser"))
            if browser.get("stageTab") or time.monotonic() > deadline:
                break
            time.sleep(2)
        expect(browser["launched"] is True, "Chromium launched (has open tabs)")
        stage = browser.get("stageTab")
        expect(stage is not None, f"a tab titled exactly {STAGE_TITLE!r}")
        assert stage is not None
        expect(stage["url"] == STAGE_URL, f"stage tab is at {STAGE_URL}")

        print("SMOKE OK: stage + ears-meet are up; Xvfb, PulseAudio, wire and Chromium verified.")
    finally:
        if args.down:
            print("\n== down ==")
            compose("down", *SERVICES)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        if e.code and e.code != 0:
            print(e.code, file=sys.stderr)
            raise SystemExit(1) from None
        raise
