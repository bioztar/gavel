# ears-meet — the stenographer, in a Google Meet

The `ears` side of [docs/CONTRACT.md](../../docs/CONTRACT.md) for Google Meet. A real
Chromium on a virtual display joins the call as a participant; the DOM tells us who is
speaking, PulseAudio carries the room's audio out and the chair's voice in. The brain on
`ws://127.0.0.1:8787` cannot tell it from `ears-discord`.

Full design, live-run instructions and what is not yet proven: [docs/EARS-MEET.md](../../docs/EARS-MEET.md).

```
just setup          # uv sync + Playwright's Chromium (Xvfb/PulseAudio/ffmpeg: see the docs)
just login          # sign the bot's Google account into MEET_PROFILE_DIR, once, by hand
just run            # join MEET_URL, serve the brain on ws://127.0.0.1:$WIRE_PORT
just live-check     # join, print every frame, play a test tone, print a scorecard
just check          # ruff + pyright + pytest — no network, no Google account, no browser
```

## Layout

```
src/ears_meet/
  __main__.py     start Xvfb + PulseAudio, launch, join, serve the wire, tear down
  app.py          composition root: DOM events + audio in → contract frames out
  browser.py      Playwright: profile, launch flags, lobby, observer, self-check, stage
  selectors.py    EVERY Meet selector, with what it matches and how sure we are
  observer.js     injected MutationObserver: tiles, speaking indicators, captions
  speaking.py     the speaking-indicator debounce (DOM flicker → speaking.start/end)
  turns.py        turn.start/tick/end, as in ears-discord
  roster.py       participants + join/leave diffing
  captions.py     Meet live captions → attributed transcript frames
  attribution.py  which speaking span an STT segment belongs to
  pulse.py        null sinks, monitor capture, pacat playback, egress attachment checks
  stt.py, stt_stream.py, tts.py, audio.py   the SLNG path, same as ears-discord
  frames.py       the contract (copied; docs/CONTRACT.md is the source of truth)
  wire.py         ws:// for the brain, /live for the operator console, the HTTP store
  settings.py     pydantic-settings; credential settings are SecretStr and only ever NAMED
scripts/
  live_check.py   human-run integration: real meeting, frames on stdout, scorecard
  login.py        make the signed-in Chromium profile
  stub_brain.py   a printing brain that speaks a tone
tests/
  test_*.py       frames, debounce, turns, roster/captions/attribution, app, wire, browser
  conformance/    the Meet recordings and the brain-replay conformance test
```
