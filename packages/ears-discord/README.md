# ears

Owns the Discord voice connection, exclusively. Joins the channel, reports who is
speaking, plays the chair's audio back into the call, and — once the spine is standing —
decodes per-speaker audio and transcribes it.

Makes no decisions. Never reads the agenda. Everything it knows goes out over the
WebSocket described in [../../docs/CONTRACT.md](../../docs/CONTRACT.md).

## Start here: E1

Before anything else, prove three things in one script:

1. The bot joins a voice channel.
2. `speaking start` / `speaking end` fire per user, with two people talking.
3. A WAV file plays into the channel and everyone hears it.

That is the whole foundation and it is the only genuinely unknown part of the build. An
hour, first thing. If it does not hold, say so immediately — the day's shape changes.

Note that (2) comes from the voice gateway's speaking state and needs no audio decoding.
Per-speaker Opus decode (E5) is a later, separate chunk with its own risks: one decoder
and jitter buffer per SSRC, never funnelled through a single player.

## Env

`DISCORD_EARS_TOKEN`, `DISCORD_GUILD_ID`, `SLNG_API_KEY` (E6 only), `WIRE_PORT`.

## Build against a stub brain

Thirty lines: accept the WebSocket, print every frame, send a `speak` with a canned WAV
every 30 seconds. Do not wait for the real brain to exist.
