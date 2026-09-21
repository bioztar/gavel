# The contract

Two things are shared: the **agenda file** and the **ears↔brain wire**. Everything else
either side can rewrite without telling anyone.

Freeze both before writing code against them. Additive changes are free afterwards;
renaming or removing a field is a conversation.

---

## 1. The agenda

Prepared before the call and handed to the brain. For the demo it is a committed file.
If the Concierge ever gets built, it writes this same shape and nothing downstream
changes.

Times are in **seconds**, so a demo agenda can be three minutes long without fractions.

```json
{
  "sessionId": "hb26-demo-1",
  "purpose": "Decide the launch date and name an owner for each blocker",
  "totalSeconds": 300,
  "attendees": [
    { "discordId": "100000000000000001", "name": "Vitaly", "role": "host" },
    { "discordId": "100000000000000002", "name": "Ana", "role": "attendee" }
  ],
  "topics": [
    {
      "id": "t1",
      "title": "Where we actually are",
      "goal": "One honest status per workstream",
      "budgetSeconds": 120,
      "owner": "100000000000000002",
      "mustHear": ["100000000000000002"],
      "questions": ["What is not done that you expected to be done?"],
      "type": "discussion"
    }
  ],
  "policy": {
    "floorShareThreshold": 0.6,
    "floorWindowSeconds": 120,
    "softHandoverSeconds": 45,
    "hardHandoverSeconds": 90,
    "topicOverrunFactor": 1.2,
    "silenceSeconds": 15,
    "minSecondsBetweenInterventions": 45
  }
}
```

`policy` is tunable on stage without a redeploy — lower the thresholds and the agent
fires inside a three-minute demo. `mustHear` lists people who should say something on
this topic; the chair invites them if they have not. `type` is `"discussion"` (the default)
or `"presentation"`: one person has the floor by design, so the chair never hands it on.

---

## 2. The ears↔brain wire

Two processes, a WebSocket on localhost. JSON frames, `{ "type": ..., ... }`.
Sub-millisecond on one machine, and it means either half runs alone.

**An `ears` package owns exactly one call connection and makes no decisions. `brain`
makes every decision and imports no call SDK — not discord.js, not any other.**

Every ears implementation is interchangeable. `brain` is started pointing at one wire and
cannot tell which surface is on the other end. Adding a second surface is a second ears
package and nothing else.

### ears → brain

| `type` | When | Fields |
|---|---|---|
| `ready` | Voice connection up | `channelId`, `participants[]` |
| `participants` | Someone joins or leaves | `participants[]` — `{discordId, name}` |
| `speaking.start` | A participant starts speaking | `discordId`, `at` |
| `speaking.end` | They stop | `discordId`, `at` |
| `transcript` | Tier 2 — an utterance was transcribed | `discordId`, `text`, `startedAt`, `endedAt` |
| `spoken` | Playback of a `speak` finished | `utteranceId` |

`speaking.start` / `speaking.end` need no audio decoding on either surface. That is
deliberate — talk-time, monologue detection and the whole interrupt policy run on those
two events plus a clock. Transcription is a later, separate capability.

How each side produces them:

| | source | note |
|---|---|---|
| Discord | the voice gateway's speaking state, per user | arrives as discrete start/stop |
| a surface that exposes a continuous audio level | per-participant level, 0–1.0 | thresholds it (~0.2) with hysteresis in the ears package and emits the discrete frames |

The hysteresis lives in the ears package, never in the brain. The brain sees the same two
frames from every surface and that is the entire point of the seam.

### brain → ears

| `type` | Does | Fields |
|---|---|---|
| `speak` | Play this audio into the voice channel | `utteranceId`, `audio` (base64), `format`; additive `text` is the exact spoken line for operator UIs |
| `speak.start` | Additive: a line streamed while it is synthesized. Queues and plays like `speak` (same `priority` rules), bridging gaps with silence until chunks arrive | `utteranceId`, `format` (`pcm_s16le`), `sampleRate` (`48000`), `channels` (`1` \| `2`), `text?`, `priority?` |
| `speak.chunk` | Raw PCM for an open `speak.start`, in order. Unknown `utteranceId`s are ignored | `utteranceId`, `audio` (base64) |
| `speak.end` | No more chunks; the line ends once what arrived has played. One `spoken` per line, as for `speak` | `utteranceId`, `error?` |
| `stop` | Stop current playback | — |

