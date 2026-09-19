# stream-vonage

Puts the live gavel stage on Vonage Video as an HLS broadcast, **alongside** the Discord
call — never instead of it. Discord stays the meeting; this service makes no moderation
decisions and never touches the ears<->brain wire. A browser page (`/publisher`) joins a
Vonage session and publishes a screen capture (gavel stage + call audio) via
`getDisplayMedia()`; this service starts the broadcast and an archive of the same session
(the archive doubles as the hackathon submission video).

## Auth: official SDKs only, no hand-rolled JWT

Two Vonage account styles can be in play, and this service picks whichever env-var pair is
present:

| Style | Env vars | SDK wrapping it |
|---|---|---|
| **jwt** (current Vonage Application model) | `VONAGE_APPLICATION_ID`, `VONAGE_PRIVATE_KEY` | [`vonage`](https://pypi.org/project/vonage/) — `Vonage(Auth(application_id=..., private_key=...)).video` |
| **api_key** (legacy TokBox/OpenTok project) | `VONAGE_API_KEY`, `VONAGE_API_SECRET` | [`opentok`](https://pypi.org/project/opentok/) — `OpenTok(api_key, api_secret)` |

Token minting, the RS256 application JWT, and the legacy `X-OPENTOK-AUTH` header are
entirely the SDKs' problem — `src/stream_vonage/vonage.py` never encodes a JWT or signs an
HMAC itself. Confirmed by reading both packages' installed source (`vonage==4.9.0`,
`opentok==3.15.0`): `Video.create_session/generate_client_token/start_broadcast/
stop_broadcast/start_archive/stop_archive/send_signal` and `OpenTok.create_session/
generate_token/start_broadcast/stop_broadcast/start_archive/stop_archive/send_signal`
all exist with matching shapes for both styles, so there was no fallback case to fall
back from.

One thing the `vonage` package's source rules out by construction: `Video` builds every
request from `http_client.auth.application_id` and mints tokens via
`auth.generate_application_jwt` — there is no api_key/api_secret code path in that class.
So the jwt/api_key split above isn't a preference, it's the only way either credential
pair actually works against these SDKs.

Neither auth style's credentials are available yet (mission blocker) — see
`scripts/live_check.py` for the first real run once they land.

## Endpoints

- `GET /healthz` → `{"credentials": "present"|"absent", "authStyle": "jwt"|"api_key"|null}`.
- `POST /stream/start` → mints a routed Vonage session, starts an archive, starts an HLS
  broadcast, and starts a background thread that polls brain's `GET /state` and relays it
  into the session via `session.signal()` (depth addition #1 — see below). Returns
  `{"hlsUrl","sessionId","archiveId","broadcastId","applicationId","apiKey","token","watchUrl","broadcastStartedAt"}`.
  409 if a stream is already active; 503 if credentials are absent (message names the
  missing setting); 502 if Vonage rejects the call.
- `POST /stream/stop` → stops the signal-relay thread, then the broadcast, then the
  archive. Returns `{"archiveId","archiveUrl","hlsUrl"}` — `archiveUrl` is surfaced here by
  design (depth addition #2: archiving is on by default and its URL is handed back at
  stop, not left for someone to go dig up from the Vonage dashboard). It is commonly still
  `null` at this point — Vonage uploads/encodes archives asynchronously after stop, lagging
  seconds to a couple of minutes; poll `GET /v2/project/{id}/archive/{archiveId}` (not
  wired up here, not needed for the demo) if you need it sooner.
- `GET /stream/status` → `{"active","sessionId","hlsUrl","archiveId"}`, for `/watch`.
- `GET /publisher` → the one browser tab: joins the session, publishes a screen capture,
  polls `/brain-state` for its own on-screen agenda overlay. See the `audioSource` gotcha
  below.
- `GET /watch` → an hls.js player pointed at the last known `hlsUrl`.
- `GET /brain-state` → same-origin proxy of brain's read-only `GET /state` (brain sets no
  CORS headers, so the publisher page's `fetch()` goes through this service instead of
  crossing origins directly).

## Depth additions (Vonage track judging, not optional)

1. **`session.signal()` relay.** `POST /stream/start` spawns a background thread
   (`_signal_relay_loop` in `app.py`) that polls brain's `/state` every
   `STREAM_BRAIN_STATE_POLL_SECONDS` (default 2s) and, on change, calls the SDK's
   `send_signal`/`signal` method with `{"type": "brainState", "data": <json>}`. Every
   client connected to the Vonage session — not just the publisher tab — can subscribe to
   `session.on('signal:brainState', ...)` and render the live agenda/intervention state.
   Server-side (not the browser page calling `session.signal()` itself) so it works whether
   or not the publisher tab is the one polling, is testable offline with the rest of the
   suite, and survives a publisher-tab reload without losing the relay.
2. **Archiving on by default, URL surfaced at stop.** Every `/stream/start` call also
   starts an archive of the same session; `/stream/stop` returns its id and (once Vonage
   has it ready) its URL directly in the response body, rather than requiring a separate
   lookup. The archive is the hackathon submission video.

## The `audioSource` gotcha

**Never pass `audioSource: false`** when publishing the screen-capture stream. Vonage's
publisher options treat `audioSource: false` as "publish no audio track at all" — which
silently drops the gavel stage's call audio from the broadcast even though
`getDisplayMedia({video: true, audio: true})` captured it. `static/publisher.html` passes
the actual `MediaStreamTrack` from `getDisplayMedia()`'s `audioTracks[0]` as `audioSource`
(or omits the key entirely when the browser declined to grant audio, which Chrome does
on macOS unless "Share tab audio" was explicitly checked) — never the boolean.

## HLS start-up latency

**Not yet measured** — no Vonage credentials in this environment (mission blocker). Once
real credentials land, `uv run python scripts/live_check.py` starts a real session +
broadcast + archive against the live API and reports elapsed time from
`POST /stream/start` to the HLS URL returning `200` on repeated fetch — replace this
section with that measurement before the freeze.

## Runbook (two-line demo path)

```
# 1. before the demo, from packages/stream-vonage:
uv run python -m stream_vonage   # or: docker compose up stream-vonage

# 2. during the demo:
open http://127.0.0.1:8792/publisher   # join, share the gavel window, start audio
curl -X POST http://127.0.0.1:8792/stream/start   # -> hlsUrl; share /watch or the hlsUrl with judges
```

Stop with `curl -X POST http://127.0.0.1:8792/stream/stop` — note the returned
`archiveUrl` (or re-fetch `/stream/stop`'s last response from logs) for the submission
video.

## Local dev

```
uv sync
uv run pytest
uv run ruff check .
uv run pyright
```

Tests run fully offline: `tests/unit/` mocks `VonageClient` at the module boundary (see
`tests/unit/conftest.py`) so no real network call is made and no credential is required to
run the suite.
