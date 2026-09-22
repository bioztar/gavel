# ears-meet — gavel in a Google Meet

`packages/ears-meet` is the second `ears` implementation of [the contract](CONTRACT.md):
a Google Meet participant that puts `ready`, `participants`, `speaking.start`,
`speaking.end`, `transcript` and `spoken` on the wire and plays the brain's `speak` audio
into the call. The brain is started pointing at `ws://127.0.0.1:8787` and cannot tell
this surface from `ears-discord` — the conformance test below is the proof.

Status in one line: **the whole pipeline is built and tested against a faked browser and
faked PulseAudio; it has not yet been run against a real Meet.** Everything that needs a
live call is listed under "Not yet proven" and "Running it live".

---

## 1. Why a browser participant

The official Meet Media API was evaluated and rejected: its SDP is receive-only (the
client offers `a=recvonly`, Meet answers `a=sendonly`) so a client cannot speak into the
conference; it caps at three virtual audio streams that rotate among the loudest
speakers, so per-person talk time — what the whole floor policy runs on — is
unobtainable; and it requires Developer Preview enrolment for every participant.

So the bot is a browser: **a real, headful Chromium on an Xvfb display**, driven by
Playwright (Python). Not `--headless`: WebRTC media and `getDisplayMedia` (the stage
share) are unreliable or unavailable headless.

## 2. Architecture

```
                    ┌────────────────────── Xvfb :99 ──────────────────────┐
  meet.google.com   │  Chromium (persistent profile, unmuted, camera off)   │
  ◄──── WebRTC ────►│    tab 1: the call      tab 2: STAGE_URL (presented)  │
                    │      │ DOM                 ▲ playback   ▼ mic         │
                    └──────┼────────────────────┼────────────┼─────────────┘
                observer.js│            PulseAudio null sinks │
             (MutationObserver)     gavel_out ──monitor──► parec ──► STT (SLNG, as Discord)
                           │        gavel_in  ◄── pacat ◄── brain `speak` (wav/mp3/pcm)
                           ▼            └─monitor──► Chromium's microphone
                 Python: speaking debounce, roster diff, captions miner, turns
                           │
                           ▼
                 wire.py  ws://:8787  (brain)   ws://:8787/live (operator)   /api/* (store)
```

