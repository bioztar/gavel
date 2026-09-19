# HANDOVER — gavel/chair-video — 2026-09-19 (latest)
## State: chair-video done-criteria complete and committed (80f7ffc). Mission ready for review.

## Done this session
- Persona pivot finished: formal/funky Karen, `POST /speak-video` + `GET /idle` both take
  optional `persona` (default `"formal"`, unknown value silently falls back — never 422).
- Regenerated funky Karen avatars after Vitaly flagged the first two passes as
  indistinguishable from formal (strength=0.6, then 0.8, both failed the "stranger test").
  Third pass at strength=0.9 (0.82 for one variant) with funky-first, concrete-material
  wording worked. See `packages/chair-video/avatars/PROMPTS.md`.
- Measured real latency for all 4 lip-sync candidates (3s/8s utterances). The original
  default (`longcat`, image-input) timed out on both runs — killed that architecture.
  Pivoted `/speak-video` to re-sync a persona's idle **video** loop via `veed/lipsync/v2`
  (fastest model that completed reliably: 41.4s/47.0s). Full table in
  `packages/chair-video/README.md`.
- Fixed the resulting breakage across `settings.py` (persona-parameterized methods),
  `cache.py` (persona in the cache key), `app.py` (persona normalization,
  `_persona_idle_url()` helper, `video_url`-shaped fal payload).
- Wrote `scripts/demo.py`, filled in README (latency table + persona note), added an
  additive chair-video section to `docs/CONTRACT.md`, wrote `tests/unit/` (fal queue/poll
  mocked, cache/settings persona logic, full app behavior) — 18 tests green, ruff + pyright
  clean. Committed as `80f7ffc`.
- Mission file (`helm/fleet/missions/20260919-gavel-chair-video.md`) Progress section and
  done-criteria checkboxes updated to match.

## In flight / partially done
- Nothing in chair-video is unfinished against the mission's done criteria.

## Next steps (ordered)
1. (Optional, lowest priority per mission) `minimax/h3-max/director` livestream-playability
   question — not started, only if time remains before freeze.
2. helm: review + merge `chair/video` branch (local-only mode — never pushed, never opened
   a PR, per mission constraints).

## Blockers / needs human
- None. Mission status should be set to `review`.

## Key files touched
- `packages/chair-video/src/chair_video/{app,settings,cache}.py` — persona-aware pipeline.
- `packages/chair-video/README.md` — latency table, persona mapping, config.
- `packages/chair-video/avatars/` — `karen-formal.png`, `karen-funky-0{1,2,3}.png`,
  `idle-formal.mp4`, `idle-funky.mp4` (old ambiguous `idle.mp4` removed).
- `packages/chair-video/tests/unit/` — new, 18 tests, fal fully mocked.
- `docs/CONTRACT.md` — additive chair-video section only, nothing else touched.
