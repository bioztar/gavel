# gavel

An AI chair for meetings. You add it to a Discord voice call, hand it the agenda, and
it runs the meeting: it keeps time per topic, keeps any one person from holding the
floor, and speaks up when a topic is about to get skipped. A live web stage shows the
agenda, the talk-time split and the chair's face.

Built at **HackBarna AI Summit 26**, Norrsken House Barcelona, 19–20 September 2026.

## Why it exists

Most meetings fail in one of three ways: no agenda, one person talks for 40 of the 45
minutes, or the last two topics get 90 seconds each because the first one ran long. All
three are chair problems, and most calls have no chair. gavel is the chair.

## The judged moment

A live call where the agent says out loud: *"Vitaly, you've had eight of the last ten
minutes — Ana, you had a point on this."* The meter moves on the stage, the room hears
it happen. Everything in this repo is either that moment or support for it.

## How it is built

The agenda is prepared **before** the call and handed to the agent as a file. Generating
that agenda from a conversation is a separate, optional half of the product — nice, not
load-bearing.

```
  agenda.json  ─────────────────────────────┐
  (prepared before the call)                │
                                            ▼
  ┌──────────────────────┐   speech    ┌──────────────────────┐
  │  EARS                │ ──────────> │  BRAIN               │
  │  owns Discord voice  │             │  never sees Discord  │
  │                      │ <────────── │                      │
  │  · joins the channel │   speak()   │  · talk-time         │
  │  · who is speaking   │             │  · agenda clock      │
  │  · per-speaker STT   │             │  · interrupt policy  │
  │  · plays audio back  │             │  · what to say       │
  └──────────────────────┘             └──────────┬───────────┘
                                                  │
                                       ┌──────────▼───────────┐
                                       │  STAGE (browser)     │
                                       │  agenda · talk-time  │
                                       │  · live fal video    │
                                       └──────────────────────┘

  CONCIERGE (stretch) — a Discord bot that interviews attendees and writes agenda.json
```

Two halves, two people, one contract: [docs/CONTRACT.md](docs/CONTRACT.md). `brain`
never imports discord.js and `ears` never makes a decision — that is what lets two
people build in parallel for thirteen hours without touching each other's files.

## Sponsor stack

| Sponsor | Used for | Tier |
|---|---|---|
| **SLNG** | Speech-to-text per speaker, text-to-speech for the chair's voice | core |
| **Nebius** | Token Factory inference — what the chair says, and why | core |
| **fal.ai** | Live-generated video of the chair on the stage | stretch |
| **Mastra** | The Concierge agent, if it gets built | stretch |

Discord blocks video publishing from bots, so the chair's face lives on the web stage
rather than in the voice channel.

## Layout

| Path | Owner | What |
|---|---|---|
| `packages/ears` | one person | Discord voice: join, speaking events, STT, audio playback |
| `packages/brain` | the other | Talk-time, agenda clock, interrupt policy, Nebius, stage |
| `packages/concierge` | whoever is free | Stretch: Discord bot that writes the agenda |
| `packages/contract` | both | Shared schema and fixtures. Changes need both to agree |

## Docs

- [docs/PLAN.md](docs/PLAN.md) — chunks, dependencies, hour-by-hour, cut lines
- [docs/CONTRACT.md](docs/CONTRACT.md) — the agenda file and the ears↔brain wire
- [docs/WORKING-AGREEMENT.md](docs/WORKING-AGREEMENT.md) — two people, one repo, thirteen hours