| concern | how | where |
|---|---|---|
| Sign-in | a **pre-authenticated Chromium profile directory** (`MEET_PROFILE_DIR`), made once by a human with `just login`. This is the implemented, preferred path. A scripted email/password fallback (`MEET_BOT_EMAIL`, `MEET_BOT_PASSWORD`) exists but Google's form fights it (captcha, "verify it's you"); it is best-effort and says so when it fails. | `browser.py` `_maybe_sign_in`, `scripts/login.py` |
| Join | open `MEET_URL`, fill the guest name if asked, mute camera, keep mic **on**, click Join / Ask to join, wait for admission (`MEET_ADMIT_TIMEOUT_S`) | `browser.py` `_lobby`, `_wait_admitted` |
| Who is speaking | `observer.js` is injected once in the call. A `MutationObserver` on the tile container posts every speaking-indicator flip (`{id, on, t}`) with the DOM timestamp; a 100 ms poll re-reads state as a safety net. Python debounces (`SPEAKING_ON_MS`=150 to start, `SPEAKING_OFF_MS`=400 to end) and emits `speaking.start` / `speaking.end` stamped with the DOM time, so a flicker never reaches the wire and bridge latency never skews floor timing. **No audio decoding is involved.** | `observer.js`, `speaking.py`, `app.py` `_on_indicator` |
| Identity | Meet's `data-participant-id` (`spaces/…/devices/…`) goes into the contract's `discordId` field — it is the generic participant-id field despite the name and must not be renamed — and the tile's display name into `name` | `roster.py`, `frames.py` |
| Join / leave | the observer posts the tile set whenever it changes; the roster diff emits `participants` | `roster.py` |
| Hearing | Chromium plays into the `gavel_out` null sink; `parec` on `gavel_out.monitor` yields 48 kHz stereo 20 ms frames — the same shape Discord's decoder produced — into the same SLNG streaming STT path. Because Meet mixes audio, STT segments are attributed to the speaking span they overlap most (`attribution.py`); if none, `meet:unattributed`. | `pulse.py` `Recorder`, `stt_stream.py`, `attribution.py` |
| Captions | the bot turns on Meet's own live captions and mines the captions region: a line is one utterance, every edit a non-final `transcript` delta, a line unedited for `CAPTION_SETTLE_MS` is final. Attributed for free. `TRANSCRIPT_SOURCE=auto` uses captions when showing and STT otherwise. | `captions.py`, `browser.py` `enable_captions` |
| Speaking | `speak` audio (wav/mp3/ogg via ffmpeg, or streamed `pcm_s16le`) is written with `pacat` into the `gavel_in` null sink; PulseAudio's default *source* is `gavel_in.monitor`, so that is what Chromium hands Meet as the microphone. The bot's mic is switched on in the lobby and re-checked after admission (`ensure_unmuted`); if a host mutes it, the next `spoken` reports egress unheard. Same queue, priority, `stop`, quiet-gate and streaming semantics as ears-discord. | `pulse.py` `PulsePlayer`, `app.py` playback queue |
| **Egress proof** | two checks, neither of which trusts local playback: (1) at startup `pactl list source-outputs` must show Chromium recording from `gavel_in.monitor`, else `egress.not_attached` is logged loudly; (2) per utterance, Meet lights the bot's *own* tile indicator from the microphone it captures — if it never lights while we play ≥ 1 s, the `spoken` frame carries `error: "egress unheard: …"`. A silent bot cannot believe it spoke. | `pulse.py` `egress_attached`, `app.py` `_egress_verdict` |
| Stage share | if `STAGE_URL` is set and answers, a second tab opens it and "Present now → **A tab**" is clicked; Chromium is launched with `--auto-select-tab-capture-source-by-title=gavel-stage` so no picker appears (the stage page guarantees `document.title === "gavel-stage"`). **Only tab capture works on a virtual display** — see "Stage share — status split in two" under §5; there is deliberately no `--auto-select-desktop-capture-source`, it is not a fallback. Stage unreachable: logged, meeting proceeds unpresented. `POST /api/present` retries later. | `browser.py` `present_stage` |
| Selectors | **all** in `selectors.py`, each a list of candidates tried in order, each candidate annotated `seen YYYY-MM` / `documented YYYY-MM` / `unverified`. `browser.self_check()` runs after joining and fails the process naming the missing *required* selector (`selfcheck.failed missing=[call.speaking_indicator]`); optional ones (captions, People panel) only warn. With `STAGE_URL` set, `call.present_tab_item` is required too: the check opens the Present menu, looks for "A tab", presses Escape, and if it is gone fails with *why* (entire-screen capture cannot start on a virtual display). `GET /api/selfcheck` re-runs it live. | `selectors.py`, `browser.py` `self_check` |
| Secrets | `MEET_BOT_EMAIL` / `MEET_BOT_PASSWORD` are `SecretStr`: repr, logs and `/api/status` show `**********`. Missing auth raises `MissingSetting("… MEET_PROFILE_DIR … MEET_BOT_EMAIL / MEET_BOT_PASSWORD …")` — names, never values. The profile directory is the credential and is `.gitignore`d. | `settings.py` |

Structure, settings style, logging (`structlog`), the wire module, turns, STT and TTS
mirror `packages/ears-discord` file for file; the brain's REST store routes exist with
the same camelCase output.

## 3. What works (tested, deterministic, no network, no Google account)

`cd packages/ears-meet && just check` — ruff, pyright, and 91 pytest tests, with the
browser and PulseAudio faked at the `Surface` / `Player` seams and a fake clock:

- **frame mapping** — Meet ids in `discordId`, `at` + `atMs` stamping, camelCase, brain
  command parsing (`tests/test_frames.py`);
