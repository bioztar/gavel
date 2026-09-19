# gavel

An AI chair for meetings. You add it to a Discord call, tell it what the meeting is
for, and it behaves like a competent project manager: it collects what it needs from
attendees beforehand, writes the agenda, then sits in the call and runs it — keeping
time, keeping one person from monologuing, and making sure every topic actually gets
covered before the call ends.

Built at **HackBarna AI Summit 26**, Norrsken House Barcelona, 19–20 September 2026.

## Why it exists

Most meetings fail in one of three ways: no agenda, one person talks for 40 of the 45
minutes, or the last two topics get 90 seconds each because the first one ran long.
All three are chair problems, and most calls have no chair. gavel is the chair.

## What it does

**Before the call** — you give it the purpose. It works out what it needs to know,
DMs the attendees for it, chases the ones who don't answer, and publishes an agenda
with a time budget per topic.

**During the call** — it joins the voice channel, listens, and tracks who is talking
and for how long. It speaks up when a speaker runs long, when a topic runs over its
budget, and when a topic is about to be skipped entirely. A live web stage shows the
agenda, the talk-time split, and the agent's own face.

## Architecture

```
  ┌───────────────────────┐                 ┌───────────────────────┐
  │  CONCIERGE            │   agenda.json   │  CHAIR                │
  │  Discord text + DMs   │ ──────────────> │  Discord voice        │
  │                       │ <────────────── │                       │
  │  · reachable cold     │  call events    │  · per-speaker audio  │
  │  · collects inputs    │                 │  · talk-time machine  │
  │  · drafts the agenda  │                 │  · interrupt policy   │
  │  · posts the minutes  │                 │  · speaks (SLNG TTS)  │
  └───────────────────────┘                 └──────────┬────────────┘
                                                       │
                                            ┌──────────▼────────────┐
                                            │  STAGE (browser)      │
                                            │  agenda · talk-time   │
                                            │  · live fal video     │
                                            └───────────────────────┘
```

Two processes, two Discord applications, one contract. See
[docs/CONTRACT.md](docs/CONTRACT.md) — it is the only thing the two halves share.

## Sponsor stack

| Sponsor | Used for |
|---|---|
| **Mastra** | The Concierge agent — reachable cold on Discord from a stranger's phone |
| **SLNG** | Speech-to-text in the call, text-to-speech when the chair speaks |
| **Nebius** | Token Factory inference — agenda drafting and the in-call moderation decisions |
| **fal.ai** | Live-generated video of the chair on the web stage |

Discord blocks video publishing from bots, so the chair's face lives on the web stage
rather than in the voice channel. The stage is a browser page, which is also where
live-generated video belongs.

## Layout

| Path | Owner | What |
|---|---|---|
| `packages/concierge` | side A | Discord bot: DMs, scheduling, info collection, agenda, minutes |
| `packages/chair` | side B | Voice join, per-speaker audio, moderation loop, TTS, stage server |
| `packages/contract` | both | Shared types and the seam schema. Changes need both sides to agree |
| `docs/` | both | Plan, contract, decisions |

## Running it

Copy `.env.example` to `.env` and fill it. Each package has its own README with the
commands for that half.

## Docs

- [docs/PLAN.md](docs/PLAN.md) — the build plan, work split and hour-by-hour schedule
- [docs/CONTRACT.md](docs/CONTRACT.md) — the seam between the two halves
- [docs/WORKING-AGREEMENT.md](docs/WORKING-AGREEMENT.md) — how two teams of agents share one repo
