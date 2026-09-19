# HANDOVER — gavel — 2026-09-19 23:30

## State: demo-ready. Agenda gate, structured invite, full-screen deck and rewritten demo script are live on https://gavel.pro7ocol.com. Code freeze Sunday 11:00.

## Done this session
- **Agenda gate.** A brief with no agenda comes back with zero topic rows and Karen's
  pushback, plus a `say it again` link back to `/compose` (the page is a POST result, so
  Back offers "Confirm Form Resubmission"). Measured against the live Nebius parse: five
  different agenda-less briefs, five empty `topics` arrays. Non-blocking by design — rows
  still render if the LLM hiccups, so a bad parse can't kill the demo.
- **The invite is the agenda, not the dictated text.** `invite_email.py` renders the parsed
  topic table (owner, duration, type, who must be heard) as HTML + text. Proven by rendering
  inside the deployed container from a real `build_agenda()` output: `dictated brief leaked:
  False`.
- **must-hear means *named*.** `llm.py` prompt now defines it; `_must_hear()` suppresses
  `compose.py`'s owner fallback so a presentation doesn't tell its own presenter to speak up.
- **Empty invitee box no longer 422s** — `attendees: str = Form("")`. Starlette reports an
  empty text input as *missing*, not empty. Regression test proven red then green.
- **Demo script rewritten** around one claim: Karen never writes your agenda, she refuses to
  work without one, then holds you to it. Four beats (gate → invite → drift catch → floor
  handover), four cold opens, a cut-lines block, a pitch-check rules table. Served at
  `/demo-script`.
- **Architecture deck** is now three full-screen slides at `/architecture`.
- 88 calendar tests green, ruff clean. `a4f718e..db8fc97 main -> main`.

## In flight / partially done
- **chair-video director sync measurement** — `scripts/measure_director_sync.mjs` is
  committed but the run never produced usable numbers: 5 of 6 utterances gave no detectable
  onset, last run died on `page.waitForFunction: Timeout 20000ms exceeded` at
  `measure_director_sync.mjs:219`. Not on the demo path; drop it if time is short.
- **Compose page-1 invitee UX** (Vitaly's back-burner item): page one's box is now optional
  and empty, which is the half that mattered. The "infer the invitees with an LLM, hard-code
  the three addresses" half is *not* built — the three addresses still come from settings.

## Next steps (ordered)
1. Rehearse §1 pre-flight end to end, including the thin brief at §4a (it must come back
   with no topic rows) and the mailbox check on the HTML invite.
2. **Send one real invite through Resend** to the three standing addresses. Everything so far
   was proven by rendering in-container; `body["html"]` has never been proven on the wire.
   This is the one gap in the demo path.
3. After the hackathon: `scripts/set-console-auth.sh --off` to burn the console password,
   rotate `VONAGE_API_KEY`.

## Blockers / needs human
- `/compose`, `/architecture`, `/demo-script` are publicly unauthenticated. Flagged before,
  still Vitaly's call — fine for a hackathon, not after.
- Two loose secret copies on disk await his decision: `/home/coder/vonage_private.key`,
  `/home/coder/DEV/gavel/.env.bak`.
- `.env.example` still doesn't mention `set-console-auth.sh --off`.

## Key files touched
- `packages/calendar/src/gavel_calendar/llm.py` — must_hear definition in the system prompt
- `packages/calendar/src/gavel_calendar/invite_email.py` — the structured invite; `_must_hear()`
- `packages/calendar/src/gavel_calendar/compose.py` — no-agenda pushback + back link
- `packages/calendar/src/gavel_calendar/app.py:133` — the `Form("")` fix
- `docs/demo-script.md` / `.html` — the run sheet Vitaly reads on stage
- `docs/architecture.md`, `docs/architecture.html` — §2b agenda gate, full-screen deck
