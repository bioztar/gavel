# STAGE — the screen Karen shares

`packages/stage` serves the live meeting board Karen presents into the call from her own
participant tile. It replaces the generated talking-head projector page: nobody navigates
anywhere, everyone in the meeting sees the same thing, and the time-governance claim is
visible in the room while it happens.

It is a **video of a page**. Nobody can click it, it is compressed to roughly 720p, and it
is often a thumbnail on someone's laptop. Every design decision below follows from that.

## What is on it

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ MEETING TITLE · purpose              Time left 12:30   This topic 8:35 / 8:00 │
│ (banner: over budget / gathering / open discussion / finished — when needed) │
├───────────────────────────────┬──────────────────────────────────────────────┤
│ WHO HAS THE FLOOR   speaking: │ AGENDA                                       │
│ ████████████████████ 61% Vit… │ ✓ Welcome & goals                    2:00    │
│ ██████ 18% Priya              │ ▶ Launch date & scope       Marc     8:35/8:00│
│ ████ 12% Marc         ●       │ · Pricing tiers             Priya    10:00   │
│ ██ 6% Sofia                   │ · Launch-day comms          Dana      5:00   │
│ █ 3% Dana                     │ · Anything else                       5:00   │
│                               ├──────────────────────────────────────────────┤
│                               │ DECISIONS   │ OPEN ITEMS   │ PARKING LOT     │
│                               │ • …         │ • …          │ • …             │
├───────────────────────────────┴──────────────────────────────────────────────┤
│ KAREN  “We're over on the date. Marc, name a date you can defend.”           │
└──────────────────────────────────────────────────────────────────────────────┘
```

- **Talk time** is the headline: one bar per attendee, share of the floor across the whole
  meeting, loudest first, the speaker marked. Anyone above brain's `floorShareThreshold`
  (default 60 %) — on the meeting or on brain's rolling window — turns red. The bar is what
  moves; the number is large but secondary, because compression eats small moving digits.
- **Agenda**: every topic with its budget; done ✓, live ▶ with `elapsed / budget`, not yet
  reached ·. Over budget flips the live row, the topic clock and a banner to red, and the
  clock keeps counting up. Owners are shown when brain publishes them (see assumptions).
- **Clocks**: `This topic elapsed / budget`, and `Time left` — what remains of this topic's
  budget plus the budgets not yet reached. Both tick locally between updates.
- **Karen's last line**, verbatim, from the newest intervention with a `line`.
- **Decisions, open items, parking lot** — the newest four of each.

## Never scrolls, never overflows

The whole board is laid out in hundredths of a 16:9 stage (`--u = min(1vw, 100vh/56.25)`),
so 1280×720 and 1920×1080 are the *same* picture, scaled; anything else letterboxes. Every
region is a fixed grid track with `overflow: hidden`, and every list is capped **in the
reducer**, where it is unit-tested, not in CSS:

| what                | shown                       | when there is more                   |
| ------------------- | --------------------------- | ------------------------------------ |
| attendees           | 8 (the speaker always among them) | one grey `+N more` row with their share |
| topics              | 7, centred on the live one  | `N done` / `N more` rows at the ends |
| notes per column    | 4, the newest               | `+N` on the column header            |
| name                | 18 chars                    | word boundary if close, else mid-word, `…` |
| topic title         | 44 chars                    | same                                 |
| note                | 72 chars                    | same                                 |
| Karen's line        | 200 chars                   | same (brain caps at 320)             |

Smallest text on the board is 1.5 units = **19.2 px at 720p**, 28.8 px at 1080p. Percentages
are 2.5–4.6 units, the clocks 2.5, the speaker's name 2.5. Dark background, three colours
that survive compression: white, one accent (live), red (over / hog).

## Live updates

The browser opens **one `EventSource("/events")`** and nothing else — no polling, no
WebSocket, no fetch. The server polls brain's `GET /state` (the same source the ears-discord
console reads through its `/api/brain-state` bridge) every 750 ms and pushes only when the
JSON changed:

```
retry: 1000

