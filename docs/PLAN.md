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

## ears-vonage — chunks

The second call surface. Same wire, so the brain is untouched. It is a **browser tab**
that joins the session as an ordinary participant — no headless Chrome, no deployment.

| # | Chunk | Effort | Depends on |
|---|---|---|---|
| V1 | Join a session, subscribe to everyone, threshold `audioLevelUpdated` into `speaking.start/end` frames over the wire | 1h | contract |
| V2 | Publish the chair's voice — `AudioContext` destination as the publisher's `audioSource`, fed by the brain's `speak` frames | 1h | V1 |
| V3 | Publish the chair's face — canvas `captureStream()` as the video source, painted with fal frames | 1h | V1, B9 |
| V4 | Depth: `session.signal()` pushes agenda + interventions to every participant's UI; enable archiving | 30m | V1 |

Two things to respect at init, both documented gotchas: never initialise a publisher with
`audioSource: false` (it can never gain audio afterwards), and `setVideoSource()` only
works on camera publishers, so change the canvas rather than the source.

This surface is *less* risky than Discord — audio levels and custom tracks are
documented and supported, where Discord's voice receive is neither. It is also the only
one where the chair's face can be in the call.

## brain — chunks

| # | Chunk | Effort | Depends on |
|---|---|---|---|
| B1 | Load and validate the agenda file. Session state object | 45m | contract |
| B2 | Talk-time state machine — seconds per person, rolling-window share, from speaking events | 1h | contract |
| B3 | Replay harness — run `replay.jsonl` through the state machine at speed or real time | 45m | B2 |
| B4 | Agenda clock — current topic, spent vs budget, which topics are now at risk | 1h | B1 |
| B5 | **Interrupt policy** — the triggers. Deterministic, tunable from the agenda's `policy` block | 1.5h | B2, B4 |
| B6a | Mastra harness — the chair as a Mastra agent: Nebius as the model, SLNG and fal as tools, traces on. Deterministic triggers stay outside it | 45m | B5 |
| B6 | Nebius — given the trigger + state, one sentence in the chair's voice, generated through the Mastra agent. Falls back to a template if the call is slow or fails | 1h | B6a |
| B7 | SLNG TTS → `speak` frame over the wire | 1h | B6 |
| B8 | Web stage — agenda, live talk-time bars, current topic, what the chair just said | 1.5h | B2, B4 |
| B11 | Fire drill — hazard word in a transcript, chair breaks in, offers to alert emergency services, host confirms, SMS goes out. Demo number only | 1h | E6, V5, B6a |
| B9 | fal lip-sync video of the chair — driven by the TTS audio the chair is about to speak, called as a Mastra tool. Idle is a still frame | 1.5h | B8, B6a, B7 |
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

| Barcelona | ears-discord | brain | ears-vonage |
|---|---|---|---|
| 12:15–13:15 | **E1 spike — join, speaking events, playback** | B1 agenda + state, B2 talk-time | credentials from the Vonage mentor |
| 13:15–14:15 | E2 wire | B3 replay harness — offline loop running | V1 join + subscribe |
| 14:15–16:00 | E3 speak handler, E4 record fixture | B4 agenda clock, B5 policy | V1 levels → frames |
| 16:00–17:00 | **Integration checkpoint — real voice → real interrupt, on Discord.** Everyone, one call | | |
| 17:00–18:30 | E5 per-speaker decode | B6 Nebius line, B7 TTS | V2 publish the chair's voice |
| 18:30–19:30 | dinner | dinner | dinner |
| 19:30–21:00 | E6 SLNG STT | B8 stage | V4 signal + archiving |
| 21:00 | **CUT LINE — is the agent interrupting live and reliably on at least one surface?** If not, everyone works on the spine until it is. Nothing else matters | | |
| 21:00–22:30 | E6 finish, feed B10 | B9 fal video | V3 the chair's face in the call |
| 22:30–23:00 | Dry run, both surfaces, four people. Record it | | |
| Sun 09:00–10:00 | Fix what the dry run broke | | |
| Sun 10:00–11:00 | READMEs, 60-second recording, submit | | |

Three workstreams and two people is the honest tension in this schedule. The resolution:
**Discord and brain are the spine and start together; Vonage starts when the brain's
offline loop is running** and is picked up by whoever is freer, or by a third agent if
Artem has one to spare. If it slips, it slips — the demo works on one surface.

## Cut lines

Drop in this order:

1. **Concierge** — already parked. The agenda is a prepared file.
2. **The chair's face (B9, V3)** — decoration. The stage without a face still shows the meters.
3. **Transcript features (E5, E6, B10)** — the whole tier 2. The spine does not need them.
4. **The second surface** — if Vonage is not working by 21:00, demo Discord alone and
   show the seam in the README. One brain, two ears, is a slide as well as a fact.
5. **Nebius line (B6)** — fall back to templates.
6. Never cut: E1, E2, E3, B1, B2, B4, B5, B7. That is the demo.

## Risks

- **E1 is the unknown.** One hour, first thing, before anything is built on it.
- **Discord blocks bot video.** A fact, not a risk — the chair's face is on the browser
  stage, never a camera in the call. Do not spend an hour rediscovering it.
