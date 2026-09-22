# Cloture — where the build stands

*Cloture — the motion that cuts off debate. 22 September 2026 · status of the application, not
the hackathon board*

> The brain and the Discord route run. **Google Meet is written and green on tests but has
> never joined a real call.** Three things you can test today; one thing blocks a real Meet
> test, and it needs a second person.

## 1 · The scaffolding

| Piece | What it is | State | Deployable? |
|---|---|---|---|
| `brain` | Decides everything. Agenda, turns, timing. Imports no call SDK. | 🟢 Works | In compose — not running anywhere now |
| `ears-discord` | Discord call connection. Decides nothing. | 🟢 Works | In compose as `ears` — not running now |
| `calendar` | Scheduling / booking service. | 🟢 Works | In compose — not running anywhere now |
| `ears-meet` | Google Meet connection. Chromium + Playwright + PulseAudio. | 🟡 Built, unproven | In compose today (`19fde09`) — behind `docker compose --profile meet up -d ears-meet` |
| `stage` | Karen's live board. She screen-shares it; no separate page to visit. | 🟡 Demo mode only | In compose today (`19fde09`) — not running anywhere now |
| `extension` | `/compose` as a browser plugin. Signs into the real account. | 🟡 Builds, unpublished | No store listing yet |
| `contract` | The frozen seam: WebSocket JSON frames + fixtures. | 🟢 Frozen | n/a — shared spec |
| `concierge` | Bot that interviews the host and writes the agenda. | ⚪ Parked | Deliberately not built |
| `chair-video` | Generated video avatar. | ⚪ Cut | Removed — replaced by a still |

Nothing generates video anywhere. Karen's face is one static image published as a real camera
track; her "visual" is the shared board.

## 2 · Google Meet — built vs. proven

| Capability | Built | Proven |
|---|---|---|
| Join a Meet as a named guest | 🟢 Yes | 🟡 Harness only |
| Hear the room (tab audio → speech-to-text) | 🟢 Yes | 🟡 Faked audio |
| Know who is talking (per-tile indicator) | 🟢 Yes | 🟡 Faked DOM |
| Speak into the room (virtual mic) | 🟢 Yes | 🟡 Faked audio |
| Show a face (still as camera track) | 🟢 Yes | 🟢 Real Chromium, pixel-verified |
| Share the board as a screen | 🟢 Yes | 🟡 Tab capture, not in a call |
| Run in a real Google Meet call | 🟢 Yes | 🔴 **Never done** |

93 tests pass. Every one of them runs against a faked Meet — no Google account, no network.
That is a real result and it is not the same as working.

## 3 · What you can test today

### On your laptop — no Google account needed

Each one wants `pnpm install` in that package first. The VPS gavel lives on has no `pnpm`, so
these are laptop-only today.

- **Karen's board, every state** — `cd packages/stage && pnpm install && pnpm start`, then
  `http://127.0.0.1:8793/?demo=1&scene=open`; also `crowd`, `gathering`, `idle`, `untimed`, `finished`.
- **The brain on a recorded meeting** — `cd packages/brain && pnpm replay`, feed it a transcript,
  watch it run the agenda.
- **The plugin, against a mock** — `cd packages/extension && pnpm mock`, the whole compose flow with
  no Google account attached.

### With setup — and a second person

**A real Google Meet call.** Four steps, in order — steps 1 and 2 are yours:

- **Host packages** — `sudo apt-get install -y xvfb pulseaudio pulseaudio-utils ffmpeg`. This VPS has
  ffmpeg and Xvfb but **no PulseAudio and no sudo**, so the live run happens on a box where you are
  root, not here.
- **A signed-in Chromium profile** — made once, on a machine with a screen. The profile *is* the
  credential: never committed, never baked into an image.
- **A second human in the call.** Meet won't behave with one participant.

```
cd packages/ears-meet && just setup       # uv sync + playwright chromium

MEET_PROFILE_DIR=~/gavel-meet-profile just login    # on a laptop, once

# .env at repo root — MEET_URL, MEET_PROFILE_DIR, MEET_BOT_NAME
#   optional: STAGE_URL, SLNG_API_KEY, AGENDA_FILE

just live-check --launch --duration 180 --speak-after 20
```

### Not yet proven as a deployment

`ears-meet` and `stage` picked up real service blocks in `compose.yaml` today (`19fde09`) —
`docker compose --profile meet up -d` is a real command now, not an aspiration. Nobody has run
it against a signed-in account yet, which is exactly what section 4 below needs from you.
On the day: `scripts/demo-preflight.sh` says whether the box is ready (images, settings
present, ports, the still, the brain pointed at the right ears) and `scripts/demo-up.sh`
brings the profile up, waits for health and prints where the board and console are —
see [EARS-MEET.md § Demo day](EARS-MEET.md#demo-day-two-scripts-nothing-to-remember).

## 4 · What needs you

| Item | Why it's stuck | Who |
|---|---|---|
| First real Meet call | A root-capable Linux box, a profile signed in on a screen, and a second participant | **You** |
| Norma's findings | ~230 findings sit behind a login I don't have. 7 real ones fixed; 10 visible ones judged noise | **You** (login) |
| Two Devin sessions | Suspended mid-flight — close them or resume | **You** |
| Plugin store listing | Chrome Web Store / Workspace Marketplace need a publisher account | **You** |

---

Cloture · `bioztar/gavel` (public). Architecture for Artem: `docs/blueprint.html`.
Demo-prep board: `docs/index.html` — different thing, don't read it as build status.
