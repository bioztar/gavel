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

**`ears` owns the Discord voice connection exclusively. `brain` never imports
discord.js. `ears` never makes a decision.**

### ears → brain

| `type` | When | Fields |
|---|---|---|
| `ready` | Voice connection up | `channelId`, `participants[]` |
| `participants` | Someone joins or leaves | `participants[]` — `{discordId, name}` |
| `speaking.start` | A participant starts speaking | `discordId`, `at` |
| `speaking.end` | They stop | `discordId`, `at` |
| `transcript` | Tier 2 — an utterance was transcribed | `discordId`, `text`, `startedAt`, `endedAt` |
| `spoken` | Playback of a `speak` finished | `utteranceId` |

`speaking.start` / `speaking.end` come from the voice gateway's speaking state and do
**not** require decoding audio. That is deliberate: talk-time, monologue detection and
the whole interrupt policy run on these two events plus a clock. Transcription is a
later, separate capability.

### brain → ears

| `type` | Does | Fields |
|---|---|---|
| `speak` | Play this audio into the voice channel | `utteranceId`, `audio` (base64), `format` |
| `stop` | Stop current playback | — |

The brain does its own TTS and hands over finished audio. The ears do not know what a
sentence is.

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