- **speaking-indicator debounce** — delayed start, blink suppression, delayed end, gap
  preservation, independent speakers, `forget`/`close_all` (`tests/test_speaking.py`);
- **turn logic** — one turn across short pauses, gap closure, ticks, previous speaker,
  crosstalk (`tests/test_turns.py`);
- roster diffing, caption mining, STT attribution, agenda re-binding (`tests/test_pure.py`);
- the composition root end to end: join → `session.started` + `ready`, participants,
  speaking → turns, chair exclusion, captions vs STT, playback queue / streaming /
  interruption / quiet gate, **egress verdict in `spoken.error`**, session lifecycle,
  stage failure is non-fatal, self-check failure is loud and named, credentials never
  appear in repr or status (`tests/test_app.py`);
- the wire: hello frames, live fan-out, brain commands, `/health`, `/api/status`,
  `/api/selfcheck`, sessions, memories, interventions, LLM usage (`tests/test_wire.py`);
- the selectors module invariants and `observer.js` wiring against a mocked Playwright
  page (`tests/test_browser.py`);
- **contract conformance** (`tests/conformance/`), see next section.

## 4. The conformance test — the seam is real

`tests/conformance/test_conformance.py` takes each Discord recording in
`packages/contract/fixtures` (`replay.jsonl`, `replay.offagenda.jsonl`), re-enacts the
same meeting as the DOM events a Meet tab would have produced — tiles appear, indicators
flip at the recorded milliseconds, caption lines are edited and settle — drives that
through the real composition root, and records what ears-meet puts on the wire into
`tests/conformance/fixtures/meet.*.jsonl` (committed; Meet ids, `session.started` with
the agenda re-bound to those ids, turns, captions — a reviewer can read them).

Then both recordings go through **the brain's own replay harness**
(`packages/brain/src/replay.ts`, `--stub-llm`, fake clock) and the decision record —
every line the chair said and at what second, per-person talk time, what was parked —
must be byte-identical. It is, for both scenarios:

```
— what the chair said —
00:00  startMeeting  Welcome, everyone. Our agenda is …  Ana, please start us off.
00:50  silence       Vitaly, you've been suspiciously quiet on Where we actually are. …
01:48  topicOverrun  Where we actually are just got a red card for overtime. …
02:41  offAgenda     Vitaly, I've bagged honestly pricing page need full redesign; …
02:59  escalateFirm  Vitaly, cutting in — The date filed a missing-persons report. …
04:12  topicOverrun  The clock beat The date. Say hello to Blocker owners. …
05:03  silence       Vitaly, is that you on mute or just enjoying the quiet? …
06:00  wrapUp        That's a wrap, team — …
— talk time (s) —
Vitaly 100 · Ana 104 · Marc 72
```

A third assertion checks frame-for-frame that every `speaking.start`/`end` and every
final `transcript` Discord emitted, Meet emits for the same person at the same
millisecond. The one visible difference between the surfaces: Meet captions keep every
word, so where Discord's STT sent an interim and then a differently-worded final, Meet
also finalises the interim text. The brain ignores interims for decisions and the
decisions match anyway; the test allows exactly those extras and nothing else.

The brain half of the test needs `packages/brain/node_modules` (`pnpm install` there);
without it that assertion skips with a message and the recording assertions still run.
`packages/brain` is not modified.

## 5. Not yet proven / stubbed — read before trusting it in a demo

1. **No live Meet run has happened.** Every selector is `documented …` or `unverified`;
   none is `seen …`. The first `just live-check` promotes or demotes them. The obfuscated
   class names (`div.IisKdb`, `SPEAKING_CLASSES`) are the ones most likely to be stale;
   the `aria-label` / `data-participant-id` hooks are the ones expected to hold.
2. **Egress is proven only by construction.** The two checks above are implemented and
   unit-tested, but nobody has yet heard the tone in a real call. `live-check` asks.
3. **Scripted Google sign-in is best-effort.** Expect it to fail on a fresh account with
   a challenge; use the profile.
