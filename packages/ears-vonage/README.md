# ears-vonage

The same job as `ears-discord`, on Vonage's Video API instead: own the call connection,
report who is speaking, play the chair's audio into the call. Speaks the identical wire
protocol, so `brain` cannot tell which one it is talking to.

This one is also where the chair gets a **face inside the call** — Vonage lets a
publisher use any `MediaStreamTrack` as its video source, which Discord does not allow
bots to do at all.

## Shape

It is a **web page**, not a headless service. The chair joins the session as an ordinary
participant — a browser tab open on the presenting laptop. No headless Chrome, no fake
media devices, no deployment. For a hackathon demo that is the whole trick.

```
  browser tab ("the chair")
    ├── subscribes to every participant   → audioLevelUpdated → speaking.start/end
    ├── publishes audio  (MediaStreamDestination fed by the brain's TTS)
    ├── publishes video  (canvas.captureStream() fed by fal frames)
    └── WebSocket to brain — same frames as ears-discord
```

## What makes it work

- **`subscriber.on('audioLevelUpdated')`** fires up to 60 times a second with
  `audioLevel` from 0 to 1.0, per subscriber. That is per-participant speaking detection,
  documented and supported, with no audio decoding anywhere. Threshold around 0.2 with
  hysteresis — raw values are noisy at 60 Hz, so require the level to hold above the
  threshold briefly before emitting `speaking.start`, and below it for longer before
  `speaking.end`. Those two timers are the only real tuning in this package.
- **Custom publisher sources.** `OT.initPublisher()` accepts a `MediaStreamTrack` as
  `audioSource` and as the video source. Audio comes from an `AudioContext`
  `MediaStreamDestination` the brain's TTS is played into; video from a canvas via
  `captureStream()`, painted with whatever fal returns.
- **Gotcha to respect at init:** never initialise with `audioSource: false` — a publisher
  created without an audio source can never gain one. And `setVideoSource()` only works
  on camera publishers, so to change the video later, replace the track on the existing
  canvas rather than calling it.

## Depth of API use

Vonage's track is judged partly on how deeply the API is used. Two cheap additions worth
having:

- **`session.signal()`** — push the agenda, the current topic and every intervention to
  all participants' UI, so the meeting state is visible in the call and not only on the
  stage.
- **Archiving** — record the session; the recording is also the demo video.

## Env

`VONAGE_APP_ID`, `VONAGE_SESSION_ID`, `VONAGE_TOKEN`, `EARS_WIRE_URL`, `FAL_KEY`.

Sessions and tokens are generated server-side. Vonage mentors are on site — get the
credentials early, it is a five-minute conversation that blocks a three-hour chunk.
