# HANDOVER — gavel — 2026-09-19 14:40

## State
Spine complete and merged to `main`: ears↔brain wire, calendar→agenda, two chair personas,
chair-video. Nothing deployed yet — Artem is building the Docker Compose, deploy is on hold
awaiting his go-ahead. DNS for `gavel.pro7ocol.com` already resolves to the dev box.

## Done this session
- `packages/calendar` merged — `.ics` → §1 agenda → join page → scheduler starts the session
  through ears' HTTP API. 26 tests pass. Policy overrides merge onto ears' full ten-key table
  instead of replacing it.
- `packages/brain` personas merged — `CHAIR_PERSONA=formal|funky`, tone folded into the cached
  system prefix, per-persona fallback templates rotated per kind.
- `packages/chair-video` merged — `/speak-video`, `/idle`, `/healthz`, all persona-keyed.
- **Funky is now the default** (`personas.yaml: active: funky`, `Settings.default_persona`),
  rendering with `karen-funky-01.png` / `idle-funky.mp4`. Vitaly confirmed the pick.
- Latency table measured against real fal. Director finding written up by helm during merge.

## Open decision — blocks the face on stage
Lip-sync is too slow to be live: fastest completing model is `veed/lipsync/v2` at **41.4s for
a 3-second utterance**. Three options, Vitaly's call:
1. **Director** (`minimax/h3-max/director`) — genuinely live, but WebRTC/LiveKit, needs a
   client integration that does not exist, and per-second session billing.
2. **Idle loop only** — ships now, face as presence rather than speech. Zero new work.
3. ~~Pre-render fallback lines~~ — dead: only 2 of 36 funky templates are placeholder-free.

## Next steps (ordered)
1. Vitaly picks the endpoint (Director vs idle-loop-only).
2. Google Calendar: only `.ics` parsing exists. Recommended next step is the per-calendar
   secret iCal URL polled by the existing scheduler — no OAuth, no consent screen.
3. Deploy when Artem's compose lands: traefik-public network, `websecure` entrypoint,
   `mytlschallenge` certresolver, label pattern copied from `pro7ocol-website`.
   `CALENDAR_PUBLIC_URL=https://gavel.pro7ocol.com` or join URLs stay host-relative.
4. Vonage lane (needs app id + private key + API secret from Vitaly).
5. Quality Clouds analysis, Galtea eval set.

## Blockers / needs human
- Endpoint decision (above).
- Vonage credentials. Quality Clouds booth answer. Galtea account.

## Key files touched
- `packages/chair-video/README.md` — latency table + the Director finding
- `packages/brain/config/personas.yaml` — `active: funky`, asset names corrected
- `packages/chair-video/src/chair_video/settings.py` — persona→asset map, default funky
- `docs/CONTRACT.md` — §4 calendar, §5 chair-video
