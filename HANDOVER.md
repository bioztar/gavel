# HANDOVER — gavel — 2026-09-19 17:15

## State: full stack deployed and live on the VPS; https://gavel.pro7ocol.com serving the calendar with a real Let's Encrypt cert. Two crewmates still building (compose front door, director live avatar).

## Done this session
- Merged `chair/gcal` — Google Calendar secret-iCal feed polling in `packages/calendar`
  (`feed_store.py` holds no URL; errors carry only status code / exception class name;
  `/health` exposes per-feed `{feed, lastSuccess, eventCount, lastError}` and never a URL).
- Rebased onto Artem's `632c462 feat: deploy full stack with docker compose`, resolving the
  `.env.example` conflict by keeping both blocks.
- `49fdb94 chore: pass CALENDAR_ICS_FEEDS through to the calendar service` — compose.yaml did
  not forward `CALENDAR_ICS_FEEDS` / `CALENDAR_FEED_WINDOW_HOURS`, so the feed poller merged
  the same day was unreachable in the deployed stack. Both default to the code's own defaults.
- Fixed four comment lines in the repo-root `.env` that were missing their leading `#`
  (`Nebius Token Factory (brain)`, `SLNG (ears + mouth)`, `fal (live video stage)`,
  `Seam between the two halves`). Docker Compose refuses to parse `.env` otherwise:
  `failed to read .env: line 5: unexpected character "(" in variable name`. Node/python
  dotenv tolerated them, `docker compose` does not. Backup at `.env.bak.<epoch>` (gitignored).
- **Deployed**: `docker compose up --build -d --wait` → exit 0. All services healthy,
  `migrate` exited 0.

## Deployment facts (validated, not assumed)
- Host `173.234.79.39`; `gavel.pro7ocol.com` A-record resolves to it.
- Ingress is the **pre-existing** `n8n-compose-file-traefik-1`, which already defines
  `--certificatesresolvers.mytlschallenge.acme.tlschallenge=true` — the name Artem's labels
  assume. Nothing in that shared Traefik was touched.
- Cert: `issuer=C=US, O=Let's Encrypt, CN=YR1`, `subject=CN=gavel.pro7ocol.com`,
  valid Sep 19 → Dec 18 2026. Not the Traefik default self-signed cert.
- `https://gavel.pro7ocol.com/health` → 200 `{"status":"ok","pending":0,"feeds":[]}`
- `https://gavel.pro7ocol.com/board` → 200, `<title>gavel calendar — board</title>`
- `http://…/board` → 301 to https.
- `https://gavel.pro7ocol.com/console` → 404. Correct: Traefik routes the host to the
  calendar service only. The operator console stays loopback-only —
  `ssh -L 8787:127.0.0.1:8787` then `http://127.0.0.1:8787/console`.
- Loopback: ears `/console` 200, brain `/state` 200, calendar `/health` 200,
  chair-video `/healthz` 200.
- Logs clean. ears: `discord.ready {"user":"Karen#0480","guilds":["HackBarna Test"]}`,
  then `voice.waiting {"reason":"no humans in a configured voice channel"}`.
  brain: `brain.ready`, `wire.connected {"url":"ws://ears:8787"}`. No auth failures.
- No `.env` additions were needed for the deploy: every one of `GAVEL_DOMAIN`,
  `TRAEFIK_NETWORK`, `CALENDAR_PUBLIC_URL`, `CALENDAR_PORT`, `CHAIR_VIDEO_PORT`,
  `POSTGRES_PORT`, `REDIS_PORT` has a `${VAR:-default}` in compose.yaml resolving to the
  intended value. `BRAIN_MODEL_FAST`/`BRAIN_MODEL_NORMAL` unset is also fine —
  `packages/brain/src/config.ts:210-212` only overrides on a truthy value, so
  `config/models.yaml` stays in charge.
- `DISCORD_GUILD_ID` empty is **not** a blocker: `packages/ears-discord/README.md` says
  meeting channels are now selected per Discord server in the console and persisted in
  Postgres; the env pair is a backward-compatibility seed only.

## In flight / partially done
- `gavel-gavel-compose` (branch `chair/compose`, worktree `/home/coder/DEV/_worktrees/gavel-compose`)
  — the free-text brief → LLM parse → confirm → calendar invite + Resend email front door.
  `local-only`; helm merges. Mission `fleet/missions/20260919-gavel-compose.md` in helm.
- `gavel-gavel-director` — `minimax/h3-max/director` live avatar. Phase 0 measured (session
  open → live track 4.6–5.1s, → first generated chunk 7.6–8.2s, mid-session
  `client.prompt` ack ~900ms). Now building the session manager, browser stage page and the
  `engine.ts` `act()` hook.

## Next steps (ordered)
1. Vitaly: publish the ears operator console — `scripts/set-console-auth.sh karen`, then
   `docker compose up -d ears`. The route exists but is off; it is the control plane, so it
   only comes up behind basic auth.
2. Vitaly: rotate `VONAGE_API_KEY` (value reached a model API in a crewmate's tool output;
   nothing reached git).
3. Fill the two judged columns in `packages/brain/evals/results.md` with
   `pnpm evals -- --model --judge` and `NEBIUS_API_KEY` set. Needs a human with the key.
4. B11 fire drill (hazard heard → host confirms → demo SMS) is the last unbuilt PLAN item that
   is not on the forfeited Vonage Video track. Needs Messages credentials — decide before
   spending time on it.

Done since the last snapshot: the old item 1 here (root `/` 404 on the public host) is stale —
`/` now 307s to `/board` and both answer 200 publicly. Three Devin PRs merged and deployed:
#1 the ten-case eval set, #2 recurring-event expansion in the calendar feed poller, #3 the
20-word line budget with a regression test that fails on the pre-fix tree.

## Blockers / needs human (Vitaly)
- `RESEND_API_KEY` + `COMPOSE_FROM_EMAIL`: create the Resend account, verify the subdomain
  **`send.pro7ocol.com`** (not the root — the root MX/SPF belongs to Proton and verifying it
  would disturb live mail), then append both keys to `/home/coder/DEV/gavel/.env`.
  Until then compose runs in dry-run.
- `CALENDAR_ICS_FEEDS=<Google "Secret address in iCal format" URL>` — now plumbed through
  compose, still unset. Treat that URL as a credential.
- Discord user IDs for Vitaly and Artem, for `CALENDAR_ATTENDEE_MAP`.
- Known demo-day limitation: recurring events (`RRULE`) are not expanded by the feed poller.

## Key files touched
- `compose.yaml` — the two ICS env passthrough lines.
- `.env` (untracked) — four malformed comment lines fixed; backup alongside.
- `HANDOVER.md` — this file.

## Console is published (2026-09-19)

`https://gavel.pro7ocol.com/console` is live behind HTTPS basic auth — user `karen`,
password set in the repo-root `.env` as a bcrypt hash (`GAVEL_CONSOLE_USERS`, with every
`$` doubled because compose interpolates them). `GAVEL_CONSOLE_PUBLIC=true` is what creates
the Traefik route at all; unset it and the route disappears.

The route covers `/console`, `/live` (websocket) and `PathPrefix(/api/)` — the whole REST
surface, because every useful console action is a write. `/watch` and `/board` are unchanged
and still open.

Turn it off after the hackathon: `scripts/set-console-auth.sh --off`.
Change the password: `scripts/set-console-auth.sh karen` then `docker compose up -d ears`.