The brain does its own TTS and hands over finished audio. The ears do not know what a
sentence is.

### Additive, from `ears` (free per the rules above — ignore what you don't need)

- Every ears→brain frame carries `at` (ISO 8601 UTC) and `atMs` (epoch ms).
- `transcript` also carries `name`, `utteranceId`, `seq`, `final`, `turnId`, `confidence`,
  `speaker`. A long utterance arrives as several frames with one `utteranceId` and rising
  `seq`, and `final: true` marks the last one. Each frame is new text: concatenate them, never
  replace. In streaming mode (the default) a frame is a stretch of finalized words, about
  0.6–0.8 s after a pause. In `STT_MODE=http` a frame is at most `CHUNK_MAX_MS` (15 s) of speech.
- `speaker` is the diarization label *within one Discord user's audio* (`"0"`, `"1"`, …).
  It tells apart several people sharing one account, like a room mic. It is `null` in
  HTTP mode. The pair (`discordId`, `speaker`) identifies a voice.
- `spoken` also carries `interrupted` (a `stop` cut it short) and `error`.
- **Turns** — speaking events smoothed over pauses shorter than `TURN_GAP_MS` (1.5 s),
  i.e. who holds the floor. Crosstalk is two open turns.

| `type` | When | Fields |
|---|---|---|
| `turn.start` | Someone takes the floor | `discordId`, `turnId`, `previousDiscordId` |
| `turn.tick` | Every `TURN_TICK_MS` (10 s) while they keep it | `discordId`, `turnId`, `startedAt`, `durationMs`, `speakingMs` |
| `turn.end` | Silent for `TURN_GAP_MS` | `discordId`, `turnId`, `startedAt`, `endedAt`, `durationMs`, `speakingMs` |
| `session.started` | A run of a meeting begins — from the ears console, or on joining voice. Also re-sent on connect | `sessionId`, `meetingId`, `title`, `context`, `agenda` (§1 shape with `sessionId` filled, or `null`) |
| `session.ended` | Console ended it, or a new one started | `sessionId` |
| `voice` | The operator picked the chair's voice in ears' console. Sent on change, and **first** on connect | `voice` (a TTS voice id, e.g. `aura-2-thalia-en`) |

`voice` is one setting for two synthesizers: ears' console say-box and the chair. Both
read it per line rather than at startup, so a change lands on the next thing either says —
no restart, and no second copy of the setting to keep in step. It leads `hello()` on
purpose: a brain reconnecting mid-meeting should learn how to speak before it learns what
the meeting is, or its first line comes out in a voice the operator already changed away
from. ears stores the choice (`app_settings.tts_voice`), so it is also what the next boot
uses; brain treats the frame as an override above its own `config/models.yaml`, because
someone clicking a dropdown mid-meeting means it now and a YAML hot-reload must not
silently undo them. Ignoring the frame is legal, as with every additive frame — a brain
that does simply keeps using its configured voice.

`session.started` opens a **gathering lobby**, not the agenda clock. Two things open the
meeting out of it, and nothing else does — not joining voice, not a wall-clock time:

- every `agenda.attendees` entry is in the latest participant set, and has been for
  `autoStartDelayMs` (3 s). A roster is required: a session with no expected attendees at
  all has no "everyone" to wait for, so it waits to be asked. `policy.requireStart: true`
  turns this half off;
- a final transcript addressed to Karen with an explicit start instruction (“Karen, let's
  start the meeting”). This one always works, however few people are in the call — being
  told to start and answering "no, I'll wait" is the one thing a chair cannot do. Whoever
  never turned up is named in the opening instead.

Either way she then speaks the agenda, names the first speaker, and enters the active
phase. While the lobby is open, somebody walking into the channel gets a short spoken
hello naming who is still expected — unless their arrival is the one that completes the
roster, since the opening is then seconds away and welcomes them itself.

