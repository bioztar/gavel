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