event: state
id: 1718000000000
data: {"at":1718000000000,"brain":true,"state":{ …brain's whole view… }}

event: link
id: 1718000004000
data: {"at":1718000004000,"brain":false}

: ping 1718000015000
```

Failure modes, in the order they were designed for:

| situation                        | what the room sees                                                |
| -------------------------------- | ----------------------------------------------------------------- |
| tab opened before any state      | calm holding screen: "gavel · Connecting to the meeting…"        |
| late join                        | the current state in the very first SSE frame                    |
| stream drops                     | last board stays; small grey "reconnecting · last update 0:41 ago"; `EventSource` reconnects itself |
| brain unreachable                | last board stays; "brain unreachable · showing 0:12 ago"; server keeps the last state and sends `link` |
| brain up, meeting idle           | title + agenda, "No meeting running."                             |
| gathering                        | who is here; "Waiting for Dana, Marc" or "Everyone is here…"      |
| no agenda                        | floor board only, "Open discussion — no agenda."                  |
| untimed meeting                  | agenda without budgets, clocks hidden                             |
| finished                         | final shares and the notes, "Agenda complete. Thank you."         |

Nothing is loaded from anywhere but the stage's own origin: no CDN, no webfont, no
serve-time build. The server has zero runtime dependencies (`node src/server.ts`).

## `document.title`

`gavel-stage`, exactly. ears-meet selects the tab to present by this string. `render.js`
never touches the title; `test/page.test.ts` asserts it before and after a paint.

## Demo mode

`/?demo=1` renders the whole board from `public/demo.js` — a fixture shaped like brain's
view, with clocks and talk time moving in real time and a scripted over-budget moment:

| query                | scene                                                     |
| -------------------- | --------------------------------------------------------- |
| `?demo=1`            | five people, five topics, Vitaly at ~60 %, topic 2 over budget |
| `&scene=crowd`       | 12 attendees, a 40-character name, 9 topics — the truncation case |
| `&scene=gathering`   | lobby, two people missing                                 |
| `&scene=idle`        | agenda loaded, nothing running                            |
| `&scene=open`        | empty agenda                                              |
| `&scene=untimed`     | no budgets                                                |
| `&scene=finished`    | the closing board                                         |
| `&t=300`             | start five minutes in                                     |
| `&link=down`         | the reconnecting marker                                   |

## Running it

```bash
cd packages/stage
pnpm install && pnpm test && pnpm typecheck
pnpm start                       # http://127.0.0.1:8793/
BRAIN_STATE_URL=http://brain:8788/state PORT=8793 HOST=0.0.0.0 pnpm start
```

Settings (names only): `HOST`, `PORT`, `BRAIN_STATE_URL`, `BRAIN_POLL_MS`. None are secrets.

In compose it is a service like the others (block in the PR that introduced it); ears-meet's
bot browser opens `http://stage:8793/` and shares that tab. The service does not need
Traefik — nobody outside the call should open it — so bind it to `127.0.0.1` only.

## Assumptions about brain's state

The stage reads `engine.view()` as published on `GET /state` and treats **every field as
optional** — a sparse or empty object still renders the holding screen, not an error.
What it relies on, and what it does when a field is missing:

| field                                   | used for                          | if absent                     |
| --------------------------------------- | --------------------------------- | ----------------------------- |
| `phase`                                 | idle / gathering / active / finished layouts | treated as `idle`   |
| `title`, `purpose`, `chairName`, `persona.displayName` | header, Karen's name | "Meeting", "Karen"    |
| `people[].{id,name,totalSeconds,speaking}` | the floor board                | "Nobody has spoken yet"     |
| `people[].windowSeconds`                | rolling-window hog detection      | whole-meeting share only      |
| `topics[].{id,title,budgetSeconds,done}` | agenda; `budgetSeconds` summed for "time left" | "No agenda"      |
| `topic.{index,elapsedSeconds,budgetSeconds}` | live row + topic clock       | no clocks                     |
| `timed` / `policy.timed`                | hide budgets and clocks           | timed                         |
| `policy.floorShareThreshold`            | the red line                      | 0.6                           |
| `interventions[].line`                  | Karen's last line                 | footer hidden                 |
| `digest.{decisions,openItems,parked}`   | notes; falls back to `understanding.*` and `parked` | empty columns |
| `missingAttendees`, `readyToStart`, `requireStart` | gathering banner       | "Gathering…"                  |
| `agendaFinished`                        | marks every topic done on the finished board | —                  |

Two things brain does **not** publish today, which the board would show the moment it does:

1. **Topic owners.** The agenda contract has `owner` (a discordId) and the reducer reads
   `topics[].owner` (resolved through `people[].id → name`) or `topics[].ownerName`, but
   `engine.view()` does not include either yet, so the owner column is blank on a live
   meeting. The demo shows it.
2. **A meeting start time.** "Time left" is therefore *remaining by plan* — this topic's
   remaining budget plus untouched budgets — not wall-clock against a scheduled end.

`topic.elapsedSeconds` is assumed to be seconds on the live topic that keep increasing while
`phase === "active"`; the board adds the time since the last update so the clock ticks even
when brain's JSON is unchanged. Talk-time bars are drawn straight from `totalSeconds` with no
local extrapolation, so they move exactly when brain says they did.
