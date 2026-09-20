# HANDOVER — gavel — 2026-09-20 10:20

## State: demo path live and proven; a complete synthetic first-pass submission video is built (6:45) and waiting for Vitaly to watch.

## Done this session (helm, on the Mac)
- Repo cloned to `/Users/alex/DEV/gavel` (the dir held a stray `private.key` and no git —
  key moved to `/Users/alex/DEV/_assets/gavel-secrets/private.key`, outside every repo).
- `.env` copied from the VPS samba share `/Volumes/dev/gavel/.env`, mode 600, gitignored.
- **`docs/recording-checklist.md`** — per-take shot list for the real recording: file names,
  clap sync, take 0 voice-clone sample, pre-flight from `demo-script.md` §1.
- **`scripts/video/`** — full synthetic video pipeline, see its README. Produces
  `/Users/alex/DEV/_assets/gavel-video/gavel-v1.mp4`, 6:45, 1920x1080.
  - Vitaly's voice = minimax clone `Voicedc785cd01789891341`, cloned from a 2-minute solo
    superwhisper recording. Artem = ElevenLabs "Brian". Karen = the product's own SLNG voice.
  - Screens are real: the gate and confirm pages were captured by driving the **live**
    `/compose` on gavel.pro7ocol.com headless. `/compose/send` was never called; the invite
    email was rendered locally through `render_invite_html`.
  - Karen's four interventions are real `veed/lipsync/v2` renders over `idle-formal.mp4`.
  - Trimmed to the 7:00 ceiling using demo-script §3's own cut lines plus `atempo=1.06`.

## In flight / next
1. Vitaly watches `gavel-v1.mp4` and calls what to change.
2. He re-records for real against `docs/recording-checklist.md`; `assemble.py`'s `SHOT_MAP`
   is where footage replaces the stand-ins.
3. Five frames carry an orange **PLACEHOLDER SHOT** badge — Discord call (×3), calendar
   accept, ears console. Those are the only shots with no real capture behind them.

## Blockers / needs human
- Submission target (URL, length cap, upload vs link) is still unknown — not in the repo.
- Artem's availability for the live floor-handover beat, if the real recording happens.

## Key files touched
- `scripts/video/*` — the pipeline (script.json is the spine; assemble.py is the cut)
- `docs/recording-checklist.md` — how to shoot the real one
- `/Users/alex/DEV/_assets/gavel-video/` — all media (audio, shots, karen, out, final mp4)
