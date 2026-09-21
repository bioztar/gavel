# Code analysis and evals — Quality Clouds, Galtea

Two different jobs. Quality Clouds looks at **our code**. Galtea looks at **what the chair
does**. Neither is on the critical path; both are cheap points if they fit.

## Quality Clouds — analysis of the repo

**Check this at the booth before spending an hour on it.** Their published product is a code
governance platform for **ServiceNow, Salesforce, Dynamics 365 and Magento** — their GitHub
Action is literally called *Build Check for Salesforce*, and the Git-repo connector is
documented under Salesforce setup. gavel is Python and vanilla JS, so the documented path may
simply not have rules for our stack.

So the first question is not "how do I install it", it is: **"do you have anything that scans a
plain Python/JavaScript repo, or is the platform Salesforce/ServiceNow only?"** Two outcomes:

- **They do** → API key from their Admin Portal, stored as a GitHub **repository secret**
  (never in the repo), plus their Action in `.github/workflows/quality.yml`, or connect
  `bioztar/gavel` as a Git instance in their portal. The repo is public, so anyone can scan it;
  no access grant needed beyond the key.
- **They do not** → say so in the submission rather than faking an integration. The honest
  substitute, which costs ten minutes and produces the same artefact: `ruff` + `mypy` + `bandit`
  over both packages, with the findings triaged in this file. Judges reward a real quality pass
  over a logo.

**What we do with the findings either way.** Every finding lands in one of three buckets, and
the documentation fixes are the ones worth chasing on a hackathon clock:

| Bucket | Action |
|---|---|
| Security / secret-shaped / injection | Fix immediately, no discussion |
| Documentation — missing docstring, stale README, an undocumented env var, a contract field that no longer matches the code | Fix in the same pass. These are the cheap ones and they are exactly what drifts fastest in a 13-hour build |
| Style / complexity / dead code | Note here, fix only after code freeze risk is zero |

**Documentation audit completed 2026-09-19:**

- [x] `docs/CONTRACT.md` matches the additive transcript, turn, moderation, persistence,
      exact-spoken-text, meeting-lifecycle, and brain-state fields used by the code.
- [x] `.env.example` includes the active brain/ears seam and `BRAIN_STATE_URL`; package
      READMEs document the remaining optional settings and defaults.
- [x] Root README reflects the actual `packages/brain` and `packages/ears-discord` layout
      and separates implemented sponsor integrations from planned ones.
- [x] Only packages that exist are described as implemented endpoints; Karen has no generated
      face, so no video-generation service is documented anywhere.
- [x] `HANDOVER.md`, `PLAN.md`, and `tasks.json` now reflect the implemented brain and UI.

**Local quality gate:** brain has 26 passing Vitest tests plus `tsc --noEmit`; ears has
41 passing pytest tests plus Ruff and Pyright with zero findings. The only test output is
two dependency deprecation warnings from Starlette's current TestClient stack.

## Galtea — evals of the chair

Galtea evaluates LLM systems: you define a test set, run your system against it, and score the
outputs. That maps onto gavel better than it looks, because the chair has exactly one
model-shaped output — **the sentence it says when a trigger fires** — and everything else is
deterministic.

The split that makes this worth doing:

- **The triggers are not an eval problem.** Whether the chair should interrupt is plain code,
  so it is tested with the replay harness: a scripted `replay.jsonl`, and an assertion that the
  floor-hog trigger fires at second 132 and not before. Unit tests, not Galtea.
- **The line it says is an eval problem.** Given the same state, is the sentence short, civil,
  specific about who and what, and does it actually ask for the floor back? That is a judgement
  call over generated text, which is what Galtea is for.

**Proposed test set** — ten cases, each a frozen state plus the trigger that fired:
floor hog at 62%, floor hog at 81%, topic 1.2× over budget, topic at risk with two left,
a `mustHear` attendee silent at 70%, 15 seconds of silence, the fire drill, crosstalk,
a monologue by the meeting's own host (does it still interrupt?), and an empty agenda.

**Scored on:** does it name the right person; is it under 20 words; does it hand the floor
somewhere specific; is it polite enough to be survivable in a real meeting; does it avoid
inventing content it never heard. That last one is the real risk with a model in this seat.

**Cheap version if Galtea's onboarding is slow:** the same ten cases, run through the same
prompt, scored by Nebius with a rubric, results in a markdown table. Same artefact, no signup.
Do the cheap version first; it is the thing that makes the Galtea run take twenty minutes
instead of two hours, because the test set already exists.

## Order of work

Both are **after** the spine. Quality Clouds only once there is code worth scanning — which
is now true for `ears-discord`. Galtea only once the chair produces lines, which is after the
brain's B7. Neither blocks anything, neither is allowed to block anything.

## The cheap version, built — `packages/brain/evals/`

The ten cases above exist, frozen, one JSON file each in `packages/brain/evals/cases/`. Each
one is a real `Agenda` plus the policy `Snapshot` fields at the instant the trigger fires, and
the expectation the case is for: which trigger and intervention kind, whose name belongs in the
line, and where the floor should land.

```
pnpm evals                     # offline: the YAML templates speak, judged dimensions not run
pnpm evals -- --model          # the real Nebius composer writes the lines
pnpm evals -- --model --judge  # the full scored pass
```

`--model` and `--judge` need `NEBIUS_API_KEY`; without it the run stops with
`NEBIUS_API_KEY is not set` before any call is made. The default needs no key and no network,
which is what keeps the table regenerable by anyone.

- `run.ts` puts each case through the chair's own code — `evaluate()` from
  `policy/triggers.ts` picks the intervention, `Engine.compose()` builds the line off
  `config/prompts/chair.yaml`. Nothing about the decision or the prompt is re-implemented here;
  only the clock, wire, store and TTS are stubs, as in `replay.ts`.
- `score.ts` is the five dimensions. Three are arithmetic and are counted in code against each
  case's own expectations: the word count, the right person named (and nobody wrongly singled
  out), the floor handed to a named person or a named agenda item. Two are judgement — polite
  enough to survive a real meeting, invents nothing it never heard — and go to a model through
  the `Judge` interface in `judge.ts`, holding the line to exactly the facts the prompt was
  given. With no judge they read "not run", never "pass".
- `results.md` is the table: one row per case, the line, the five scores, what failed.

Tests: `test/evalCases.test.ts` and `test/evalScore.test.ts`, both offline — the stub model and
a fake judge. No test touches the network.

What this does not do: it is not Galtea, there is no account and no SDK. If someone does run
Galtea later, the test set and the rubric it needs are already here.
