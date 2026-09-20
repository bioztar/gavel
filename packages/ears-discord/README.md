# ears — the stenographer

Owns the Discord voice connection, exclusively. Joins the channel, reports who is
speaking, transcribes each speaker separately with SLNG, records everything to
Postgres, fans every frame out to the brain (WebSocket) and Redis, and plays the
chair's audio back into the call.

Makes no decisions. Never reads the agenda. The wire is
[../../docs/CONTRACT.md](../../docs/CONTRACT.md) §2.

## Run it

Test server: **https://discord.gg/qR6RwKuAh** — after `just run`, select its meeting
voice channel in the console and join it.

```bash
brew install opus ffmpeg just     # libopus for decode, ffmpeg for playback
just setup                        # uv sync, Postgres + Redis in docker, migrations
just run                          # joins voice, serves ws://127.0.0.1:8787
just stub-brain                   # second terminal: prints frames, speaks every 30s
```

Env (repo-root `.env`): `DISCORD_EARS_TOKEN`, `SLNG_API_KEY`. Meeting channels are
selected per Discord server in the console and persisted in Postgres. The old
`DISCORD_GUILD_ID` + `DISCORD_VOICE_CHANNEL_ID` pair remains a deployment seed for
backward compatibility. `DISCORD_LEAVE_GRACE_SECONDS` controls how long the moderator
waits after the room empties before leaving (10 seconds by default). Postgres and Redis
are optional at runtime — if either is down, ears logs it once and the brain still gets
every frame.

The bot must be invited with the **`bot`** scope, not just `applications.commands`:
`https://discord.com/oauth2/authorize?client_id=<APP_ID>&scope=bot&permissions=40914176`
(View Channel, Connect, Speak, Use Voice Activity, Mute Members, Priority Speaker, Send
Messages, Embed Links). No privileged intents. Without the last two the chair still talks, but `mute` comes back
`failed` and priority lines do not duck the room.
Creating the app and sharing invite links: [docs/DISCORD-SETUP.md](../../docs/DISCORD-SETUP.md).

## The console — `http://127.0.0.1:8787/console`

A no-auth operator page, served by ears itself. It follows the OS light/dark
preference, and the **light / dark** button in the header overrides that and is
remembered per browser — dark at a desk, light when the console is on a projector
next to the meeting room page, which has no black to give.

- **Meeting** — title, purpose, context for the chair, topics with budgets / owner /
  must-hear, policy thresholds, and JSON import/export of the contract agenda. Attendees
  are snapshotted automatically from the voice channel when a session starts. Stored in
  Postgres (in memory if Postgres is down).
- **Discord servers** — every server visible to the bot, its voice channels and current
  occupancy. Choose one meeting channel per server, and where its live status message goes. The moderator joins when someone
  enters that channel and leaves shortly after the last person goes.
- **Sessions** — *Start new session with this meeting* ends the current run and sends the
  brain `session.started` with the agenda. Joining voice starts one automatically.
- **Live transcript** — per-speaker utterances as chunks land, with STT latency and confidence.
- **What Karen understands** — lobby/meeting state, agenda completion, extracted facts,
  decisions, unresolved items, and off-topic points parked for later (proxied from brain).
- **Floor & signals** — who is speaking, open turns ticking, talk-time share (silent
  attendees included), turn counters, STT p50, and a filterable log of every frame plus
  debug events (`stt.result` / `stt.skipped` / `tts.*` / `speak.*`). Click a row for JSON.
- **Say-box** — type a line, SLNG TTS speaks it into the channel through the same
  playback path as the brain's `speak`. *Stop* cuts it off.

## The status message — in Discord

Everything in *What Karen understands*, as one embed in the meeting voice channel's own
text chat, edited in place every `DISCORD_STATUS_INTERVAL_SECONDS` (5) when something
changed: phase and current topic with a time bar (red once over budget), the agenda,
talk-time share, then decisions, what is still open, and the parking lot. An untimed
meeting (`timed: false`) shows no clock or bar: the agenda marks where the room is now and
which topics it has already been on. One message per session; a deleted one is posted again. The notes are the brain's `digest` —
merged and deduplicated there (see the brain README). Per server, in the console's server
card: on/off, and the voice channel's chat or any text channel — with a warning when Karen
lacks Send Messages / Embed Links there. Stored in Postgres (`discord_status`).
`DISCORD_STATUS_ENABLED=false` turns it off everywhere. The console log shows
`status.posted` with the message link. `status_board.py`; only `voice.py` touches
Discord.

## What comes out