The roster is snapshotted when the session starts and is re-sent unchanged if a brain
reconnects. It is the meeting's **saved** attendee list where there is one — an invitation
from `packages/calendar` — with each saved attendee bound to the speaker in the channel
whose **name** is theirs, because an invitation carries an email and a voice channel
carries a snowflake (§4). Whoever is present and matches no attendee is appended; whoever
is expected and absent is kept, and is who the chair is waiting for. With no saved roster
— every meeting the ears console creates — the people in the voice channel *are* the
roster, and the first of them is the host. The brain re-runs the same name binding on
every `participants` frame, which is what recognizes the people who arrive after the
session started; a binding rewrites that attendee's `discordId` and every `owner` /
`mustHear` that named them.

### Additive — moderation (brain → ears, and back)

The chair's hands in the call. ears decides nothing: it does what it is told, and owns
only the timer that lifts a mute, so a brain that dies mid-mute never leaves anyone muted.

| `type` | Direction | Fields | Does |
|---|---|---|---|
| `speak` | brain → ears | + `priority` (bool, default false) | Jumps the queue, cuts off a non-priority line (it gets `spoken.interrupted`), plays as Discord's priority speaker so the room is ducked |
| `speak`, `speak.start` | brain → ears | + `quietMs`, `maxWaitMs` (ints, both optional) | Wait for a pause: the line stays first in the queue (streamed audio keeps buffering) until no human has been heard for `quietMs`, then plays; after `maxWaitMs` in the queue it plays anyway. A held priority line does not cut off the line already playing. Unset: play as soon as it is first in line |
| `mute` | brain → ears | `discordId`, `seconds` (ears caps at 60), `reason?` | Server-mutes them; ears unmutes after `seconds`, on `session.ended`, and on shutdown |
| `unmute` | brain → ears | `discordId` | Lifts a mute early. ears only ever unmutes people it muted |
| `moderation` | ears → brain | `action` (`muted` \| `unmuted` \| `failed`), `discordId`, `until?` (epoch ms), `error?` | The outcome of the above |

The Discord bot needs **Mute Members** and **Priority Speaker** for these.

### Additive — ears is the one store (REST, `http://127.0.0.1:8787`)

The brain keeps nothing on disk. What it decides goes into ears' Postgres, next to the
transcripts; Mastra's own storage uses the same database in a `mastra` schema.

| Route | Body / query | For |
|---|---|---|
| `POST /api/memories` | `discordId`, `name?`, `kind` (`parked` \| `note`), `summary`, `quote?`, `topicId?`, `sessionId?` | A point parked for later, per person — survives the session |
| `GET /api/memories` | `?discordId=` (repeatable) `&status=open` `&sessionId=` | What is still open for the people in the call |
| `PATCH /api/memories/{id}` | `status` | Resolve it |
| `POST /api/interventions` | `sessionId`, `kind`, `targetId?`, `addresseeId?`, `topicId?`, `line`, `source` (`llm` \| `template` \| `cache`), `actions[]`, `composeMs?`, `ttsMs?` | What the chair said, and why |
| `POST /api/llm-calls` | `sessionId`, `agent`, `model`, `inputTokens`, `outputTokens`, `cachedTokens`, `latencyMs`, `costUsd`, `cacheHit` | Token accounting; returns the session's running totals |
| `GET /api/sessions/{id\|current}/usage` | — | Totals for a session |
| `GET /api/brain-state` | — | Same-origin proxy to brain's live `/state` view for the ears console; URL comes from `BRAIN_STATE_URL` |

Brain's read-only `GET http://127.0.0.1:8788/state` view includes the meeting phase
(`idle`, `gathering`, `active`, `finished`), readiness/missing attendees, agenda completion,
topic and talk-time state, Karen's interventions, model usage, and `understanding`:
`facts`, `decisions`, `openItems`, `later`, and `offTopics`. This is a UI/read model, not
an additional command channel.

### Additive — policy

