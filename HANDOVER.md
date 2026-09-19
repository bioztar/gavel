# HANDOVER — gavel — 2026-09-20 00:05

## State: demo path is built, deployed and proven live. Code freeze in ~11h (Sun 11:00).

The invite flow is three screens and holds one rule: **no agenda, no booking.**
Everything below is live on `https://gavel.pro7ocol.com` and merged to `main` (`0771b26`).

## Done this session
- **Agenda gate.** A thin brief comes back as a refusal page — headline, one textarea,
  one button. No topic grid, no send path. `render_gate_html` in `compose.py`.
  `_rows_from_lines` is the insurance: if a typed agenda still parses to nothing, it
  splits on newlines/`;` so the headline demo beat cannot dead-end.
- **Enforcement gauge** (low/medium/high) on the confirm page. Levels live in
  `schema.py:ENFORCEMENT_LEVELS`, merged *over* `settings.policy_overrides` — env
  carries deployment facts, the gauge carries this meeting's intent. Pinned by
  `test_enforcement_gauge_reaches_the_agenda_policy`.
- **Karen can never mute Vitaly.** `policy.yaml` has `neverMuteRoles: [host]`, the
  organizer always gets `role: host`, and mute only fires via `escalate`. The visible
  delta at High is `handover: "hard"`, not the mute. Demo script says this out loud.
- **UI rebuilt light** — near-white ground, system font stack, hairline tables, pill
  buttons, segmented control, mobile breakpoint. Invite email matches the palette;
  its table skeleton is untouched so mail clients still render it.
- **Parser fix**: the brief opens "Karen, set up…" and she was being parsed in as an
  attendee/owner. `llm.py` prompt now states the first known attendee is the dictator
  ("me" = them) and the chair is never a participant. Owners now Artem/Vitaly/Vitaly.
- Demo script (md + html) and the architecture roadmap slide updated — gate at 0:28,
  gauge at 1:22, company-wide enterprise rules on the roadmap.

## Proven live (not just locally)
- Gate page: `200`, `name="agenda"` ×1, `topic_title_0` ×0, `/compose/send` ×0.
- Gate cleared: `200`, `name="enforcement"` ×3, topics parsed, "Send the invite".
- One **real** invite emailed to `vitaly@pro7ocol.com` at `enforcement=high` → `200`.
- `uv run pytest -q` → exit 0, 91 tests. `uv run ruff check .` → clean.

## Known, not bugs
- After `docker compose up -d --build calendar`, Traefik serves `404` for a few
  seconds while it re-resolves the new container. It clears itself. Do not go
  hunting for a routing misconfiguration — `curl` the route again.

## Next steps (ordered)
1. Rehearse the demo against the live site, script in hand.
2. `/compose`, `/architecture`, `/demo-script` are publicly unauthenticated — Vitaly's
   call whether that stands through the hackathon.
3. After the hackathon: `scripts/set-console-auth.sh --off`, rotate `VONAGE_API_KEY`,
   and decide on the two loose secret copies (`/home/coder/vonage_private.key`,
   `/home/coder/DEV/gavel/.env.bak`). `.env.example` still does not mention `--off`.
4. Back-burner, unbuilt: infer invitees with the LLM instead of the three hard-coded
   addresses.

## Blockers / needs human
- None for the demo path.

## Key files touched
- `packages/calendar/src/gavel_calendar/compose.py` — the three screens, all the CSS
- `packages/calendar/src/gavel_calendar/schema.py` — `ENFORCEMENT_LEVELS`, merge-order note
- `packages/calendar/src/gavel_calendar/app.py` — `agenda: str = Form("")` (empty form
  field is *missing* to Starlette unless it is defaulted)
- `packages/calendar/src/gavel_calendar/llm.py` — who "me" is, and that the chair isn't a guest
- `packages/calendar/src/gavel_calendar/invite_email.py` — palette only
- `docs/demo-script.{md,html}`, `docs/architecture.html` — the two new beats