| Frame | From |
|---|---|
| `ready`, `participants` | joining, and anyone joining/leaving; re-sent to every brain that connects |
| `speaking.start` / `.end` | py-cord's per-SSRC speaking timer (packets, 200 ms timeout) |
| `turn.start` / `.tick` / `.end` | speaking smoothed over pauses < `TURN_GAP_MS`; a tick every `TURN_TICK_MS` while someone holds the floor |
| `transcript` | one streaming SLNG socket per Discord user, diarization on (`speaker` = voice within that user's audio — a room on one mic); names as keyterms. `STT_MODE=http` falls back to per-utterance chunks |
| `spoken` | a `speak` finished playing, was `stop`ped (`interrupted`), or failed (`error`) |
| `moderation` | a brain `mute` / `unmute` landed (`muted` with `until`, `unmuted`) or did not (`failed`, `error`); ears lifts every mute itself on its timer, on session end and on shutdown |

Every frame goes to three places: the WebSocket at `/`, Redis
(`XADD` + `PUBLISH gavel:ears:events`), and Postgres (`events`, plus `turns`,
`transcripts`, `participants`, `sessions`). The brain can also send `speak` / `stop` via
`PUBLISH gavel:ears:commands`.

The brain sends `speak` (with the exact `text` for the console, and `priority: true` to
jump the queue and duck the room as priority speaker), `stop`,
`mute {discordId, seconds}` (capped at 60 s) and `unmute`.

Or it streams a line while it is still being synthesized: `speak.start` (48 kHz
`pcm_s16le`, mono or stereo) queues and starts playing it, `speak.chunk`s feed raw PCM
as it arrives (a late chunk is bridged with silence), `speak.end` closes it. Same queue,
priority and `spoken` as `speak` — see `src/ears/pcm_stream.py`.

ears is also the brain's store — one Postgres for everything. The brain writes parked
points and notes per person (`/api/memories`), what the chair said (`/api/interventions`)
and every model call's tokens and cost (`/api/llm-calls`); each write shows up in the
console log as `memory.*` / `chair.*`.

HTTP: `GET /health`, `GET /api/status`, `/api/discord/servers`, `/api/meetings`,
`/api/sessions`, `POST /api/say`, `/api/memories`, `/api/interventions`, `/api/llm-calls`
— full list at the top of `src/ears/wire.py`, OpenAPI at `/docs`.

`just export-replay > ../contract/fixtures/replay.jsonl` turns the last recorded call into
the brain's replay fixture (plan chunk E4).

## Layout

| File | Does |
|---|---|
| `voice.py` | the only discord import. Join, sink, speaking, playback, receive watchdog |
| `app.py` | composition root: voice events → frames → wire/Redis/Postgres; playback queue |
| `turns.py`, `segmenter.py` | pure, clock-injected: turns and utterance chunking |
| `stt.py`, `audio.py` | SLNG over HTTP; 48k stereo → 16k mono WAV |
| `wire.py`, `console.html` | WebSockets (brain `/`, console `/live`), REST API, the console page |
| `meetings.py`, `tts.py` | agenda schema; SLNG TTS for the say-box |
| `status_board.py` | the live meeting-status message: brain `/state` → embed, edited in place |
| `bus.py`, `db/` | Redis; Postgres (queued writer, alembic migrations) |

## Speech-to-text

Streaming by default: each Discord user gets one SLNG WebSocket while they talk. The
model keeps context across a turn, finals land ~0.6-0.8 s after a pause, and
diarization labels stay stable within the stream, so two people sharing one account
come out as `speaker` "0" and "1". Discord sends no packets during silence, so ears
sends 1.2 s of zeros after each pause to let the model finalize; idle sockets close
after 45 s.

| `SLNG_STT_MODEL` | Notes (bake-off on two voices, one track) |
|---|---|
| `deepgram/nova:3` (default) | 0% WER, 2/2 voices, names via `keyterm`, endpointing 300 ms |
| `soniox/speech-ai:rt-v5` | same voices, digits for numbers, gets the meeting's title/purpose/context as vocabulary context |

`just stt-check --stream` replays two synthesized voices through the real path.
SLNG quirks found by probing (docs differ): Soniox config must have **no** `type`;
keepalive is `KeepAlive` for Nova and `keepalive` for Soniox; `finalize`/`close`
controls are rejected — end of speech is silence, end of stream is closing the socket.

The console log shows `voice.receive` every 5 s: packets decrypted (`ok`) vs dropped.
`dropped_dave_not_ready` means Discord's E2EE was still negotiating — ears drops those
frames rather than decoding ciphertext into noise (which is what garbled the first
lines of a call before).

## Why py-cord from a git commit

Discord enforces DAVE end-to-end encryption on voice. No released Python library
decrypts DAVE on **receive** yet: discord.py only sends, discord-ext-voice-recv is
unmaintained, and py-cord 2.8.1 itself warns receive is broken. `pyproject.toml` pins
py-cord PR #3159 (`fix/voice-rec-2`), which does. If it misbehaves in a real call,
`voice.py` is the only file to replace — `@discordjs/voice` 0.19 is the known-good
fallback behind the same `VoiceEvents` interface.

## Tuning

`TURN_GAP_MS` (1500), `TURN_TICK_MS` (10000), `UTTERANCE_GAP_MS` (800),
`CHUNK_MAX_MS` (15000), `CHUNK_MIN_MS` (400), `SILENCE_RMS` (60), `SLNG_STT_LANGUAGE` (en),
`SLNG_TTS_MODEL` (`deepgram/aura:2`) and `SLNG_TTS_VOICE` (`aura-2-thalia-en`) — the
say-box is Karen talking, so these stay in step with the chair's voice in the brain's
`config/models.yaml`.