`policy` also takes `offAgendaGraceSeconds` (20), `allowMute` (false),
`escalateAfterSeconds` (10), `muteSeconds` (15) and `requireStart` (false — the chair
opens the meeting herself once every expected attendee is in the call; true: only "Karen,
let's start the meeting" ever opens it, however full the room is) and `timed` (true — false: topics have no budgets and no order; the chair
follows the room to whichever agenda item it takes up, never calls time on a topic or the
meeting, and the brain's `/state` reports `timed: false` and each topic's `discussed`) and
the two floor-handover thresholds, both counting one person's speaking time inside
`floorWindowSeconds`: `softHandoverSeconds` (45 — past it the chair hands the floor on at
that talker's next pause, never talking over them) and `hardHandoverSeconds` (90 — still
holding the floor past it, she cuts in at once as priority speaker; `0`: never cut in;
below the soft one: always cut in). Absent means the default. The older `handover`
(`"soft"` / `"hard"`) and `floorMinSpeakingSeconds` are still read from saved agendas.

`session.started.agenda` is optional for the brain to use: it is whatever the host typed
into the ears console (`http://localhost:8787/console`). A brain that loads its agenda
from a file can ignore it.

The same frames are also on Redis (`XADD` / `PUBLISH gavel:ears:events`), and `speak` /
`stop` are accepted on `PUBLISH gavel:ears:commands` — see `packages/ears-discord/README.md`.

### Rules

- Either side may restart. The brain re-sends nothing; the ears re-announce `ready` and
  `participants` on reconnect.
- Brain keeps live moderation state. ears owns durable transcripts, memories,
  interventions, and model-usage rows in its store.
- If the wire drops mid-call the ears stay in the channel silently rather than leaving.

---

## 3. The replay fixture

`packages/contract/fixtures/replay.jsonl` is a recorded stream of ears→brain frames with
timestamps. `brain` replays it to develop the entire policy with no Discord, no voice
channel and no second person. Commit it before either side starts, and keep it honest —
if the real ears emit something the fixture does not, add it to the fixture.

---

## 4. Calendar → agenda (packages/calendar)

`calendar` turns a real `.ics` invite into the §1 agenda shape and starts a session by
calling `ears-discord`'s existing HTTP API (`POST /api/meetings` then `POST /api/sessions`)
— it invents no second session concept and never touches `packages/ears-discord/`.

Creating a meeting starts it: `POST /compose/send` hands it to ears there and then, so the
chair is already holding this meeting (and this agenda) by the time anyone reaches the
voice channel. That is a lobby, not a running meeting — see §2 for what opens it. ears
being unreachable costs the head start and never the invite: the scheduler and the room
page's Join button still start it, and both are idempotent.

| Method & path | Body | Response |
|---|---|---|
| `POST /invite` | multipart `file` (an `.ics`) or `text/calendar` body | `{sessionId, joinUrl}` |
| `GET /m/{sessionId}` | — | HTML join page: title, agenda with budgets, attendees, a Join button |
| `POST /m/{sessionId}/join` | — | Starts the session via `ears-discord` (idempotent) and shows it as started |

A background scheduler calls the same start path automatically at the event's start time;
clicking Join just does it early. See `packages/calendar/README.md` for the attendee
email→`discordId` mapping (the one real seam between an invite and a Discord speaker).

## 5. chair-video (packages/chair-video)

A service the brain calls to turn the chair's spoken audio into a lip-synced talking-head
clip. It makes no decisions and never touches the agenda — see `packages/chair-video/README.md`
for latency numbers and persona details.

| Endpoint | Request | Response |
|---|---|---|
| `POST /speak-video` | `{"audioUrl"}` or `{"audioBase64","format"}`, optional `"persona"` (`"formal"`\|`"funky"`, default `"funky"`) | `{"videoUrl","durationMs","latencyMs"}` |
| `GET /idle` | optional `?persona=formal\|funky` | the persona's idle loop (video/mp4) |
| `GET /healthz` | — | `{"falConfigured","falReachable","lipsyncModel","avatarModel"}` |

An unknown or missing `persona` silently falls back to the configured default — a typo on stage must
not silence the chair. `packages/brain/config/personas.yaml` is the source of truth for a
persona's tone and template lines; `chair-video`'s own settings decide which asset file a
persona renders with.
