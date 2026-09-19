# Build plan

**HackBarna AI Summit 26.** Hacking opened 11:30 Saturday. Doors close 23:00. Code
freeze **Sunday 11:00**, demos 14:00, judging 16:00, awards 17:30. Barcelona time.

Roughly eleven hours Saturday and two Sunday morning. This plan is sized for thirteen
and has cut lines in it on purpose.

## Where we are — Saturday 15:57

**The Discord spine and brain are implemented and tested.** ears-discord has live voice,
streaming STT, playback, persistence, and the operator console. Brain has the gathering
lobby, explicit addressed start, agenda/talk-time policy, group tangent detection,
cross-session parking, structured meeting notes, Nebius composition, SLNG TTS, Mastra
traces, and an offline replay. The next critical task is the real end-to-end call (S4).

- **Voice in and out works on Discord, E2EE included.** Discord enforces DAVE end-to-end
  encryption on voice, and no released library decrypts it on receive. ears is Python on
  py-cord pinned to PR #3159, the one branch that does. It joins, reports speaking per
  user and plays the brain's `speak` audio back into the channel.
- **The wire is live** on `ws://localhost:8787` with every contract frame. Additive
  frames on top: `turn.start/tick/end` (who holds the floor, with a tick every 10 s so the
  brain never polls), `session.started/ended` (carrying the agenda typed in the console),
  and `at`/`atMs` on every frame. See [CONTRACT.md](CONTRACT.md) §2.
- **Transcription works (tier 2).** Each Discord user gets one streaming SLNG STT socket
  with diarization on. Finals arrive about 0.6–0.8 s after a pause, and two people on one
  mic come out as separate `speaker` labels. That means the fire drill (B11) and content-aware
  lines (B10) can use real transcripts instead of the stage-button fallback.
- **Everything is recorded.** Each frame also goes to Redis (`gavel:ears:events`) and
  Postgres. The brain can send `speak`/`stop` on Redis as well as the WebSocket.
- **Operator console** at `http://localhost:8787/console`: set up the meeting and agenda,
  start and end sessions, watch the live transcript, see floor/turn state and a signal log,
  see Karen's exact spoken lines and live understanding (facts, decisions, open items,
  agenda completion, parking lot), and use a say-box through SLNG TTS.
- **Meeting start is explicit.** A session is a lobby until expected attendees are present
  and somebody says “Karen, let's start the meeting.” No timer starts it accidentally.
- **Model bake-off:** DeepSeek-V4.1-Flash, thinking off, runs every call. It kept the chair's
  rules best (no parked point brought back up, no reused joke) at ~1 s a call.

Run it with `just setup && just run` in `packages/ears-discord`
([README](../packages/ears-discord/README.md)). Test server: https://discord.gg/qR6RwKuAh.

**Next:** run S4 on a real multi-person Discord call, export that session for E4, then
decide whether the remaining time goes to the second surface or demo polish.

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
| Imports a Discord SDK (py-cord) | yes, exclusively | never |
| Risk | The undocumented parts of voice receive | Almost none — replayable offline |
| Blocked by the other | no | no |

Seam: [CONTRACT.md](CONTRACT.md). The brain develops against
`packages/contract/fixtures/replay.jsonl` from minute one and does not wait for a voice
channel to exist.

## ears — chunks

| # | Chunk | Effort | Depends on | Status |
|---|---|---|---|---|
| E1 | **Spike, first thing:** bot joins a voice channel, logs `speaking start/end` per user, plays a WAV into the channel. Both directions proven | 1h | — | done |
| E2 | WebSocket server, emits the ears→brain frames from the contract | 45m | E1 | done |
| E3 | `speak` handler — accept base64 audio, play it, emit `spoken` | 45m | E2 | done |
| E4 | Record a real session to `replay.jsonl` so the fixture stops being hand-written | 30m | E2 | script done (`just export-replay`), fixture not yet recorded |
| E5 | Tier 2 — per-speaker Opus decode to PCM, one decoder per SSRC, two simultaneous speakers | 1.5h | E1 | done |
| E6 | Tier 2 — SLNG STT per utterance → `transcript` frames | 1.5h | E5 | done, streaming with diarization |
| E7 | Operator console + Postgres/Redis recording (unplanned) | — | E2 | done |

E1 is the only genuinely unknown thing in the build and it is an hour. Do it before
anything else, including reading the rest of this file. If speaking events or playback
do not work, the shape of the whole day changes and it is better to know at 13:00.

E5 is where the documented weirdness lives — per-SSRC packets separate fine but each
speaker needs its own decoder and jitter buffer, and funnelling them through one player
drops packets. It sits behind the spine deliberately.

*As built:* E1 turned out to be a different problem than planned. Speaking events were easy.
The hard part was DAVE, Discord's E2EE, which no released library decrypts on receive. The
fix was py-cord PR #3159. Once that worked, E5 came almost for free from py-cord's
per-user sink. The one extra rule: frames that are still encrypted while DAVE negotiates
are dropped rather than decoded into noise.

## ears-vonage — chunks

The second call surface. Same wire, so the brain is untouched. It is a **browser tab**
that joins the session as an ordinary participant — no headless Chrome, no deployment.

