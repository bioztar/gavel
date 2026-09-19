# brain — the chair

Every decision Karen, gavel's chair, makes. She tracks who has held the floor and for how long, keeps the
meeting on its agenda, parks off-agenda points for later, invites quiet people by name,
decides when to cut in, writes the sentence, turns it into speech, and moderates through
ears.

**Never imports a call SDK.** Its entire input is the frame stream in
[../../docs/CONTRACT.md](../../docs/CONTRACT.md). ears is its hands (speak, priority speak,
mute) and its memory: one Postgres for everything.

## Run it

```bash
pnpm install
pnpm test                 # policy, state, and the whole loop on a recorded meeting
pnpm replay ../contract/fixtures/replay.offagenda.jsonl --stub-llm   # offline, free, instant
pnpm replay ../contract/fixtures/replay.offagenda.jsonl              # same, real Nebius (~$0.002)
pnpm start                # live: ears on ws://127.0.0.1:8787, state on http://127.0.0.1:8788/state
pnpm studio               # Mastra Studio: agents, tools, the intervene workflow, traces
```

Start ears first (`just run` in `packages/ears-discord`). Env, from the repo-root `.env`:
`NEBIUS_API_KEY`, `SLNG_API_KEY`. Optional: `EARS_WIRE_URL`, `EARS_HTTP_URL`, `STAGE_PORT`,
`AGENDA_FILE` (used when the ears console started a session without an agenda),
`POSTGRES_DSN` (same as ears; Mastra's tables go in the `mastra` schema),
`BRAIN_MODEL_FAST` / `BRAIN_MODEL_NORMAL`, `BRAIN_CONFIG_DIR`.

Without a Nebius key it uses a keyword classifier and the YAML templates. Without SLNG it
can decide, but it cannot speak.

## What the chair does

A voice connection opens a **gathering lobby**, not the meeting clock. Karen waits until
every expected attendee is present and someone says an addressed instruction such as
“Karen, let's start the meeting.” She then states the agenda, invites a named person to
open the first topic, and starts moderation. Other requests addressed to Karen get a
spoken answer as well.

Code decides **whether** to act and **what action** to take. The model only writes **what
to say**, and a YAML template is always there as a fallback. Triggers, checked every 250 ms
in this order, with at most one per tick:

| Trigger | When | Does |
|---|---|---|
| **escalate** | Someone redirected is still talking `escalateAfterSeconds` after the chair finished | Firm redirect. With `allowMute`, it announces the mute out loud and then mutes for `muteSeconds`. The host is never muted |
| **offAgenda** | The floor holder has been off the agenda for `offAgendaGraceSeconds` | **Parks** the point under their name in ears, then cuts in as priority speaker: acknowledge → "parked for later" → back to the topic with a question. When several people share the tangent, Karen addresses the room and parks it for everyone involved. A jump to a *later* agenda item gets "we'll get there" instead, and nothing is parked |
| **floorHog** | Over `floorShareThreshold` of the recent window, with others quiet | Thanks them, recaps, and hands the floor to someone by name |
| **topicOverrun** | Topic at budget × `topicOverrunFactor` | Moves on. After the last topic it wraps up and reads the parking lot back |
| **silence** | Nobody has spoken for `silenceSeconds` | Invites a specific person with one of the topic's questions: mustHear first, then the owner, then whoever has spoken least on this topic. If everyone has spoken, it runs a quick round |

The chair never talks over itself, and keeps `minSecondsBetweenInterventions` between
interventions (escalation is exempt, since it follows up on a redirect). The practice
behind the phrasing: parking lot, bank-and-thank, targeted questions, round robin, and
never embarrassing anyone.

**Memory.** Parked points go into ears' `memories` table under the person who raised them
and stay open across meetings. At the next session's start the chair loads the open ones
for everyone expected, and `/state` shows them. Every intervention lands in
`interventions`, and every model call in `llm_calls` with tokens and cost. `/state` also
exposes session facts, decisions, open items, and parked topics to the ears console.

## Tuning: everything is YAML (`config/`, hot-reloaded)

| File | What |
|---|---|
| `models.yaml` | Nebius model per profile (`fast` = classifier, `normal` = the chair's line), timeouts, prices, SLNG voice |
| `policy.yaml` | Threshold defaults (the agenda's `policy` block overrides them per meeting), trigger order, classifier rationing, pick-speaker order |
| `prompts/chair.yaml` | Persona, style rules, and for each intervention kind: instruction, examples, fallback templates |
| `prompts/relevance.yaml` | The off-agenda classifier prompt |

Edit a file mid-call and the next tick uses it. A file that fails validation is logged and
the last good config stays. To A/B a change, copy `config/` and run
`pnpm replay <file> --config ./config-b`; try a threshold with `--policy allowMute=true`.

## Cost

Measured on `replay.offagenda.jsonl`, a 6-minute, three-person meeting after adding note
extraction: **33 model calls, 16.7k input and 1.9k output tokens, $0.0027.**

- **Stable prefix.** Every call is `system prompt + session context block + short tail`.
  The context block (purpose, agenda, attendees) is built once per session and stays
  byte-identical, and Nebius reports ~340 of ~390 classifier input tokens as cached.
- **Stateless calls.** No conversation history grows with the meeting; continuity lives in
  the database.
- **Rationed classifier.** It runs only after ≥ 12 new words from someone who has held the
  floor for ≥ 3 s, with one call in flight per speaker. It re-checks an open episode only
  every 8 s, and identical windows reuse the verdict.
- **Cheap lines.** Capped at 70 output tokens. The off-agenda redirect is composed while
  the grace period runs, so cutting in costs only TTS (~1.2 s), and identical lines reuse
  their TTS audio.

Model bake-off notes are in `config/models.yaml`. Reasoning models (Nemotron-Lightning,
DeepSeek-V4-Flash, GLM-5.3-Flash) spend their whole token budget thinking; avoid them for
these calls. Gemma was faster in the full replay but broke the constrained wrap-up, so the
Qwen pair remains the default.

## Layout

| Path | Does |
|---|---|
| `src/engine.ts` | The loop: frames in, tick, interventions out. Every I/O dependency is injected |
| `src/policy/triggers.ts`, `pickSpeaker.ts` | Pure, deterministic policy |
| `src/state/talk.ts`, `relevance.ts` | Talk-time ledger; off-agenda episodes and classifier rationing |
| `src/chair/` | Context block, LLM interface + stub, SLNG TTS |
| `src/ears/` | WebSocket client; REST store client (plus an in-memory store for replay) |
| `src/mastra/` | Agents (`chair`, `relevance`, `operator`), ears/memory tools, the `intervene` workflow |
| `src/main.ts`, `src/replay.ts` | Live, and recorded |

The `operator` agent carries every tool (speak, stop, mute, unmute, park, recall, resolve,
meeting-state, advance-topic), for a human chatting with the chair in Studio. The live
agents carry none, so no tool schemas are sent on hot-path calls.
