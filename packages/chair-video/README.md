# chair-video

Turns the chair's spoken audio into a lip-synced talking-head clip through fal.
A service the brain calls — it makes no decisions and never touches the agenda.

## Personas

Two personas, one face (Karen): `formal` and `funky`. `packages/brain/config/personas.yaml`
(owned by another crewmate) is the source of truth for a persona's **tone and template
lines**. This service's `settings.py` (`avatar_image_by_persona`, `idle_video_by_persona`)
is the source of truth for **which file** a persona renders with — that's this service's
own concern, not the brain's.

Both `POST /speak-video` and `GET /idle` take an optional `persona` field/param
(`"formal"` / `"funky"`, default `"funky"`). An unknown or missing value silently falls
back to the configured default rather than erroring — on stage a typo must not silence the chair.

## Endpoints

- `POST /speak-video` — `{"audioUrl"}` or `{"audioBase64","format"}` (+ optional
  `"persona"`) → `{"videoUrl","durationMs","latencyMs"}`. Re-syncs the persona's idle
  video loop to the given audio via the configured `lipsync_model`. Results are cached
  in-memory keyed by `persona + sha256(audio)` — a repeated line costs nothing.
- `GET /idle?persona=formal|funky` — the persona's idle loop/still, served directly.
- `GET /healthz` — fal reachability + model ids in use, plus Director session state.
- `/director/*` — the live WebRTC session manager and stage proxy. See below.

## Lip-sync model: measured, not guessed

Candidates were timed end-to-end (submit → COMPLETED) against real fal, for a 3s and an
8s utterance, using `karen-formal.png` / a static idle loop:

| model | utterance | latency |
|---|---|---|
| `fal-ai/sync-lipsync/v2` | 3s | 58.3s |
| `fal-ai/sync-lipsync/v2` | 8s | 70.4s |
| `veed/lipsync/v2` | 3s | 41.4s |
| `veed/lipsync/v2` | 8s | 47.0s |
| `fal-ai/kling-video/lipsync/audio-to-video` | 3s | 114.8s |
| `fal-ai/kling-video/lipsync/audio-to-video` | 8s | FAILED — timed out after 120.0s |
| `fal-ai/longcat-single-avatar/image-audio-to-video` | 3s | FAILED — timed out after 120.0s |
| `fal-ai/longcat-single-avatar/image-audio-to-video` | 8s | FAILED — timed out after 120.0s |

`fal-ai/longcat-single-avatar/image-audio-to-video` was the original pick (it takes a
still `image_url` directly, no idle loop needed) but it timed out on both runs — not
viable for a live demo. Reproducible: `uv run python scripts/measure_latency.py`.

Everything reliable takes `video_url` (re-syncs an existing clip), not `image_url`. So
`/speak-video` re-syncs the persona's **idle loop**, not the portrait still. Default
`lipsync_model` is `veed/lipsync/v2` — fastest of the models that completed both runs.
Overridable via env, so a faster model found later is a config change, not a redeploy.

## `minimax/h3-max/director` — live stream, measured against real fal

