# Build plan

**HackBarna AI Summit 26.** Hacking opened 11:30 Saturday. Doors close 23:00. Code
freeze **Sunday 11:00**, demos 14:00, judging 16:00, awards 17:30. Barcelona time.

Roughly eleven hours Saturday and two Sunday morning. This plan is sized for thirteen
and has cut lines in it on purpose.

## The spine

Everything below is ordered around one demo: **the agent cuts in on someone who has been
talking too long, by name, out loud, while the meter moves on screen.**

The spine that produces it is shorter than it looks:

```
join voice → speaking events → talk-time clock → policy fires → TTS → audio in the call
```

Note what is *not* in that line: no audio decoding, no speech-to-text, no video. The
voice gateway reports who is speaking without a single audio packet being decoded.
Talk-time, monologue detection, topic budgets and the interrupt all run on speaking
events plus a clock plus the agenda file.

So **transcription is tier 2, not the foundation.** It buys content-aware lines ("Ana,
you said QA needs two weeks"), topic-coverage detection and minutes. Real value, bought
after the spine is standing, and if it fails nothing else falls over.

## Two halves

| | **ears** | **brain** |
|---|---|---|
| Owns | The Discord voice connection | Every decision |
| Imports discord.js | yes, exclusively | never |
| Risk | The undocumented parts of voice receive | Almost none — replayable offline |
| Blocked by the other | no | no |

Seam: [CONTRACT.md](CONTRACT.md). The brain develops against
`packages/contract/fixtures/replay.jsonl` from minute one and does not wait for a voice
channel to exist.

## ears — chunks

| # | Chunk | Effort | Depends on |
|---|---|---|---|
| E1 | **Spike, first thing:** bot joins a voice channel, logs `speaking start/end` per user, plays a WAV into the channel. Both directions proven | 1h | — |
| E2 | WebSocket server, emits the ears→brain frames from the contract | 45m | E1 |
| E3 | `speak` handler — accept base64 audio, play it, emit `spoken` | 45m | E2 |
| E4 | Record a real session to `replay.jsonl` so the fixture stops being hand-written | 30m | E2 |
| E5 | Tier 2 — per-speaker Opus decode to PCM, one decoder per SSRC, two simultaneous speakers | 1.5h | E1 |
| E6 | Tier 2 — SLNG STT per utterance → `transcript` frames | 1.5h | E5 |

E1 is the only genuinely unknown thing in the build and it is an hour. Do it before
anything else, including reading the rest of this file. If speaking events or playback
do not work, the shape of the whole day changes and it is better to know at 13:00.

E5 is where the documented weirdness lives — per-SSRC packets separate fine but each
speaker needs its own decoder and jitter buffer, and funnelling them through one player
drops packets. It sits behind the spine deliberately.

## brain — chunks

| # | Chunk | Effort | Depends on |
|---|---|---|---|
| B1 | Load and validate the agenda file. Session state object | 45m | contract |
| B2 | Talk-time state machine — seconds per person, rolling-window share, from speaking events | 1h | contract |
| B3 | Replay harness — run `replay.jsonl` through the state machine at speed or real time | 45m | B2 |
| B4 | Agenda clock — current topic, spent vs budget, which topics are now at risk | 1h | B1 |
| B5 | **Interrupt policy** — the triggers. Deterministic, tunable from the agenda's `policy` block | 1.5h | B2, B4 |
| B6 | Nebius — given the trigger + state, one sentence in the chair's voice. Falls back to a template if the call is slow or fails | 1h | B5 |
| B7 | SLNG TTS → `speak` frame over the wire | 1h | B6 |
| B8 | Web stage — agenda, live talk-time bars, current topic, what the chair just said | 1.5h | B2, B4 |
| B9 | fal live video of the chair on the stage | 1.5h | B8 |
| B10 | Tier 2 — consume `transcript`, topic-coverage detection, content-aware lines, minutes | 1.5h | E6 |

B6 always has a template fallback. A model call inside a live interruption is a latency
risk on stage, and a chair that says a slightly generic sentence on time beats a clever
one that arrives after the moment has passed.

## The interrupt policy — this is the product

Deterministic triggers, so it fires predictably in front of judges. Thresholds come from
the agenda's `policy` block so they can be tuned in the room:

- **Floor hog** — one person holds more than 60% of speaking time over a rolling two
  minutes, has spoken at least 45 seconds, and someone else present has been quiet.
- **Topic overrun** — a topic passes its budget by 20%.
- **Topics at risk** — time remaining is less than the summed budget of topics not yet
  started.
- **Unheard attendee** — someone in `mustHear` has not spoken on the current topic and
  the topic is 70% spent.
- **Silence** — 15 seconds of nobody speaking inside an active topic.

Plus one rule that matters as much as the triggers: **at least 45 seconds between
interventions.** An agent that chimes in constantly reads as broken.

The model never decides *whether* to speak — only *what to say*. A model deciding when
either never fires on stage or fires every eight seconds.

## Schedule

| Barcelona | ears | brain |
|---|---|---|
| 12:15–13:15 | **E1 spike — join, speaking events, playback** | B1 agenda + state, B2 talk-time |
| 13:15–14:15 | E2 wire | B3 replay harness — full offline loop running |
| 14:15–16:00 | E3 speak handler, E4 record fixture | B4 agenda clock, B5 policy |
| 16:00–17:00 | **Integration: real voice → real interrupt.** Both people, one call | |
| 17:00–18:30 | E5 per-speaker decode | B6 Nebius line, B7 TTS |
| 18:30–19:30 | dinner | dinner |
| 19:30–21:00 | E6 SLNG STT | B8 stage |
| 21:00 | **CUT LINE — is the agent interrupting live, on stage, reliably?** If not, both people work on the spine until it is. Nothing else matters | |
| 21:00–22:30 | E6 finish, feed B10 | B9 fal video, B10 transcript features |
| 22:30–23:00 | Dry run with four people in a call. Record it | |
| Sun 09:00–10:00 | Fix what the dry run broke | |
| Sun 10:00–11:00 | READMEs, 60-second recording, submit | |

## Cut lines

Drop in this order:

1. **Concierge** — already parked. The agenda is a prepared file.
2. **fal video (B9)** — decoration. The stage without a face still shows the meters.
3. **Transcript features (E5, E6, B10)** — the whole tier 2. The spine does not need them.
4. **Nebius line (B6)** — fall back to templates. Keep Nebius in the agenda-drafting path
   so the track still applies.
5. Never cut: E1, E2, E3, B2, B4, B5, B7. That is the demo.

## Risks

- **E1 is the unknown.** One hour, first thing, before anything is built on it.
- **Discord blocks bot video.** A fact, not a risk — the chair's face is on the browser
  stage, never a camera in the call. Do not spend an hour rediscovering it.
- **Latency on the intervention.** Measure TTS round-trip early. Over ~3 seconds and the
  interruption lands after the moment. Pre-warm the TTS and template the common lines.
- **"Built during the event — prior ideas fine, prior code is not."** This repo started
  empty today. Nothing gets lifted from an existing codebase.

## Tracks

| Track | Qualifies via | Status |
|---|---|---|
| **SLNG** | TTS for the chair's voice; STT per speaker if tier 2 lands | core |
| **Nebius** | Token Factory for what the chair says | core |
| **fal.ai** | Live-generated video on the stage | stretch |
| **Mastra** | Only if the Concierge gets built and hosted | parked |

Parking the Concierge gives up the Mastra track, and Vonage's gold Video API track was
already out of reach the moment the call surface became Discord. SLNG, Nebius and fal
remain, and the overall prize does not care which sponsor track you entered.
