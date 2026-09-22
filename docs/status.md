# gavel — where the build stands

*22 September 2026 · status of the application, not the hackathon board*

> The brain and the Discord route run. **Google Meet is written and green on tests but has
> never joined a real call.** Three things you can test today; one thing blocks a real Meet
> test, and it needs a second person.

## 1 · The scaffolding

| Piece | What it is | State | Deployable? |
|---|---|---|---|
| `brain` | Decides everything. Agenda, turns, timing. Imports no call SDK. | 🟢 Works | Yes — in compose |
| `ears-discord` | Discord call connection. Decides nothing. | 🟢 Works | Yes — in compose as `ears` |
| `calendar` | Scheduling / booking service. | 🟢 Works | Yes — in compose |
| `ears-meet` | Google Meet connection. Chromium + Playwright + PulseAudio. | 🟡 Built, unproven | **No** — no compose service |
| `stage` | Karen's live board. She screen-shares it; no separate page to visit. | 🟡 Demo mode only | **No** — no compose service |
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

### Right now, no setup

- **The brain on a recorded meeting** — `pnpm replay`, feed it a transcript, watch it run the agenda.
- **Karen's board, every state** — `/?demo=1&scene=open`; scenes for crowd, gathering, idle, open,
  untimed, finished.
- **The plugin, against a mock** — `pnpm mock`, the whole compose flow with no Google account attached.

Caveat: needs a machine with `pnpm`. This VPS does not have it — the box gavel lives on can't
build the two front-end pieces right now.

### ~30 minutes of setup, and a second person

**A real Google Meet call.** Three things stand in the way, all human:

- A signed-in Chromium profile — made once, *on a machine with a screen* (not this VPS).
- A Linux host with Xvfb, PulseAudio and ffmpeg. This box has ffmpeg and Xvfb; PulseAudio is
  untested here.
- **A second human in the call.** Meet won't behave with one participant.

```
just login                 # once, on a laptop — signs the profile in
just live-check --launch --duration 180 --speak-after 20
```

### Not testable as a deployment

Neither `ears-meet` nor `stage` has a service block in `compose.yaml`. They run from a terminal,
by hand. Nothing stands up the Meet route as a service yet — and this was never wired, it isn't
something the merges broke.

## 4 · What needs you

| Item | Why it's stuck | Who |
|---|---|---|
| First real Meet call | Needs a signed-in profile made on a screen + a second participant | **You** |
| Compose blocks for `ears-meet` + `stage` | Just not written yet — half a day | helm |
| Norma's findings | ~230 findings sit behind a login I don't have. 7 real ones fixed; 10 visible ones judged noise | **You** (login) |
| Two Devin sessions | Suspended mid-flight — close them or resume | **You** |
| Plugin store listing | Chrome Web Store / Workspace Marketplace need a publisher account | **You** |

---

gavel · `bioztar/gavel` (public). Architecture for Artem: `docs/blueprint.html`.
Demo-prep board: `docs/index.html` — different thing, don't read it as build status.