Karen is **live**. This replaces the queue-and-wait lip-sync path above with a persistent
WebRTC session, rendered on a browser stage page (Discord blocks bot video outright, so this
page is the chair's visual face — never a camera in the call, shown on a projector instead).

**Phase 0 spike (real fal, no mocks, 5 sessions, each explicitly closed within 8–20s):**

- Transport is **WebRTC end to end**: one-shot SDP offer/answer POSTed to `wma.fal.run` (no
  trickle ICE), TURN creds fetched from `wma.fal.run/ice`. No LiveKit SDK required — LiveKit is
  only an alternate audio codec mode name, not a dependency. Used `@fal-ai/client@alpha`'s
  `wma` realtime extension directly.
- One data channel (`control`). Client→server: `configure` (first message), `prompt`
  (mid-session steering — **must carry a `prompt_version` higher than the last accepted one,
  or the server silently drops it as `stale_prompt_version`**). Server→client:
  `session_info`/`configured`/`chunk`/`prompt_applied`/`audio_applied`/`error`/etc. Actual
  video+audio arrive as WebRTC `MediaStream` tracks via `onMedia`, independent of the `chunk`
  telemetry cadence.
- **Audio is submitted by URL, not pushed over the wire** — `fal.storage.upload()` first (fal's
  own CDN), then that URL as `prompt.audio_url`. A local/private URL will not work; fal's
  servers must be able to fetch it themselves.
- **Time-to-first-frame: ~4.6–5.1s** (session open → live media track) vs. the **41.4s**
  lip-sync replay it replaces. Mid-session audio: `client.prompt` → server `audio_applied` ack
  in **~900ms**. Director is genuinely live — the gate passed.
- **Price (checked 2026-09-19):** promotional rate expired 2026-09-14. Current list:
  **$0.08/s at 768p** (1080p is 2×), **$1.20/session minimum**, default session cap ~15min.
  Bills for the whole meeting's wall-clock time, not per utterance — the session manager opens
  once at meeting start and must close on every exit path, never leave one idle.
- **`FAL_KEY` can stay fully server-side** — confirmed with `fal.config({ proxyUrl })` pointed
  at a local proxy that reads `x-fal-target-url` and attaches the real key server-side; both
  the `/ice` and `/session` requests forwarded successfully, session came up in the same ~4.4s.
  The browser holds no fal credential at all.

Spike cost: ~$6.00 (5 sessions × the stated $1.20 minimum, ceiling not certainty — fal's
minimum-charge wording doesn't fully resolve strict-flat vs. flat-or-metered for a session
this short).

**Architecture built on top of the spike:**

- **Python (`chair_video/director.py` + `app.py`) is the coordinator and proxy, not the peer.**
  `DirectorManager` is pure logic (no network calls, injectable clock — unit-testable with zero
  mocking): lazily opens a session on the first `speak()` of a meeting, tracks
  `prompt_version`, self-restarts past `director_max_session_s` (14min, under fal's own ~15min
  cap so the manager controls the cut), and reports heartbeat-derived state for `/healthz`.
- **The browser (`stage/` → committed `static/stage.bundle.js`) owns the actual
  `RTCPeerConnection`.** Python cannot open or close a browser's peer connection — it can only
  ask the stage page to, via Server-Sent Events (`GET /director/events`: `start`/`speak`/`stop`
  commands), and listen for `POST /director/heartbeat` (every 5s) to know the stage is still
  alive. **A lost heartbeat only degrades what `/healthz` reports — it cannot billing-stop
  anything**, since Python can't reach into the browser tab. fal's own server-side idle
  reaping, plus the 14-minute self-stop above, are the real leak backstops.
- **`FAL_KEY` never reaches the browser.** `POST/GET /director/fal-proxy` is exact-host
  allowlisted (`wma.fal.run` only — checked via `urlsplit().hostname`, not a suffix match, so
  `wma.fal.run.evil.com` or a userinfo trick fails closed), strips any inbound `Authorization`,
  forwards only `content-type`/`accept`, and requires a valid `x-director-token` (the
  per-session token handed to the stage page over SSE) before it will attach the real key and
  forward anything. Without the token gate this would be an open, billed relay to fal for
  anyone who can reach chair-video.
- **The stage page's JS is a committed build artifact, not a runtime CDN import.** `stage/` is
  a small npm project pinning `@fal-ai/client` to the exact spike-verified `1.11.0-alpha.3`
  (no `^`), esbuild-bundled once to `static/stage.bundle.js`. No node/build step needed at
  serve time, no dependency on an alpha package resolving correctly over conference wifi.
- **Known limitation:** a persona switch mid-meeting does not restart an already-live Director
  session — the visual prompt was set once at session start. Fine for the demo (funky Karen is
  the default and the only persona actually shown live); a future change would need to send an
  updated `configure`-equivalent message, which the current `prompt`/`configure` split in the
  fal protocol doesn't cleanly support without a version bump.

**Endpoints added:** `POST /director/session/start`, `POST /director/session/stop`,
`POST /director/speak` (`{"audioBase64","format","persona"}` → uploads via the same
`FalClient.upload` `/speak-video` uses, returns `{"sessionId","promptVersion"}`),
`POST /director/heartbeat`, `GET /director/events` (SSE), `GET/POST /director/fal-proxy`.
`GET /healthz` now includes `"director": {...}` alongside the existing fal fields.

**Brain integration:** `packages/brain/src/engine.ts`'s `speak()` fires a
fire-and-forget `POST {CHAIR_VIDEO_URL}/director/speak` right after TTS synthesis (2s
abort timeout, logs and continues on failure) — never awaited, so a down or slow
chair-video cannot delay or break the existing Discord voice path. No-ops entirely if
`CHAIR_VIDEO_URL` is unset, so the idle-loop/lip-sync fallback above keeps working
unchanged when Director isn't configured.

## Config

Env vars (loaded from the repo-root `.env`, see `settings.py`):

- `FAL_KEY` — required. Service fails fast with `FAL_KEY is not set` if missing.
- `LIPSYNC_MODEL` — default `veed/lipsync/v2`.
- `AVATAR_MODEL` — default `fal-ai/flux/schnell`.
- `FAL_POLL_TIMEOUT_S` / `FAL_POLL_INTERVAL_S` — queue poll budget, default 120s / 1s.
- `DIRECTOR_ENDPOINT_ID` — default `fal-ai/minimax-h3-max-director`.
- `DIRECTOR_PROXY_HOST` — exact host the fal-proxy will forward to, default `wma.fal.run`.
- `DIRECTOR_RESOLUTION` / `DIRECTOR_ASPECT_RATIO` — default `480p` / `16:9`.
- `DIRECTOR_HEARTBEAT_TIMEOUT_S` — stage heartbeat staleness before `/healthz` reports
  `degraded`, default 15s.
- `DIRECTOR_MAX_SESSION_S` — self-imposed session lifetime before an auto-restart, default
  14min (under fal's own ~15min cap).

## Scripts

- `scripts/demo.py` — wav in, video URL out, proof of end-to-end.
- `scripts/measure_latency.py` — regenerates the latency table above against real fal.
- `scripts/gen_funky_karen.py` — one-off generator for the funky Karen avatar variants
  (see `avatars/PROMPTS.md` for what prompts/strengths actually worked).
