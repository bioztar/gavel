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
(`"formal"` / `"funky"`, default `"formal"`). An unknown or missing value silently falls
back to formal rather than erroring — on stage a typo must not silence the chair.

## Endpoints

- `POST /speak-video` — `{"audioUrl"}` or `{"audioBase64","format"}` (+ optional
  `"persona"`) → `{"videoUrl","durationMs","latencyMs"}`. Re-syncs the persona's idle
  video loop to the given audio via the configured `lipsync_model`. Results are cached
  in-memory keyed by `persona + sha256(audio)` — a repeated line costs nothing.
- `GET /idle?persona=formal|funky` — the persona's idle loop/still, served directly.
- `GET /healthz` — fal reachability + model ids in use.

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

## `minimax/h3-max/director` — live stream, not a file

The mission asked whether Director's output is playable in a browser `<video>` element.
**It is not, and it is not a queue job at all.** Findings from the model page (helm, not the
crewmate — this section was written during merge):

- Transport is **WebRTC**, with LiveKit named explicitly ("Opus audio mode on direct WebRTC…
  LiveKit uses its native mode with the same bitrate target"). No HLS, no RTMP, no mp4 URL
  appears anywhere on the page. A plain `<video src="…">` cannot play it; it needs a WebRTC
  client SDK.
- It publishes an **AsyncAPI** spec alongside the OpenAPI one — an event/message-driven
  session, not `POST` → poll → fetch like every other fal model here.
- It is a **session**, priced per second of video generated, with a session minimum and a
  default cap around 15 minutes. Check the live page for the current rate before budgeting:
  a promotional rate was advertised as ending mid-September.
- No published latency number. Generation proceeds in chunks conditioned on prior context,
  so a live prompt change takes effect from a segment boundary, not instantly.

**What this means for gavel.** Director is the only option here that is genuinely live — a
chair visibly present and reacting, rather than a clip that arrives after the moment passed.
The cost is a LiveKit client integration that does not exist yet, plus per-second billing
while the meeting runs. The lip-sync table above is the argument for paying it: the fastest
model that completed takes 41s to sync a 3-second line, which is not a chair, it is a replay.

Not attempted: measuring Director end to end, or reading its actual output message schema
(`/api/apps/fal-ai/minimax-h3-max-director/asyncapi.json`). Both are needed before committing.

## Config

Env vars (loaded from the repo-root `.env`, see `settings.py`):

- `FAL_KEY` — required. Service fails fast with `FAL_KEY is not set` if missing.
- `LIPSYNC_MODEL` — default `veed/lipsync/v2`.
- `AVATAR_MODEL` — default `fal-ai/flux/schnell`.
- `FAL_POLL_TIMEOUT_S` / `FAL_POLL_INTERVAL_S` — queue poll budget, default 120s / 1s.

## Scripts

- `scripts/demo.py` — wav in, video URL out, proof of end-to-end.
- `scripts/measure_latency.py` — regenerates the latency table above against real fal.
- `scripts/gen_funky_karen.py` — one-off generator for the funky Karen avatar variants
  (see `avatars/PROMPTS.md` for what prompts/strengths actually worked).