4. **No Postgres/Redis.** The brain's store routes (`/api/memories`, `/api/interventions`,
   `/api/llm-calls`, `/api/sessions/*/usage`) answer from memory and forget on restart.
   ears-discord's Alembic schema could be shared later; for a demo the brain does not
   notice.
5. **Operator console pages** (`/console`, the watch page) are not served; the `/live`
   socket and the REST routes are, so ears-discord's console could be pointed at it.
   `mute` / `unmute` from the brain answer `moderation … failed`: Meet gives a
   participant no control over others' microphones (ears-discord does the same without
   Mute Members).
6. **Meet's speaking indicator is Meet's VAD**, so `speaking.*` timing has Meet's own
   hold-off (~200–500 ms) baked in before our debounce. Fine for talk time; measure
   before tuning `SPEAKING_*_MS`.
7. **Camera stays off.** The stage share is the face.
8. **Dockerfile builds on the Playwright base image** (`mcr.microsoft.com/playwright/python:v1.63.0-noble`
   + xvfb + pulseaudio); it has been written, not yet built in CI.

### Stage share — status split in two, measured 2026-09-21

The seam has a Chromium half and a Meet half, and they are not equally proven. Item 1
above covers the Meet half only; the Chromium half was measured on a box with Xvfb:

| half | status | evidence |
|---|---|---|
| Chromium picks the `gavel-stage` tab with no picker | **VERIFIED** | Real headful Chromium on Xvfb, these exact launch args, a page titled `gavel-stage`, `getDisplayMedia({video:{displaySurface:'browser'}})` from a second page → succeeds, no picker; track `web-contents-media-stream://…`, `displaySurface: "browser"`, 1280×720 @ 30 fps, the `gavel-stage` tab selected. |
| Entire-screen capture as a fallback | **DOES NOT WORK** | Same box, `getDisplayMedia({video:true})` with `--auto-select-desktop-capture-source=Screen 1` → `NotReadableError: Could not start video source`, every time. Desktop capture does not start on a virtual display. Hence the flag is absent and `A tab` is load-bearing. |
| Meet's "Present now" button and its "A tab" menu item are where `PRESENT_BUTTON` / `PRESENT_TAB_MENU_ITEM` say | **unverified** until a live call | If Meet ever falls back to "Entire screen" here, capture fails outright rather than degrading — which is why the tab item is a required selector whenever a stage is configured, and why the failure log spells that out. |

### Contract frames — nothing missing, one remark

No frame is missing for Meet; nothing was added. One honest remark for the contract
owner rather than a change: `transcript` on Meet is *attributed by name* (captions) or
*by overlap* (STT on mixed audio), so `discordId` on a transcript is a best guess in
crosstalk and may be `meet:unattributed`. The frame has no field for that confidence;
`confidence` (additive, already in the frame model) is left `null` rather than invented.

## 6. Running it live — what a human must do

### Host requirements

Linux. `Xvfb`, `pulseaudio` (+ `pulseaudio-utils` for `pactl`/`parec`/`pacat`), `ffmpeg`,
Python 3.13, `uv`. On Debian/Ubuntu:

```
sudo apt-get install -y xvfb pulseaudio pulseaudio-utils ffmpeg
cd packages/ears-meet && just setup        # uv sync + playwright install chromium
```

Do not run as root: Chromium needs `--no-sandbox` and PulseAudio needs `--system` there;
the Dockerfile runs as `pwuser` for the same reason.

### 1. Make the signed-in profile (once, on a machine with a screen)

```
MEET_PROFILE_DIR=~/gavel-meet-profile just login
```

A visible Chromium opens on the Google sign-in page. Sign in as the bot's Google account
(2-step included), press Enter; the script confirms the account shows on meet.google.com.
Copy the directory to the machine that runs ears-meet. **It is the credential**: never
commit it, never bake it into an image. Google may still ask for re-verification after a
long gap — re-run `just login`.

### 2. Settings (`.env` at the repo root, never committed)

