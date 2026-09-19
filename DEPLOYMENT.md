# gavel — backend deployment

**Status:** live and validated
**Host:** `uk-lon-1` (173.234.79.39) · **Domain:** https://gavel.pro7ocol.com
**Deployed commit:** `5baf50b` (`feat(scripts): set-vonage-key.sh` — on top of Artem's `3227f0a`, Karen waits for a pause + STT fix)
**Deployed at:** 2026-09-19 16:39 UTC · **Last validated:** 2026-09-19 16:39 UTC
**Checkout on the box:** `/home/coder/DEV/gavel` · **Compose project:** `gavel`

---

## What is running

Eight containers from `compose.yaml`, one of which is a run-once migration job.

| Container | Image | Size | Bind | Health | Purpose |
|---|---|---|---|---|---|
| `gavel-ears-1` | `gavel-ears:local` | 1.67 GB | `127.0.0.1:8787` | healthy | Discord voice connection, STT/TTS, the wire, the REST API. Artem's package |
| `gavel-brain-1` | `gavel-brain:local` | 807 MB | `127.0.0.1:8788` | healthy | All chair decisions — talk-time, interruptions, agenda budget. Imports no call SDK |
| `gavel-calendar-1` | `gavel-calendar:local` | 385 MB | `127.0.0.1:8790` | healthy | Invite board, `.ics` feed poller, scheduler. **The only public service** |
| `gavel-chair-video-1` | `gavel-chair-video:local` | 387 MB | `127.0.0.1:8791` | healthy | Karen's face — fal lip-sync, idle loop |
| `gavel-stream-vonage-1` | `gavel-stream-vonage:local` | — | `127.0.0.1:8792` | healthy | Vonage Video HLS broadcast + archive, publisher/watch pages. **No credentials yet** — `/healthz` reports `credentials: absent` |
| `gavel-postgres-1` | `postgres:17-alpine` | 424 MB | `127.0.0.1:5432` | healthy | Meetings, sessions, transcripts, memories, LLM cost log |
| `gavel-redis-1` | `redis:7-alpine` | 57.8 MB | `127.0.0.1:6379` | healthy | Ephemeral only (`--save "" --appendonly no`) |
| `gavel-migrate-1` | `gavel-ears:local` | — | — | `Exited (0)` | `alembic upgrade head`, runs once per `up`, gates `ears` |

Every application port is bound to **`127.0.0.1`**, not `0.0.0.0`. Nothing but Traefik reaches
them from outside the box.

### Boot order

`postgres` (healthy) → `migrate` (exit 0) → `ears` (healthy) → `brain`, `calendar`.
`chair-video` has no dependencies — it only talks to fal.

```
                    Traefik (shared, not ours)
                              │ :443
                              ▼
                       calendar :8790  ──► ears :8787 (EARS_API_URL)
                                                │
   Discord voice ◄──────────────────────────────┤
                                                │ ws://ears:8787
                                         brain :8788
                                                │
                                        chair-video :8791 ──► fal.ai
        postgres :5432 ◄── ears, brain          │
        redis :6379    ◄── ears                 ▼
                                          Nebius Token Factory
```

---

## Ingress

There is **no Traefik in this project's compose file.** The box already runs one:

```
n8n-compose-file-traefik-1   traefik   0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
```

It owns `:80`/`:443` and is shared with ~22 other containers (n8n, interg, calcom, thalamus,
rental-os…). `calendar` joins its network (`traefik-public`, declared `external: true`) and
attaches routing labels. **Nothing in the shared Traefik config was modified.**

```yaml
traefik.http.routers.gavel-calendar.rule: Host(`gavel.pro7ocol.com`)
traefik.http.routers.gavel-calendar.entrypoints: websecure
traefik.http.routers.gavel-calendar.tls.certresolver: mytlschallenge
traefik.http.services.gavel-calendar.loadbalancer.server.port: "8790"
```

`mytlschallenge` is the resolver name the shared Traefik already defines
(`--certificatesresolvers.mytlschallenge.acme.tlschallenge=true`). Artem's labels assumed it;
it was verified present before the first `up`, which is why ACME succeeded on the first try
instead of silently falling back to a self-signed cert.

### TLS — real, not self-signed

```
issuer=C=US, O=Let's Encrypt, CN=YR1
subject=CN=gavel.pro7ocol.com
notBefore=Sep 19 14:12:00 2026 GMT
notAfter=Dec 18 14:11:59 2026 GMT
```

DNS was confirmed to point at this box (`gavel.pro7ocol.com` → 173.234.79.39, matching the
host's own IPv4) *before* deploying — ACME's TLS-ALPN challenge fails silently otherwise.

---

## Public surface

The whole host routes to `calendar`. What answers on it:

| Path | Code | Notes |
|---|---|---|
| `https://gavel.pro7ocol.com/board` | 200 | The invite board — this is the demo URL |
| `https://gavel.pro7ocol.com/health` | 200 | `{"status":"ok","pending":0,"feeds":[]}` |
| `https://gavel.pro7ocol.com/` | 307 → `/board` | A judge types the bare domain and lands on the board |
| `https://gavel.pro7ocol.com/compose` | 200 | The compose front door — free-text brief → confirm → meeting |
| `https://gavel.pro7ocol.com/console` | 404 | Correct — the operator console is deliberately not exposed |
| `http://gavel.pro7ocol.com/board` | 301 → `https://…/board` | HTTP is redirected, not served |

`ears`, `brain` and `chair-video` have **no** Traefik labels and are unreachable from the
internet. They are reached only over the compose network by service name, or from the box
over loopback.

---

## Routes, per service

**calendar** (`:8790`, public)
```
GET  /board                    the invite board
GET  /health
POST /invite                   create a meeting + invite
GET  /m/{session_id}           one meeting's page
POST /m/{session_id}/join      join → hands off to ears
```

**ears** (`:8787`, internal — Artem's API)
```
GET    /health
GET    /api/status
GET    /api/meetings            POST /api/meetings
PUT    /api/meetings/{id}       DELETE /api/meetings/{id}
GET    /api/sessions            POST /api/sessions
POST   /api/sessions/end
GET    /api/sessions/{id}/transcript
GET    /api/sessions/{id}/usage
GET    /api/discord/servers     PUT /api/discord/servers/{guild_id}
GET    /api/memories            POST /api/memories   PATCH /api/memories/{id}
POST   /api/interventions
POST   /api/llm-calls
POST   /api/say
POST   /api/stop
GET    /api/brain-state
```

**brain** (`:8788`, internal)
```
GET /state     full chair state — phase, topic, people, persona
```

**chair-video** (`:8791`, internal)
```
POST /speak-video    audio → lip-synced Karen clip
GET  /idle           the between-interventions loop
GET  /healthz
```

---

## Configuration

Config comes from `/home/coder/DEV/gavel/.env` (untracked, gitignored) via
`${VAR:-default}` interpolation in `compose.yaml`. **Key names only** — no value has been
read, printed or logged:

| Key | State | Used by |
|---|---|---|
| `DISCORD_EARS_TOKEN` | set | ears — Karen's bot login |
| `NEBIUS_API_KEY` | set | brain — all LLM calls |
| `NEBIUS_BASE_URL` | set | brain |
| `SLNG_API_KEY` | set | ears — STT (`deepgram/nova:3`) + TTS (`slng/fish/tts:s2.1-pro`) |
| `FAL_KEY` | set | chair-video — lip-sync + avatars |
| `EARS_WIRE_URL` | set | — |
| `CONCIERGE_WEBHOOK_URL` | set | — |
| `WIRE_PORT`, `STAGE_PORT` | set | port overrides |
| `VONAGE_API_KEY` | set | **not the Video product** — sits beside `VONAGE_SMS_FROM` in `.env.example`, i.e. Messages/SMS |
| `DEVIN_PAT_KEY` | set | not used by any service; agent-orchestration API only |
| `DISCORD_GUILD_ID` | empty | **fine** — servers are now chosen in the console and stored in Postgres; this is a legacy seed (`packages/ears-discord/README.md:23-29`) |
| `NEBIUS_MODEL` | empty | **fine** — `config/models.yaml` owns the profiles; `config.ts:210-212` only overrides on a truthy value |
| `DISCORD_CONCIERGE_TOKEN` | empty | second bot, not deployed |
| `SEAM_SHARED_SECRET` | empty | not enforced in this build |

**Not set, and each one disables a feature:**

| Missing key | What stays dark |
|---|---|
| `CALENDAR_ICS_FEEDS` | Google/iCal feed polling — `/health` reports `"feeds":[]` |
| `CALENDAR_ATTENDEE_MAP` | Discord-id → name mapping; unmapped ids render as the raw id |
| `RESEND_API_KEY` + `COMPOSE_FROM_EMAIL` | the compose lane's email leg (branch not merged yet) |

Defaults that matter, all in `compose.yaml`: `CHAIR_PERSONA=funky`, `STT_MODE=stream`,
`LIPSYNC_MODEL=veed/lipsync/v2`, `AVATAR_MODEL=fal-ai/flux/schnell`,
`SCHEDULER_POLL_SECONDS=30`, `CALENDAR_FEED_WINDOW_HOURS=24`, `DISCORD_LEAVE_GRACE_SECONDS=10`.

### One fix was needed before this would start

`.env` had four section headings written without a leading `#`:

```
Nebius Token Factory (brain)
SLNG (ears + mouth)
fal (live video stage)
Seam between the two halves
```

Node and Python dotenv tolerate that. **Docker Compose does not** — a line with no `=` and no
`#` is a fatal parse error:

```
failed to read /home/coder/DEV/gavel/.env: line 5: unexpected character "(" in variable name "Nebius Token Factory (brain)"
```

Backed up to `.env.bak.<epoch>` (covered by `.gitignore:6`), then commented the four lines with
`sed -i -E 's/^([^#=[:space:]][^=]*)$/# \1/'`. The file was only ever inspected through
`sed 's/=.*/=<redacted>/'` — no value was printed.

---

## Data

- **`gavel_postgres_data`** — named Docker volume, 50.38 MB. Survives `down`/`up`. This is the
  only persistent state. `docker compose down -v` destroys it; back up first.
- **Redis** — deliberately non-persistent (`--save "" --appendonly no`). Losing it costs
  nothing.
- Schema is Alembic, applied by `gavel-migrate-1` on every `up` before `ears` is allowed to
  start.

---

## One change was made to the repo for this deploy

`compose.yaml`'s `calendar` service was missing the ICS passthrough, so the Google-feed poller
merged earlier the same afternoon had no way to be configured in the deployed stack. Added
before the first build, not after, so the image was built once:

```yaml
      SCHEDULER_POLL_SECONDS: ${SCHEDULER_POLL_SECONDS:-30}
      CALENDAR_ICS_FEEDS: ${CALENDAR_ICS_FEEDS:-}
      CALENDAR_FEED_WINDOW_HOURS: ${CALENDAR_FEED_WINDOW_HOURS:-24}
      EARS_API_URL: http://ears:8787
```

Committed `49fdb94`, pushed `9997897..49fdb94`.

---

## Operating it

```bash
cd /home/coder/DEV/gavel

# redeploy from source control — never hand-copy files
git pull --ff-only
docker compose up --build -d --wait

docker compose ps
docker compose logs -f ears brain calendar chair-video
docker compose restart calendar          # one service
docker compose down                      # stop; volume survives
```

`--wait` is what makes a deploy honest: it blocks until every healthcheck passes, so a failed
start is an exit code rather than a container quietly restart-looping.

**Do not** run `docker compose down` in the Traefik project — 22 unrelated containers depend
on that ingress.

---

## Validation evidence (2026-09-19 15:55 UTC)

Behaviour, not just "it's up":

```
brain        Up 45 minutes (healthy)
calendar     Up 45 minutes (healthy)
chair-video  Up 45 minutes (healthy)
ears         Up 45 minutes (healthy)
postgres     Up 45 minutes (healthy)
redis        Up 45 minutes (healthy)
migrate      Exited (0)

https://gavel.pro7ocol.com/board    200
https://gavel.pro7ocol.com/health   200   {"status":"ok","pending":0,"feeds":[]}
http  →  301 https://gavel.pro7ocol.com/board
cert     Let's Encrypt YR1, expires Dec 18 2026

127.0.0.1:8787/health    200
127.0.0.1:8788/state     200   {"chairName":"Karen","phase":"idle","persona":{"id":"funky","displayName":"Funky Karen"}}
127.0.0.1:8790/health    200
127.0.0.1:8791/healthz   200   {"falConfigured":true,"falReachable":true,"lipsyncModel":"veed/lipsync/v2"}
```

Karen is actually logged into Discord:

```json
{"user": "Karen#0480", "guilds": ["HackBarna Test"], "event": "discord.ready", "level": "info", "timestamp": "15:10:18.579047"}
```

Brain is connected to the wire:

```
15:10:22.424 info  brain.ready {"state":"http://0.0.0.0:8788/state","ears":"ws://ears:8787"}
15:10:22.449 info  wire.connected {"url":"ws://ears:8787"}
```

`chair-video` reports `falReachable: true` — that is a live call to fal, not a config check.

---

---

## Vonage Video wiring

The Application exists in the Vonage dashboard and uses **key auth** (private/public keypair,
JWT), not the legacy key/secret pair:

```
VONAGE_APPLICATION_ID = c9a721b4-914b-49ef-9690-0f3b06da678e
```

That id is an identifier, not a credential — it is safe in this file. The **private key is
not**, and never appears here, in `.env.example`, or in any log. `packages/stream-vonage`
supports both auth styles and picks automatically (`vonage.py: detect_auth_style`): an
Application id + private key means JWT auth (`vonage==4.9.0`), a bare key/secret means the
legacy path (`opentok==3.15.0`).

### Installing the private key

`VONAGE_PRIVATE_KEY` holds the PEM **contents**, not a path — as a single line with literal
`\n` between the PEM lines, which `settings.py: vonage_private_key_pem` unescapes on read.
A multi-line value in a `.env` is parsed inconsistently by docker compose, so it is stored
escaped on purpose.

Do not hand-edit `.env`. Use the helper, which never lets the key reach a terminal, a log or
a shell history entry:

```bash
# from a machine that can reach this box over ssh
ssh coder@173.234.79.39 'umask 077; cat > ~/vonage_private.key && \
  /home/coder/DEV/gavel/scripts/set-vonage-key.sh ~/vonage_private.key \
    c9a721b4-914b-49ef-9690-0f3b06da678e' < ~/Downloads/private.key

# or, when ssh to this box is not available, from a PLAIN SHELL on the box
# (never an agent chat box — that would put the key in a conversation transcript):
scripts/set-vonage-key.sh --paste c9a721b4-914b-49ef-9690-0f3b06da678e
# paste the whole PEM including BEGIN/END lines, then Ctrl-D
```

It checks the `BEGIN … PRIVATE KEY` header, replaces rather than appends (re-running is
safe), chmods `.env` to 600, and prints only the shape of what landed — byte count and PEM
line count, never content.

Then:

```bash
docker compose up -d --wait stream-vonage
curl -s localhost:8792/healthz     # credentials: "present", authStyle: "jwt"
```

Until the key is installed, `/healthz` reports `{"credentials":"absent","authStyle":null}`
and `POST /stream/start` fails with `VONAGE_API_SECRET is not set` — the setting name, never
a value.

**The Application needs the Video capability enabled.** If it was created with only Messages
or Voice, JWT auth will succeed and session creation will still 4xx.

### Exposure

`stream-vonage` binds `127.0.0.1:8792` only and carries no Traefik labels, so `/publisher`
and `/watch` are **not reachable from the internet**. If judges are meant to open the watch
page themselves, it needs a router label on `gavel.pro7ocol.com` the way `calendar` has one —
a five-minute change, but a deliberate one, so it has not been made unasked.

### Reference implementations from the Vonage team

- `Vonage-Community/demo-video-javascript-fal-starter` — Vonage Video + fal avatar
  livestreaming. Uses **Broadcast** (watch page + RTMP out to YouTube/Twitch/LinkedIn),
  **Archiving** to record, and **Signaling** for chat and avatar commands; the fal model is
  `decart/lucy-2-5/realtime`. This is the closest match to what `stream-vonage` already
  does, and its `setup.js` provisions the Vonage Application automatically.
- `Vonage-Community/demo-video-javascript-mastra-starter` — Vonage Video + Mastra agents.
  The interesting part for gavel is **Audio Connector**: it bridges call audio to and from an
  AI voice agent over a WebSocket (`src/wsBridge.ts`), and uses Signaling to push the agent's
  live transcript into the UI as captions. That is structurally what `packages/ears-discord`
  does through Discord. It is a real alternative ears path, and a decision for Vitaly — not
  a change to make two days before freeze.

## Known gaps

1. **`RESEND_API_KEY` and `DISCORD_MEETING_URL` are unset in the container.** The compose
   front door works and creates the meeting; the mailer runs dry-run by design and the `.ics`
   `LOCATION`/join link is empty until `DISCORD_MEETING_URL` lands. Both are Vitaly's to
   supply. Live email send is therefore **unverified**.
2. **Recurring calendar events are not expanded.** The feed poller does not handle `RRULE`, so
   a weekly standup in a subscribed calendar produces one occurrence, not a series.
3. **No feeds configured** — `CALENDAR_ICS_FEEDS` is empty, so the poller runs against nothing.
4. **Email is not wired** — the compose lane's Resend leg needs `RESEND_API_KEY` and
   `COMPOSE_FROM_EMAIL`, and that branch is unmerged.
5. **`SEAM_SHARED_SECRET` is empty.** The ears↔brain seam is unauthenticated. Acceptable only
   because both ports are loopback-bound and the services share a private Docker network.

## Blocked on Vitaly

- `CALENDAR_ICS_FEEDS=<secret ical url>` — treat the URL as a credential; it grants calendar read.
- Discord user ids for himself and Artem → `CALENDAR_ATTENDEE_MAP`.
- Resend account → verify the **`send.pro7ocol.com`** subdomain, not the root (root MX/SPF
  belongs to Proton) → `RESEND_API_KEY`, `COMPOSE_FROM_EMAIL=karen@send.pro7ocol.com`.

## Links

- Board (demo URL): https://gavel.pro7ocol.com/board
- Health: https://gavel.pro7ocol.com/health
- Repo: https://github.com/bioztar/gavel
- This document, rendered: https://github.com/bioztar/gavel/blob/main/DEPLOYMENT.md
- Host: `uk-lon-1`, 173.234.79.39 — the box these containers run on *is* the VPS
- Vonage fal starter: https://github.com/Vonage-Community/demo-video-javascript-fal-starter
- Vonage Mastra starter: https://github.com/Vonage-Community/demo-video-javascript-mastra-starter
- Contract between the halves: `docs/CONTRACT.md`
- Session state: `HANDOVER.md`
