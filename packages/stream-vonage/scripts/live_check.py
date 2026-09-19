#!/usr/bin/env python3
"""Real E2E check against the live Vonage Video API. Not run in CI, not run
by `pytest` (`tests/unit/` mocks `VonageClient` at the module boundary and
makes no network call — see `tests/unit/conftest.py`) — this is the one
script in the package that actually talks to Vonage.

Run it once real credentials are confirmed present (`GET /healthz` on a
running `stream-vonage` service reports `"credentials": "present"`):

    uv run python scripts/live_check.py

What it does:
1. Builds `Settings()` (same env-file resolution as the service) and refuses
   to run if no credential pair is configured, naming the missing setting.
2. Creates a session, mints a publisher token, starts an archive, starts an
   HLS broadcast — the same call order as `POST /stream/start`.
3. Polls the returned HLS URL with `HEAD`/`GET` until it returns 200 (or a
   timeout), timing how long that takes from broadcast-start.
4. Stops the broadcast and the archive (same order as `POST /stream/stop`).
5. Prints ONLY timing and status — never the HLS url, the session id, the
   token, or any credential. See the repo-wide rule: "Credentials: never
   read, print, log or echo a value." The HLS url is itself a live,
   credential-bearing URL for the duration of the broadcast, so it gets the
   same treatment.

Update the README's "HLS start-up latency" section with the printed number
once this has actually been run against real credentials.
"""

from __future__ import annotations

import sys
import time

import httpx

from stream_vonage.settings import Settings
from stream_vonage.vonage import VonageClient, VonageError, VonageNotConfigured

POLL_INTERVAL_S = 1.0
POLL_TIMEOUT_S = 60.0


def _redact_url(url: str) -> str:
    """Host + path only — never the query string, which on an HLS/archive
    URL can carry a signed access token."""
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def _wait_for_hls_ready(hls_url: str) -> float | None:
    """Returns elapsed seconds until `hls_url` first responds 200, or `None`
    on timeout. Never logs `hls_url` itself."""
    deadline = time.monotonic() + POLL_TIMEOUT_S
    start = time.monotonic()
    with httpx.Client(timeout=5.0) as client:
        while time.monotonic() < deadline:
            try:
                resp = client.get(hls_url)
                if resp.status_code == 200:
                    return time.monotonic() - start
            except httpx.HTTPError:
                pass
            time.sleep(POLL_INTERVAL_S)
    return None


def main() -> int:
    settings = Settings()
    vonage = VonageClient(settings)

    session_id = None
    archive_id = None
    broadcast_id = None
    try:
        t_session = time.monotonic()
        session_id = vonage.create_session()
        print(f"live_check: auth style = {vonage.auth_style}")
        print(f"live_check: session created in {time.monotonic() - t_session:.2f}s")

        vonage.generate_token(session_id)
        print("live_check: publisher token minted")

        t_archive = time.monotonic()
        archive = vonage.start_archive(session_id)
        archive_id = archive.archive_id
        print(f"live_check: archive started in {time.monotonic() - t_archive:.2f}s")

        t_broadcast = time.monotonic()
        broadcast = vonage.start_broadcast(session_id)
        broadcast_id = broadcast.broadcast_id
        print(f"live_check: broadcast started in {time.monotonic() - t_broadcast:.2f}s")
        print(f"live_check: HLS host/path = {_redact_url(broadcast.hls_url)}")

        elapsed = _wait_for_hls_ready(broadcast.hls_url)
        if elapsed is None:
            print(
                f"live_check: HLS url did not return 200 within {POLL_TIMEOUT_S:.0f}s",
                file=sys.stderr,
            )
        else:
            print(f"live_check: HLS ready {elapsed:.2f}s after broadcast start")

    except VonageNotConfigured as exc:
        print(f"live_check: not configured — {exc}", file=sys.stderr)
        return 1
    except VonageError as exc:
        print(f"live_check: FAILED — {exc}", file=sys.stderr)
        return 1
    finally:
        if broadcast_id is not None:
            try:
                vonage.stop_broadcast(broadcast_id)
                print("live_check: broadcast stopped")
            except VonageError as exc:
                print(f"live_check: broadcast stop failed — {exc}", file=sys.stderr)
        if archive_id is not None:
            try:
                stopped = vonage.stop_archive(archive_id)
                has_url = stopped.url is not None
                print(f"live_check: archive stopped (url ready: {has_url})")
            except VonageError as exc:
                print(f"live_check: archive stop failed — {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
