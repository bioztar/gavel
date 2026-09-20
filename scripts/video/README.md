# Submission video pipeline

Builds a complete run of `docs/demo-script.md` without a live call: every line is
synthesized, every screen is a real screenshot of the live service, and Karen's face is
the same fal lip-sync path the product uses on stage.

Outputs land in `/Users/alex/DEV/_assets/gavel-video/` (not in the repo — media).

| Step | Script | What it does |
|---|---|---|
| 1 | `script.json` | The spine: 21 segments, each with speaker, text and shot |
| 2 | `synth.py` | Vitaly = minimax voice clone, Artem = ElevenLabs, Karen = the product's own SLNG voice |
| 3 | `shots.py` / `shots2.py` | Drives the live `/compose` flow headless and screenshots the gate, the confirm table and the gauge. Never calls `/compose/send` |
| 4 | `invite_shot.py` | Renders the invite email locally with `render_invite_html` — no mail is sent |
| 5 | `karenface.py` | `veed/lipsync/v2` over `avatars/idle-formal.mp4` for each of Karen's four lines |
| 6 | `overlays.py` | Speaker labels and PLACEHOLDER badges as transparent PNGs — this ffmpeg has no `drawtext` |
| 7 | `assemble.py` | Ken Burns per shot, Karen picture-in-picture, `atempo` trim to fit 7:00, concat |

```
cd packages/chair-video && GAVEL_ENV_FILE=/path/to/gavel/.env FAL_POLL_TIMEOUT_S=420 \
  uv run python ../../scripts/video/synth.py      # then karenface.py
cd ../.. && uv run --with playwright python scripts/video/shots.py
python3 scripts/video/assemble.py
```

**Voice clone id** `Voicedc785cd01789891341` — minimax, cloned from a 2-minute solo
superwhisper recording. Re-clone against a fresh sample recorded on the video's own mic
before any take that has to blend with real narration.

**Shots that are stand-ins** (Discord call, calendar accept, ears console) carry an orange
PLACEHOLDER badge on screen. They are the frames to replace with real capture.
