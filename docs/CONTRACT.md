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
      "questions": ["What is not done that you expected to be done?"]
    }
  ],
  "policy": {
    "floorShareThreshold": 0.6,
    "floorWindowSeconds": 120,
    "floorMinSpeakingSeconds": 45,
    "topicOverrunFactor": 1.2,
    "silenceSeconds": 15,
    "minSecondsBetweenInterventions": 45
  }
}
```

`policy` is tunable on stage without a redeploy — lower the thresholds and the agent
fires inside a three-minute demo. `mustHear` lists people who should say something on
this topic; the chair invites them if they have not.

---

## 2. The ears↔brain wire

Two processes, a WebSocket on localhost. JSON frames, `{ "type": ..., ... }`.
Sub-millisecond on one machine, and it means either half runs alone.

**An `ears` package owns exactly one call connection and makes no decisions. `brain`
makes every decision and imports no call SDK — not discord.js, not the Vonage SDK.**

There are two ears implementations and they are interchangeable. `brain` is started
pointing at one wire and cannot tell which surface is on the other end. Adding a third
surface later is a third ears package and nothing else.

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
| Vonage | `subscriber.on('audioLevelUpdated')`, per subscriber, 0–1.0 | a continuous level — the ears package thresholds it (~0.2) with hysteresis and emits the discrete frames |

The hysteresis lives in `ears-vonage`, never in the brain. The brain sees the same two
frames from both surfaces and that is the entire point of the seam.

### brain → ears

| `type` | Does | Fields |
|---|---|---|
| `speak` | Play this audio into the voice channel | `utteranceId`, `audio` (base64), `format` |
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

### Additive — moderation (brain → ears, and back)

The chair's hands in the call. ears decides nothing: it does what it is told, and owns
only the timer that lifts a mute, so a brain that dies mid-mute never leaves anyone muted.

| `type` | Direction | Fields | Does |
|---|---|---|---|
| `speak` | brain → ears | + `priority` (bool, default false) | Jumps the queue, cuts off a non-priority line (it gets `spoken.interrupted`), plays as Discord's priority speaker so the room is ducked |
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

### Additive — policy

`policy` also takes `offAgendaGraceSeconds` (20), `allowMute` (false),
`escalateAfterSeconds` (10) and `muteSeconds` (15). Absent means the default.

`session.started.agenda` is optional for the brain to use: it is whatever the host typed
into the ears console (`http://localhost:8787/console`). A brain that loads its agenda
from a file can ignore it.

The same frames are also on Redis (`XADD` / `PUBLISH gavel:ears:events`), and `speak` /
`stop` are accepted on `PUBLISH gavel:ears:commands` — see `packages/ears-discord/README.md`.

### Rules

- Either side may restart. The brain re-sends nothing; the ears re-announce `ready` and
  `participants` on reconnect.
- The brain keeps all state. The ears keep none beyond the live connection.
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

| Method & path | Body | Response |
|---|---|---|
| `POST /invite` | multipart `file` (an `.ics`) or `text/calendar` body | `{sessionId, joinUrl}` |
| `GET /m/{sessionId}` | — | HTML join page: title, agenda with budgets, attendees, a Join button |
| `POST /m/{sessionId}/join` | — | Starts the session via `ears-discord` (idempotent) and shows it as started |

A background scheduler calls the same start path automatically at the event's start time;
clicking Join just does it early. See `packages/calendar/README.md` for the attendee
email→`discordId` mapping (the one real seam between an invite and a Discord speaker).