```
MEET_URL=https://meet.google.com/xxx-yyyy-zzz
MEET_PROFILE_DIR=/absolute/path/to/gavel-meet-profile
MEET_BOT_NAME=Karen (gavel)
STAGE_URL=http://127.0.0.1:<stage port> # optional; packages/stage's page, title `gavel-stage`
SLNG_API_KEY=…                         # optional; captions work without it
AGENDA_FILE=packages/contract/fixtures/agenda.demo.json
FRAMES_FILE=recordings/live.jsonl      # optional; every emitted frame, for the fixture
```

Fallback only: `MEET_BOT_EMAIL`, `MEET_BOT_PASSWORD`. Values are never logged.

### 3. Check it, with a second human in the call

```
just live-check --launch --duration 180 --speak-after 20
```

This starts `python -m ears_meet`, admits itself to the wire as a stand-in brain, prints
every frame, sends one `speak` (a 440 Hz tone) after 20 s, and ends with a scorecard:
people seen, who produced `speaking.start`, who produced attributed transcripts, whether
the `spoken` frame carried an egress error, and the selector self-check. Meanwhile the
human in the call: admit the bot from the lobby if it asks, talk (watch for your
`speaking.start` within ~200 ms and `speaking.end` ~400 ms after you stop), confirm you
**heard the tone**. If you did not hear it and `spoken` has no `error`, that is a bug —
file it with the scorecard. Then annotate `selectors.py` (`seen 2026-09`) and commit that.

### 4. Run it for real

```
just run                                   # ears-meet on ws://127.0.0.1:8787
cd ../brain && pnpm dev                    # brain, pointed at the same wire
```

Only one `ears` may own port 8787: stop the Discord `ears` service first.

### Docker

```
docker build -f packages/ears-meet/Dockerfile -t gavel-ears-meet:local .
```

`compose.yaml` carries `stage` as a regular service and `ears-meet` under the **`meet`
profile**. `ears-meet` mounts `MEET_PROFILE_HOST_DIR` read-write at `/profile` (it must
be writable by the image's `pwuser`, uid 1001), needs `shm_size: 2gb` for Chromium,
shares `http://stage:8793`, and publishes its wire on loopback
`MEET_WIRE_PORT` (default 8797) because the Discord `ears` still holds 8787. The brain
is pointed at it with `EARS_WIRE_URL=ws://ears-meet:8787` / `EARS_HTTP_URL=http://ears-meet:8787`
in `.env`; left at the default it listens to the Discord ears and hears nothing.

### Demo day: two scripts, nothing to remember

```
scripts/demo-preflight.sh          # PASS/FAIL table, exit 1 on any FAIL, changes nothing
scripts/demo-up.sh [--build]       # preflight, `--profile meet up -d`, wait for health, print URLs
scripts/demo-up.sh --down          # tear it down (named volumes kept)
```

Preflight checks: docker + compose, `--profile meet config` validates, every image the
profile builds exists, `MEET_URL` is set, `MEET_PROFILE_HOST_DIR` exists, is non-empty
and is writable by the container, `MEET_FACE_IMAGE` is a real file under `assets/persona/`, every published host
port is free (or already held by this stack), `EARS_WIRE_URL` points the brain at
`ears-meet`, and the external Traefik network exists. Settings are checked for
**presence only** — no value is ever printed and `.env` is never read directly; the
checks go through `docker compose config`, the same interpolation `up` uses.

`demo-up.sh` waits (default 180 s, `--timeout N`) for every service to be `healthy`
(or, for the migrations, exited 0). Any service that fails or times out gets its last
50 log lines dumped and the script exits 1 with the stack left up for inspection. Both
scripts are safe to run twice.

## 7. When Meet changes

The symptom is `selfcheck.failed missing=[call.speaking_indicator]` at join (fatal) or,
for optional selectors, `selfcheck.optional_missing` in the log and `/api/selfcheck`.
Open the call in a desktop Chrome, inspect the element, add the new candidate to the
*front* of the list in `selectors.py` with a `seen YYYY-MM` comment, leave the old one
behind it, run `just check`. Nothing else in the package knows a Meet selector —
`observer.js` receives them as config.
