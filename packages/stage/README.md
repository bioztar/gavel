# stage — the screen Karen shares

The live meeting board Karen presents from her own participant tile: the agenda with its
budgets, who has had how much of the floor, who is speaking, the clock, her last line,
and the decisions, open items and parking lot as they build up. Everyone in the call sees
it without leaving the meeting. Design notes and the brain-state assumptions are in
[../../docs/STAGE.md](../../docs/STAGE.md).

**`document.title` is `gavel-stage`** — ears-meet picks the tab to present by that exact
string. Do not change it, do not append to it.

## Run it

```bash
pnpm install           # dev tooling only (vitest, jsdom, tsc); the server has no dependencies
pnpm start             # http://127.0.0.1:8793/  ← reads brain at http://127.0.0.1:8788/state
pnpm dev               # same, restarts on change
pnpm test              # reducer, truncation, the page (jsdom), the SSE server
pnpm typecheck         # strict TS over src/, test/ and the browser JS in public/
```

Open `http://127.0.0.1:8793/?demo=1` for the whole board from a fixture with moving data —
no brain, no meeting. Scenes: `&scene=crowd` (12 people, a 40-character name, 9 topics),
`gathering`, `idle`, `finished`, `open` (empty agenda), `untimed`; `&t=60` starts the
clock a minute in (`&t=1400` puts the meeting over budget); `&owners=0` / `&owners=some`
show the agenda with no or only some topic owners; `&link=down` shows the reconnecting marker.

`pnpm test` includes `test/layout.test.ts`, which drives a real headless Chrome (found via
`CHROME_BIN`, `PATH`, or Playwright's cache) through every demo scene at 1280×720 and
1920×1080 and fails if any text box is painted partially clipped. On a machine with no
Chrome set `STAGE_NO_CHROME=1` to skip it; the skip is printed, never silent.

Env (names only; nothing here is a secret):

| setting           | default                          |                                        |
| ----------------- | -------------------------------- | -------------------------------------- |
| `HOST` / `PORT`   | `127.0.0.1` / `8793`             | where the screen is served             |
| `BRAIN_STATE_URL` | `http://127.0.0.1:8788/state`    | brain's state endpoint, polled server-side |
| `BRAIN_POLL_MS`   | `750`                            | how often; only changes are pushed     |

## Routes

| route         |                                                                     |
| ------------- | ------------------------------------------------------------------- |
| `GET /`       | the screen                                                          |
| `GET /events` | SSE: `state` events (brain's whole view), `link` events (brain up/down), a comment ping every 15 s |
| `GET /state`  | the last state seen from brain (503 before the first)               |
| `GET /health` | `{ ok, brain, clients, stateAgeMs }`                                |

## Shape

```
public/stage.html   markup + CSS, sized in 1/100ths of a 16:9 stage — identical at 720p and 1080p
public/board.js     pure: brain state → board view model, every cap and truncation rule
public/render.js    board → DOM; keyed rows so bars animate, text rewritten only on change
public/app.js       one EventSource, a Link record, a paint 4× a second
public/demo.js      the ?demo=1 fixture, shaped like brain's GET /state
src/server.ts       static files + SSE fan-out + the brain poller
```

The browser never talks to brain and never polls: the server polls brain once for all
tabs and pushes over SSE. If the stream drops, `EventSource` reconnects itself and the last
board stays up with a quiet "reconnecting" marker; if brain is down, the last state stays
up with "brain unreachable"; before the first state there is a calm holding screen. Nothing
is fetched from anywhere but this origin — no CDN, no webfont, no build step.
