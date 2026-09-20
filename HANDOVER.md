# HANDOVER — gavel — 2026-09-20 11:15

## State: demo path live and proven; a complete synthetic first-pass submission video is built (6:45) and waiting for Vitaly to watch. The meeting room (`/m/{id}`) is new since that video was cut — it is not in it.

## Done this session (helm, on the Mac)
- Repo cloned to `/Users/alex/DEV/gavel` (the dir held a stray `private.key` and no git —
  key moved to `/Users/alex/DEV/_assets/gavel-secrets/private.key`, outside every repo).
- `.env` copied from the VPS samba share `/Volumes/dev/gavel/.env`, mode 600, gitignored.
- **`docs/recording-checklist.md`** — per-take shot list for the real recording: file names,
  clap sync, take 0 voice-clone sample, pre-flight from `demo-script.md` §1.
- **`scripts/video/`** — full synthetic video pipeline, see its README. Produces
  `/Users/alex/DEV/_assets/gavel-video/gavel-v1.mp4`, 6:45, 1920x1080.
  - Vitaly's voice = minimax clone `Voicedc785cd01789891341`, cloned from a 2-minute solo
    superwhisper recording. Artem = ElevenLabs "Brian". Karen = the product's own SLNG voice.
  - Screens are real: the gate and confirm pages were captured by driving the **live**
    `/compose` on gavel.pro7ocol.com headless. `/compose/send` was never called; the invite
    email was rendered locally through `render_invite_html`.
  - Karen's four interventions are real `veed/lipsync/v2` renders over `idle-formal.mp4`.
  - Trimmed to the 7:00 ceiling using demo-script §3's own cut lines plus `atempo=1.06`.

## In flight / next
1. Vitaly watches `gavel-v1.mp4` and calls what to change.
2. He re-records for real against `docs/recording-checklist.md`; `assemble.py`'s `SHOT_MAP`
   is where footage replaces the stand-ins.
3. Five frames carry an orange **PLACEHOLDER SHOT** badge — Discord call (×3), calendar
   accept, ears console. Those are the only shots with no real capture behind them.
4. The room board is a candidate for the placeholder shots and for the screen-share beat —
   it is the only surface that shows the meeting happening without the ears console.

## Done this session (11:15) — the meeting room
- **The meeting room — one link, before / during / after.** `GET /m/{id}` is no longer a
  join page; it is the meeting's public face, **built to be screen-shared**. The organizer
  opens it and shares the tab, so it is also the answer to "Discord blocks bot video":
  chair-video's `/stage/` is embedded as Karen's face.
  `packages/calendar/src/gavel_calendar/room.py`, 7 new tests.
- **It is a board, not a document.** One screen, no scrollbar, type sized in `vh` so it
  scales to whatever it is shared on; light on white because a projector has no black.
  Before: the face, the agenda, who is expected (missing people marked). During: the topic
  clock against its budget, one line for who has the floor, what the chair has understood
  on this topic, the agenda, and decided / still open / parked. After: the picture drops
  and the record takes the screen.
- **Two things are deliberately off the board.** Nothing Karen *says* — the room can hear
  her, and her lines printed beside a live meeting pull eyes off whoever is talking — and
  the per-person talk-time meter, which is what the chair acts on rather than what the
  room reads mid-sentence. Both are in the **Detail view** in the ⋯ menu (remembered per
  browser), along with **Join the call** (the Discord voice channel, never hidden — people
  arrive late), **Copy this link**, and, before the meeting, **Start the meeting now**.
- **chair-video fix:** the stage's "Click to start the chair" overlay shipped visible and
  was only ever hidden *by* a click, so it sat over Karen's face in the embed. It now
  starts hidden and `entry.mjs` reveals it only if autoplay is refused — which is what its
  own comment always said it was for. `static/index.html` only; no bundle rebuild.
- **ears console has a light theme.** Follows the OS, and the header's light/dark button
  overrides it, remembered per browser, applied before first paint. For when the console
  is on a projector next to the room page.
