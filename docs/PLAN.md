# Build plan

**HackBarna AI Summit 26.** Hacking opened 11:30 Saturday. Doors close 23:00. Code
freeze **Sunday 11:00**, demos 14:00, judging 16:00, awards 17:30. All times Barcelona.

That is roughly 11 hours on Saturday and 2 on Sunday morning. The plan is sized for 13
hours, not for 24, and it has cut lines in it on purpose.

## The one thing that must work

A live call where the agent says, out loud, something like *"Vitaly, you've had eight
of the last ten minutes — Ana, you had a point on this."* Everything else is support.
If the demo shows the talk-time meter moving and the agent cutting in at the right
moment, it lands. If it shows a beautiful agenda and no intervention, it does not.

Build toward that moment and cut away from it.

## Two sides

| | **Side A — Concierge** | **Side B — Chair** |
|---|---|---|
| Owner | colleague's agents | helm crewmates |
| Package | `packages/concierge` | `packages/chair` |
| Surface | Discord text and DMs | Discord voice + web stage |
| Sponsors | Mastra, Nebius | SLNG, Nebius, fal |
| Demo moment | A stranger DMs the bot and gets a real agenda back | The agent interrupts a monologue |

They meet at [CONTRACT.md](CONTRACT.md) and nowhere else.

## Side A — Concierge (chunks)

| # | Chunk | Effort | Depends on |
|---|---|---|---|
| A1 | Discord application, bot online in the guild, `/meeting` slash command registered | 45m | — |
| A2 | **Hosted** — public URL, stays up. Mastra's judge DMs it cold from a phone and it must answer at 17:30 Sunday | 45m | A1 |
| A3 | Intake conversation: purpose, attendees, duration, in DM or channel | 1.5h | A1 |
| A4 | Attendee info collection — DMs each attendee the questions, chases non-responders once | 1.5h | A3 |
| A5 | Agenda drafting on Nebius: purpose + attendee answers → topics with time budgets | 1.5h | A3 |
| A6 | `POST /v1/sessions` to the Chair, and post the agenda to the text channel as a fallback | 30m | A5, contract |
| A7 | Receive call events, post live notes, post minutes when the call ends | 1h | A6 |
| A8 | Mastra polish — the cold-start path from a stranger with no context | 1h | A2, A3 |

A2 is first among equals. Mastra's rubric gives 30 points to "works from a stranger's
phone" and the tie-break is whichever bot still answers at 17:00 Sunday. A bot on
localhost scores zero on both.

## Side B — Chair (chunks)

| # | Chunk | Effort | Depends on |
|---|---|---|---|
| B1 | **Spike: per-speaker audio.** Second Discord app joins a voice channel, one decoded PCM stream per speaker, two people talking at once. Prove it or fall back | 1h | — |
| B2 | Talk-time state machine — seconds per participant, share of floor, rolling window | 1h | B1 |
| B3 | SLNG STT on each speaker's stream → attributed transcript | 1.5h | B1 |
| B4 | Agenda engine — current topic, time spent vs budget, what is at risk of being skipped | 1h | contract |
| B5 | Interrupt policy — the rules that decide *when* to speak. Deterministic triggers, model only for *what to say* | 1.5h | B2, B4 |
| B6 | SLNG TTS → agent speaks into the voice channel | 1h | B1 |
| B7 | Nebius call — given transcript window + state, produce one sentence of chairing | 1h | B3, B4 |
| B8 | Web stage — agenda, live talk-time bars, transcript, served from the Chair's state | 1.5h | B2 |
| B9 | fal live video of the chair on the stage | 1.5h | B8 |

B1 is the load-bearing assumption of this entire half. Discord's voice receive is
undocumented and the common failure is handling only one speaker at a time — per-SSRC
packets are separable but each speaker needs its own decoder and jitter buffer, and
funnelling them through one player drops packets. **Prove two simultaneous speakers in
the first hour.** If it will not hold, the fallback is each participant running a
browser page that captures their own mic — worse demo, but it cannot fail in the room.

## Interrupt policy — get this right, it is the product

Deterministic triggers, so it fires predictably on stage:

- **Speaker overrun** — one participant holds more than ~60% of the floor over a rolling
  three minutes while others are present and quiet.
- **Topic overrun** — a topic passes its budget by 20%.
- **Topic at risk** — remaining time is less than the budget of the topics not yet
  started.
- **Silence** — more than ~15 seconds of nobody speaking during an active topic.

The model never decides *whether* to interrupt, only *what to say* — one sentence, in
the chair's voice, naming a person and a topic. A model deciding when to speak will
either never fire on stage or fire constantly.

## Schedule

| Barcelona time | Side A | Side B |
|---|---|---|
| 12:00–13:00 | A1 bot online | **B1 spike — go/no-go on per-speaker audio** |
| 13:00–14:00 | A2 hosted and reachable | B2 talk-time machine |
| 14:00–16:00 | A3 intake, A4 collection | B3 STT, B4 agenda engine |
| 16:00–18:00 | A5 agenda drafting on Nebius | B5 interrupt policy, B6 TTS out |
| 18:00–19:00 | dinner — A6 wired over dinner | dinner — B7 Nebius chairing line |
| 19:00–20:00 | **Integration: A6 → B. First end-to-end run** | |
| 20:00 | **CUT LINE — is the agent interrupting live?** If no, everything else stops and both sides work on B5/B6 until it does | |
| 20:00–22:00 | A7 minutes, A8 Mastra cold-start polish | B8 stage, then B9 fal video if B8 is done |
| 22:00–23:00 | Full dry run with four people in a call. Record it | |
| Sun 09:00–10:00 | Fix whatever the dry run broke | |
| Sun 10:00–11:00 | READMEs, 60-second recording, repo public, submit | |

## Cut lines

In this order, drop first when time runs out:

1. **fal video (B9)** — decoration. The stage without a face still shows the meters.
2. **Attendee chasing (A4)** — collect from whoever answers, mock the rest.
3. **Minutes (A7)** — the call ending well matters less than the call running well.
4. Never cut: B1, B2, B5, B6. That is the demo.

## Risks

- **Discord bot video is blocked.** Not a risk, a fact — the chair's face is on the web
  stage, never in the voice channel. Do not spend an hour rediscovering this.
- **Discord voice receive is unofficial.** See B1. Spike first, decide by 13:00.
- **SLNG latency.** Measure it in the first hour alongside B1. If round-trip STT→LLM→TTS
  is over ~3 seconds the interruption lands after the moment has passed; shorten the
  transcript window and pre-warm the TTS.
- **"Built during the event — prior ideas fine, prior code is not."** This repo starts
  empty today. Nothing gets lifted from an existing codebase.
- Two people, one repo, thirteen hours — see [WORKING-AGREEMENT.md](WORKING-AGREEMENT.md).

## Tracks this build is eligible for

| Track | What qualifies it | Who owns it |
|---|---|---|
| **Mastra** | Agent reachable cold on Discord, answers a stranger from their phone, still live 17:30 Sunday | A |
| **SLNG** | STT on every speaker, TTS for the chair's voice | B |
| **Nebius** | Token Factory for agenda drafting and in-call chairing decisions | both |
| **fal.ai** | Live-generated video on the stage — browser-viewable, not pre-rendered | B |

Vonage's Video API track is not reachable from a Discord build. That is the price of
the Discord decision and it was taken with eyes open.
