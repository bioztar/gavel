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

**Documentation fixes we already know we owe**, before any tool tells us:

- [ ] `docs/CONTRACT.md` vs `packages/ears-discord/src/ears/frames.py` — the additive fields
      (`seq`, `final`, `turnId`, `speaker`, `confidence`) must match the code exactly.
- [ ] `.env.example` vs every setting actually read — `DISCORD_VOICE_CHANNEL_ID`, `STT_MODE`,
      `CHUNK_MAX_MS`, `TURN_GAP_MS` appear in code or README but not in `.env.example`.
- [ ] `README.md` still describes a `packages/chair` layout that no longer exists.
- [ ] The two new packages (`chair-video`, `calendar`) need their endpoints in `CONTRACT.md`.
- [ ] `fleet`-style docs list Vonage as forfeit in one place and core in another.

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
