# gavel

Karen is an AI chair for meetings. Add her to a Discord voice call, hand her the agenda,
gather the attendees, and say “Karen, let's start the meeting.” She opens with the agenda,
hands the first topic to a named person, keeps time, redirects shared tangents, balances
the floor, and answers when someone addresses her. The ears console shows the live
transcript, Karen's exact words, agenda progress, facts, decisions, open items, and the
parking lot.

Built at **HackBarna AI Summit 26**, Norrsken House Barcelona, 19–20 September 2026.


**Build board:** https://bioztar.github.io/gavel/ — every task, owner, dependency and
status. Change a status by editing [`docs/tasks.json`](docs/tasks.json) and pushing.

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
  ┌──────────────────────┐             ┌──────────────────────┐
  │  EARS-DISCORD        │   speech    │  BRAIN               │
  │  owns the voice conn │ ──────────> │  knows no call API   │
  ├──────────────────────┤             │                      │
  │  EARS-VONAGE         │ <────────── │  · talk-time         │
  │  owns the session    │   speak()   │  · agenda clock      │
  │                      │             │  · interrupt policy  │
  │  · who is speaking   │             │  · what to say       │
  │  · plays audio back  │             │  · meeting notes     │
  └──────────────────────┘             └──────────┬───────────┘
                                                  │
                                       ┌──────────▼───────────┐
                                       │  EARS CONSOLE        │
                                       │  agenda · talk-time  │
                                       │  transcript · notes  │
                                       └──────────────────────┘

  CONCIERGE (stretch) — a Discord bot that interviews attendees and writes agenda.json
```

Two call surfaces, one brain. `brain` holds every decision and knows about no call API
at all; an `ears` package owns one connection and makes no decisions. They meet at
[docs/CONTRACT.md](docs/CONTRACT.md) and nowhere else — which is what lets the same
agent chair a Discord call and a Vonage call, and lets people build in parallel for
thirteen hours without touching each other's files.

**Discord** is where meetings already happen. Karen's presence in the room is her voice,
a static persona still in her participant tile (`assets/persona/`), and a live board —
agenda, talk-time, decisions — that she presents as a screen share from that tile
(`packages/stage`, built separately).

## Sponsor stack

| Sponsor | Used for | Status |
|---|---|---|
| **SLNG** | Speech-to-text per speaker and Karen's text-to-speech voice | implemented |
| **Nebius** | Token Factory inference for relevance, meeting notes, and Karen's spoken lines | implemented |
| **Mastra** | Agents and the traced intervention workflow | implemented |
| **Vonage** | Planned second call surface with custom audio/video tracks | planned |

Discord blocks video publishing from bots. The implemented Discord experience therefore
uses the ears operator console; the Vonage surface remains planned.

## Layout

| Path | Owner | What |
|---|---|---|
| `packages/ears-discord` | one person | Discord voice: join, speaking events, STT, audio playback |
| `packages/ears-vonage` | one person | Vonage session: join as a participant, audio levels, publish voice |
| `packages/brain` | the other | Meeting lifecycle, talk-time, agenda, moderation, notes, Nebius |
| `packages/concierge` | whoever is free | Stretch: Discord bot that writes the agenda |
| `packages/contract` | both | Shared schema and fixtures. Changes need both to agree |
| `assets/persona` | — | Karen's persona stills — the image in her participant tile (`PROMPTS.md` records how they were made) |

## Try it

Join the test Discord server: **https://discord.gg/qR6RwKuAh**. While `ears-discord` is
running, select its meeting voice channel in the operator console; the bot joins when
someone enters it and leaves after the room empties. Setup and the operator console:
[packages/ears-discord/README.md](packages/ears-discord/README.md).

Start ears with `just run`, start brain with `pnpm start`, open
`http://127.0.0.1:8787/console`, and create a meeting. Starting a session creates a
gathering lobby; Karen greets whoever walks in and starts the agenda clock once everyone
expected is in the call — or the moment somebody asks her to begin, whichever comes
first. Nothing on a wall clock ever starts it.

## Run everything with Docker Compose

The root [`compose.yaml`](compose.yaml) runs the complete deployment: Postgres, Redis,
schema migrations, Discord ears, brain, and calendar ingestion. Docker is
the only host dependency; the VPS's existing `traefik-public` network provides HTTPS for
the calendar join page.

```bash
cp .env.example .env             # first run only; fill DISCORD_EARS_TOKEN,
                                 # SLNG_API_KEY and NEBIUS_API_KEY
docker compose up --build -d --wait
docker compose ps
```

Open `http://127.0.0.1:8787/console`. Follow both application logs with
`docker compose logs -f ears brain`; stop the deployment with `docker compose down`.
Postgres data survives restarts and `down` in the `postgres_data` volume.

The console and data-service ports are intentionally published on host loopback, not
the public network. For a single VPS, clone the repository there, create `.env`, and run
the same `docker compose up` command. Set `CALENDAR_PUBLIC_URL` and `GAVEL_DOMAIN` to
the VPS hostname; `gavel.pro7ocol.com` is the default. Access the no-auth operator
console through SSH:

```bash
ssh -L 8787:127.0.0.1:8787 user@your-vps
# Then open http://127.0.0.1:8787/console on your laptop.
```

Only SSH needs to be open inbound; the bot and model APIs use outbound connections.
Traefik owns public ports 80/443 and routes only the calendar service. If the named
external network does not exist yet, create it once with
`docker network create traefik-public`. Deploy an update with
`git pull --ff-only && docker compose up --build -d --wait`.

## Docs

- [docs/PLAN.md](docs/PLAN.md) — chunks, dependencies, hour-by-hour, cut lines
- [docs/CONTRACT.md](docs/CONTRACT.md) — the agenda file and the ears↔brain wire
- [HANDOVER.md](HANDOVER.md) — current implementation state, limits, and next live test
- [docs/QUALITY.md](docs/QUALITY.md) — verification results and eval strategy
- [docs/CREDENTIALS.md](docs/CREDENTIALS.md) — required accounts and environment names
- [docs/WORKING-AGREEMENT.md](docs/WORKING-AGREEMENT.md) — two people, one repo, thirteen hours
