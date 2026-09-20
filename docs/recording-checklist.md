# Recording checklist — submission video (20 Sep 2026)

Deadline **12:00**. Script is `demo-script.md`; this file is only *how to shoot it*.

## Where files go

Everything into `/Users/alex/DEV/_assets/gavel-video/raw/`, named exactly:

| Take | Screen file | Webcam file |
|---|---|---|
| 0 — clone sample | — | `take0-voice.mov` |
| 1 — open + gate + invite | `take1-screen.mov` | `take1-cam.mov` |
| 2 — architecture + drift catch | `take2-screen.mov` | `take2-cam.mov` |
| 3 — Artem handover | `take3-screen.mov` | `take3-cam.mov` |
| 4 — roadmap + close | `take4-screen.mov` | `take4-cam.mov` |

Bad take: re-record over the same name. Only the last one survives.

## Capture setup (once, ~3 min)

1. **Screen** — ⌘⇧5 → *Record Entire Screen*, Options → Microphone = your usual mic. Do not
   record a window; the tab switches are part of the demo.
2. **Webcam** — QuickTime → File → New Movie Recording → Record. Leave it running across a
   whole take. Frame yourself head-and-shoulders, upper third of frame (it lands in a corner
   at ~22% size, so anything below your chest is thrown away).
3. **Sync** — start both, then **clap once, hands in webcam frame**, wait one second, then
   start talking. The clap is how the two files get aligned. One clap per take, every take.
4. Quit Slack/Mail notifications. Do Not Disturb on.

## Take 0 — voice clone sample (60s, do this first)

Webcam recording only, or screen-with-mic, doesn't matter — what matters is it is **the same
mic and room** as every other take. Read at the pace you'll narrate:

> "Most meetings get booked with a title, a time and nothing else. The few that do have an
> agenda have nobody enforcing it, because the person who could is the person talking. So we
> built a chair that will not let you schedule a meeting without an agenda, and then sits in
> the call and holds you to it. Including me. Three moves: hear, think, speak. She is in the
> Discord call as a participant, audio goes to speech-to-text, turns land in Postgres and
> Redis. Whether to interrupt is plain code — who has held the floor, for how long, against
> the agenda's own budget. Deterministic, testable, and it runs every two hundred and fifty
> milliseconds. Six containers behind Traefik. One of them knows what Discord is."

That paragraph is deliberately the video's own vocabulary — the clone gets your numbers and
your cadence, not generic read-aloud English.

## Pre-flight (from demo-script.md §1 — check, don't re-derive)

- [ ] `/compose` open, `/architecture` on slide 1, mailbox, calendar, Discord — tabs in that order
- [ ] Thin brief still refused (one rehearsal into `/compose`, expect the gate page)
- [ ] Attendee map has **Vitaly and Artem** both
- [ ] Persona **formal**, enforcement **High**
- [ ] Artem in the Discord call, briefed: **one answer, ~60 seconds, no pauses, keep going
      until she cuts in.** Without this, the floor-handover beat does not fire.

## The four takes

### Take 1 — cold open + gate + invite (target 2:35)
Cold open **B** (§2B — safest, no room dependency). Then §3 spine rows 0:00 → 2:35:
thin brief (§4a verbatim) → refusal page → real brief (§4b verbatim) → confirm table →
enforcement **High** → Send → open the invite in the mailbox → accept → calendar → join link.
Every click gets its own sentence. Never click in silence.

### Take 2 — architecture + the drift (target 1:15)
Karen opens the meeting herself — **stay silent 10 seconds**, let her read the agenda.
Then §5 verbatim off slide 1 (50s), then drift straight into §6 verbatim and keep talking.
She fires at ~8s. Let her finish, then: *"That was eight seconds. I did not cue her — and
notice she parked it rather than binned it."*

⚠ ≥45s must pass between her opening line and your drift (`minSecondsBetweenInterventions`).
The spine gives you 65s — don't rush the architecture to claw it back.

### Take 3 — Artem's minute + the handover (target 1:15)
*"Artem, you have been building the Discord side — what breaks first at scale?"* Then
**stop talking.** No "mhm", no agreement noises — every sound you make dilutes his share and
delays the trigger. She thanks him and hands the floor to you by name. One beat, then:
*"Sixty seconds, one voice, and the chair moved the floor. Nobody in this room had to be the
person who interrupts."*

### Take 4 — roadmap + close (target 1:10)
§7 off slide 3 (45s), then §8 close (25s). Land on *"It refused to work without one, and
then it held me to it."*

## Rules while shooting

- **Do not re-take a Karen intervention that lands slightly late.** A real one at 11 seconds
  beats a perfect one nobody believes (demo-script §11).
- Parse comes back wrong → fix the row, say *"the parse is a draft, the table is the
  contract"*, keep rolling. Never re-record for a parse miss.
- Her face fails to render → ignore it, keep going. Voice is the product.
- Overrun on a take is fine — I cut. Dead air is not; keep talking through every click.

## When a take is done

Tell me the take number. I start cutting take 1 while you shoot take 2 — don't wait until
all four are in the can.