- **Latency on the intervention.** Measure TTS round-trip early. Over ~3 seconds and the
  interruption lands after the moment. Pre-warm the TTS and template the common lines.
- **"Built during the event — prior ideas fine, prior code is not."** This repo started
  empty today. Nothing gets lifted from an existing codebase.

## The fire drill (B11)

The one scripted laugh, and the only place the chair leaves the agenda.

Someone says "there's a fire" — or smoke, or gas leak. The chair stops the topic clock
mid-sentence, breaks in, and offers to alert emergency services. A **host** confirms out
loud. The chair sends the message and says so. Then, deadpan, it returns the floor to
whoever it interrupted and resumes the topic where it left off.

It demos three things at once: the chair hears content, not just who is talking (SLNG STT);
it reasons about what it heard (Nebius, through the Mastra agent); and it acts outside the
call (Vonage Messages). Depth of API use, in one twenty-second beat.

**How it fires**

1. Deterministic keyword spot on a `transcript` frame — `fire`, `smoke`, `gas leak`,
   `fuego`, `humo`. Cheap, no model in the hot path.
2. Model call classifies hazard vs figure of speech, so "fire off an email", "you're fired"
   and "this demo is fire" do not trip it. One sentence back: hazard yes/no.
3. Chair interrupts immediately, ignoring the `minSecondsBetweenInterventions` floor — this
   trigger is exempt, and it is the only one that is.
4. Chair asks a **host** (an attendee with `role: host` in the agenda) to confirm. Nothing is
   sent without a spoken yes inside 20 seconds. Anything else and it stands down out loud.
5. On confirm: Vonage SMS to `EMERGENCY_DEMO_NUMBER`, stage shows the message that went out,
   chair announces it and hands the floor back.

**Safety rules — these are not negotiable, and they are in the code, not the plan**

- The destination is **only** ever `EMERGENCY_DEMO_NUMBER` from the environment — a phone in
  the room. Never 112, 911, 999, or any emergency short code, in any branch, at any time.
  There is no configuration path that reaches a real emergency service; the demo number is
  read once and nothing else is dialable.
- Every message body starts `[DEMO — HackBarna hackathon, not a real emergency]`.
- No send without the host's spoken confirmation, and the exemption applies to this trigger
  only.
- If `EMERGENCY_DEMO_NUMBER` is unset, the chair still performs the whole beat and says it
  would have sent — it never falls back to a different number.

**Fallback if STT is not done by 21:00.** Keep the beat: a stage button plants the transcript
line, everything downstream runs for real. Say so in the demo — a scripted input into a real
pipeline is honest, a faked output is not.

## The face, revised (fal)

The fal mentor pointed at the **lip-sync** endpoint on the H3 Max family rather than
continuous video generation. That is a better fit and a cheaper one, and it changes the
shape of B9 and V3.

The chair only needs a face **while it is speaking**. The pipeline becomes:

```
trigger fires -> Nebius line -> SLNG TTS audio -> fal lip-sync(portrait, that audio) -> clip
                                      |                                                  |
                                      +-> audio into the call ------------------- stage / Vonage video
```

- One still portrait of the chair, generated once at the start of the day and reused.
- Between interventions the stage shows that still (or a two-second idle loop). No spend,
  no latency, nothing to keep alive.
- Lip-sync runs on the exact audio already produced for B7, so the face and the voice cannot
  drift apart.

**Latency is the open question.** Lip-sync is not instant, and the chair interrupting four
seconds late is worse than a chair with no face. Measure it first thing after the key lands.
If the round trip is slow: speak on time with the still frame up, and let the clip land on
the stage a beat later as a replay. Never hold the audio back to wait for video.

**Endpoint id to confirm with the mentor** — fal's lip-sync models sit under several
families and the H3 Max variant is the one they suggested. Get the exact model id from them
rather than guessing; ask at the same time whether a lip-sync clip per intervention counts
for the MiniMax H3 Max Director track, which reads as aimed at livestream-style generation.

## Decisions

- **Mastra stays thin** (decided 2026-09-19, Vitaly). It orchestrates the chair's outward
  calls — Nebius as the model, SLNG and fal as tools, traces on — and nothing more. The
  interrupt triggers stay plain deterministic code outside the framework. Nothing that
  decides *whether* to speak may sit behind an agent loop; the framework only shapes *what*
  is said and carries the calls. Budget for B6a is 45 minutes. If it costs more than that on
  the day, drop to direct SDK calls and keep the beat.

## Tracks

| Track | Qualifies via | Status |
|---|---|---|
| **SLNG** | TTS for the chair's voice; STT per speaker if tier 2 lands | core |
| **Nebius** | Token Factory for what the chair says | core |
| **Vonage** (gold) | The chair joins a session as a real participant — custom audio and video tracks, signalling, archiving | core |
| **fal.ai** | Live-generated video, called through Mastra, on the stage and in the Vonage call | stretch |
| **Mastra** | The harness around the brain's outward calls — Nebius, SLNG, fal as tools, with traces | core |

Building the second surface is what puts the gold track back on the table. Mastra no longer
depends on the Concierge — it is the harness the live chair already runs on. The overall prize does not care which track you entered.