| # | Chunk | Effort | Depends on | Status |
|---|---|---|---|---|
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
| B1 | Load and validate the agenda file. Session state object | 45m | contract | done |
| B2 | Talk-time state machine — seconds per person, rolling-window share, from speaking events | 1h | contract | done |
| B3 | Replay harness — run `replay.jsonl` through the state machine at speed or real time | 45m | B2 | done |
| B4 | Agenda clock — current topic, spent vs budget, which topics are now at risk | 1h | B1 | done |
| B5 | **Interrupt policy** — deterministic triggers, including group tangents | 1.5h | B2, B4 | done |
| B6a | Mastra harness — agents, tools, traced intervention workflow | 45m | B5 | done |
| B6 | Nebius — relevance/notes plus one sentence in Karen's voice, with template fallback | 1h | B6a | done |
| B7 | SLNG TTS → `speak` frame over the wire, including exact display text | 1h | B6 | done |
| B8 | Operator view — agenda, talk-time, Karen's lines, facts, decisions and parking lot | 1.5h | B2, B4 | done in ears console |
| B11 | Fire drill — hazard heard, host confirms, demo SMS goes out | 1h | E6, V5, B6a | todo |
| B9 | fal face/video | 1.5h | B8, B6a, B7 | todo |
| B10 | Transcripts, relevance, content-aware lines and structured minutes-lite | 1.5h | E6 | done |

B6 always has a template fallback. A model call inside a live interruption is a latency
risk on stage, and a chair that says a slightly generic sentence on time beats a clever
one that arrives after the moment has passed.

## The interrupt policy — this is the product

Deterministic triggers, so it fires predictably in front of judges. Thresholds come from
the agenda's `policy` block so they can be tuned in the room:

- **Explicit opening** — before the active phase Karen only answers direct requests. Once
  everyone expected is present, an addressed start instruction makes her read the agenda
  and hand the first topic to a named person.
- **Off agenda** — after a grace period, park the tangent and return to the current topic.
  If several people share it, address the room rather than blaming the current speaker.
- **Escalation** — if a redirected speaker continues, issue a firm follow-up; optionally
  announce and apply a short mute, never to the host.
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

**Director vs lip-sync — pick one on the day, not both.**

The Director endpoint is an *infinite livestream*: a video stream that stays up and is steered
with prompts while it runs. Lip-sync is a clip per utterance. They solve different halves of
the same problem and the build has time for one.

| | Director (livestream) | Lip-sync (clip per line) |
|---|---|---|
| Presence | Chair is visibly there the whole call | Still portrait until it speaks |
| Mouth matches the words | No | Yes |
| Latency at the moment of interruption | None — stream is already live, steer it | A clip has to be generated first |
| Track fit | Aimed squarely at the H3 Max Director track | Generic |
| Risk | A stream to keep alive, publish, and pay for all day | Round-trip time on every intervention |

**Lean Director**, for three reasons: it is what that track is judged on, presence is what
sells "there is a chair in this meeting", and it removes latency from the exact moment that
must not be late. Steer it on state change — idle, listening, interrupting, fire drill —
rather than per word. A chair whose mouth is approximate but who is *always there and reacts*
reads better on a projector than a still that occasionally animates.

**The question that decides it**, and the first thing to ask the fal mentor: *is the Director
output playable in a browser `<video>` element (HLS or WebRTC URL)?* If yes, both surfaces get
it nearly free — `<video>` → canvas → `captureStream()` → the stage, and the same canvas track
straight into the Vonage publisher (V3). If it only comes back as files or a proprietary
player, the plumbing cost jumps and lip-sync becomes the better buy.

Decide within thirty minutes of the key working. Whichever loses, the fallback is the still
portrait — the demo never depends on the face.

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
- **ears-discord is Python on py-cord, not discord.js** (decided 2026-09-19, Artem).
  Discord enforces DAVE E2EE on voice, and py-cord PR #3159 is the only Python code that
  decrypts it on receive. `voice.py` is the only file that imports Discord, so if the pin
  misbehaves in a real call, `@discordjs/voice` 0.19 can replace it behind the same
  interface. The wire doesn't change, so the brain doesn't care.
- **STT is streaming, not per-utterance** (decided 2026-09-19, Artem). Each user gets one
  SLNG socket with diarization. In a bake-off on two voices sharing one track, streaming
  separated both voices and HTTP chunks separated one. It also keeps context across a turn
  and finalizes faster. `STT_MODE=http` stays as a fallback.

## Tracks

| Track | Qualifies via | Status |
|---|---|---|
| **SLNG** | TTS for the chair's voice; streaming STT per speaker with diarization (live in ears) | core |
| **Nebius** | Token Factory for what the chair says | core |
| **Vonage** (gold) | The chair joins a session as a real participant — custom audio and video tracks, signalling, archiving | core |
| **fal.ai** | Live-generated video, called through Mastra, on the stage and in the Vonage call | stretch |
| **Mastra** | The harness around the brain's outward calls — Nebius, SLNG, fal as tools, with traces | core |

Building the second surface is what puts the gold track back on the table. Mastra no longer
depends on the Concierge — it is the harness the live chair already runs on. The overall prize does not care which track you entered.
