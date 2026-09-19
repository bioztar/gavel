# HANDOVER — gavel — 2026-09-19 15:57

## State

The Discord meeting spine and the full brain are implemented. Karen can gather a room,
start only on an explicit addressed instruction, run the agenda, balance participation,
park individual or shared tangents, answer direct questions, and expose structured meeting
understanding in the ears console. The next milestone is a real multi-person end-to-end
call, not more offline policy work.

## Implemented

- `ears-discord`: Discord/DAVE voice receive, per-user streaming SLNG STT with diarization,
  playback/priority/mute commands, turn shaping, Postgres/Redis recording, meeting/session
  CRUD, and the operator console.
- `brain`: validated agendas, `gathering → active → finished` lifecycle, explicit wake/start
  instruction, talk ledger, deterministic triggers, group off-topic handling, persistent
  parking lot, Nebius relevance/notes and spoken-line generation, template fallback, SLNG
  TTS, and Mastra workflow traces.
- Console: exact text Karen is speaking, transcript and floor meters, agenda completion,
  missing-attendee/readiness state, facts, decisions, unresolved items, and parked topics.
- Contract: `speak.text` carries the exact spoken line for operator UIs; ears proxies brain's
  read-only state at `/api/brain-state`.
- Verification: brain 26 tests + TypeScript; ears 41 tests + Ruff + Pyright; deterministic
  stub replay and two real Nebius model replays.

## Model decision

Keep the configured Qwen pair. On the six-minute replay, the final Qwen run used 33 calls,
16,676 input tokens, 1,921 output tokens, and approximately $0.0027. Gemma returned lines
faster but violated the constrained wrap-up and spoke as if Karen would do follow-up work.

## Next steps

1. Run S4: ears + brain in one real Discord call with all expected attendees.
2. Verify the spoken opening, direct-address response, shared tangent redirect, and console
   understanding in the browser.
3. Export the real session with `just export-replay` and complete E4.
4. Record the short demo/dry run. Only then spend time on Vonage, fal video, or the fire drill.

## Known limits

- Meeting understanding is session-memory in brain; durable rows currently cover transcripts,
  interventions, model calls, and parked memories, not the extracted facts/decisions list.
- Vonage, fal video, calendar ingestion, concierge, and emergency-demo SMS are planned but
  not implemented in this repository state.
- The ears test suite emits two upstream deprecation warnings from Starlette's TestClient;
  project lint/type checks are clean.

## Run

1. `cd packages/ears-discord && just run`
2. `cd packages/brain && pnpm start`
3. Open `http://127.0.0.1:8787/console`, create/start a meeting session, gather everyone,
   then say “Karen, let's start the meeting.”
