# chair — side B

The half that sits in the call. Joins the voice channel, keeps one decoded audio stream
per speaker, tracks who has the floor and for how long, and speaks up when the meeting
needs a chair.

Also serves the web stage: the agenda, the live talk-time bars, and the chair's
generated face. Discord does not allow bots to publish video, so the stage is a browser
page rather than a camera in the call.

Consumes the agenda from [../../docs/CONTRACT.md](../../docs/CONTRACT.md), emits call
events back to the Concierge.

Chunks B1–B9 in [../../docs/PLAN.md](../../docs/PLAN.md). **B1 first** — per-speaker
audio receive is the assumption everything else rests on, and Discord's voice receive is
undocumented enough that it deserves an hour of proof before anything is built on it.

## Env

`DISCORD_CHAIR_TOKEN`, `SLNG_API_KEY`, `NEBIUS_API_KEY`, `FAL_KEY`,
`CONCIERGE_WEBHOOK_URL`, `SEAM_SHARED_SECRET`.

## Build against a fixture

`packages/contract/fixtures/agenda.example.json` is a real agenda. Nothing here needs
the Concierge to exist.