- `GET /m/{id}/state` is what the page polls (2 s). It reads the brain's `/state`
  server-side, so the browser never needs the brain's address and the console's auth is
  untouched. Two rules: a state whose `sessionId` isn't this record's is **never** shown
  under this link (one brain, one session), and every live poll **banks** the snapshot on
  the invite record — the brain forgets a session when the next starts, and the report has
  to outlive it. Unreachable brain = the banked report or the agenda, never an error page.
- Env: `BRAIN_STATE_URL` (hard-coded to `http://brain:8788/state` in compose, like ears'
  and stream-vonage's copies) and `CHAIR_VIDEO_STAGE_URL` (default `/stage/`, relative so
  it needs no domain).

## Done earlier this session
- **Agenda gate.** A thin brief comes back as a refusal page — headline, one textarea,
  one button. No topic grid, no send path. `render_gate_html` in `compose.py`.
  `_rows_from_lines` is the insurance: if a typed agenda still parses to nothing, it
  splits on newlines/`;` so the headline demo beat cannot dead-end.
- **Enforcement gauge** (low/medium/high) on the confirm page. Levels live in
  `schema.py:ENFORCEMENT_LEVELS`, merged *over* `settings.policy_overrides` — env
  carries deployment facts, the gauge carries this meeting's intent. Pinned by
  `test_enforcement_gauge_reaches_the_agenda_policy`.
- **Karen can never mute Vitaly.** `policy.yaml` has `neverMuteRoles: [host]`, the
  organizer always gets `role: host`, and mute only fires via `escalate`. The visible
  delta at High is the hard handover threshold meeting the soft one (both 30s), so the
  first handover cuts in instead of waiting for a pause — not the mute. Demo script says this out loud.
- **UI rebuilt light** — near-white ground, system font stack, hairline tables, pill
  buttons, segmented control, mobile breakpoint. Invite email matches the palette;
  its table skeleton is untouched so mail clients still render it.
- **Parser fix**: the brief opens "Karen, set up…" and she was being parsed in as an
  attendee/owner. `llm.py` prompt now states the first known attendee is the dictator
  ("me" = them) and the chair is never a participant. Owners now Artem/Vitaly/Vitaly.
- Demo script (md + html) and the architecture roadmap slide updated — gate at 0:28,
  gauge at 1:22, company-wide enterprise rules on the roadmap.

## Proven live (not just locally)
- Gate page: `200`, `name="agenda"` ×1, `topic_title_0` ×0, `/compose/send` ×0.
- Gate cleared: `200`, `name="enforcement"` ×3, topics parsed, "Send the invite".
- One **real** invite emailed to `vitaly@pro7ocol.com` at `enforcement=high` → `200`.
- `uv run pytest -q` → exit 0, 91 tests. `uv run ruff check .` → clean.

## Known, not bugs
- After `docker compose up -d --build calendar`, Traefik serves `404` for a few
  seconds while it re-resolves the new container. It clears itself. Do not go
  hunting for a routing misconfiguration — `curl` the route again.
- **Redeploying `calendar` drops every pending invite.** `store.py` is in-memory on purpose,
  so a rebuild or `restart` of that container makes live `/m/{id}` links 404 and empties
  `/board`. Send the demo invite *after* the last calendar deploy, not before.

## Next steps (ordered)
1. Rehearse the demo against the live site, script in hand.
2. `/compose`, `/architecture`, `/demo-script` are publicly unauthenticated — Vitaly's
   call whether that stands through the hackathon.
3. After the hackathon: `scripts/set-console-auth.sh --off`, rotate `VONAGE_API_KEY`,
   and decide on the two loose secret copies (`/home/coder/vonage_private.key`,
   `/home/coder/DEV/gavel/.env.bak`). `.env.example` still does not mention `--off`.
4. Back-burner, unbuilt: infer invitees with the LLM instead of the three hard-coded
   addresses.

## Blockers / needs human
- Submission target (URL, length cap, upload vs link) is still unknown — not in the repo.
- Artem's availability for the live floor-handover beat, if the real recording happens.

## Key files touched
- `scripts/video/*` — the pipeline (script.json is the spine; assemble.py is the cut)
- `docs/recording-checklist.md` — how to shoot the real one
- `/Users/alex/DEV/_assets/gavel-video/` — all media (audio, shots, karen, out, final mp4)
