# brain

Every decision gavel makes. Holds the agenda, tracks who has held the floor and for how
long, decides when the meeting needs a chair, writes the sentence, turns it into speech,
and serves the web stage.

**Never imports discord.js.** Its entire input is the frame stream defined in
[../../docs/CONTRACT.md](../../docs/CONTRACT.md), which means it can be developed,
tested and demoed with no voice channel in sight.

## Start here: the offline loop

`packages/contract/fixtures/replay.jsonl` is a recorded meeting — three people, one of
them monologuing. Replay it through the state machine and watch the policy fire. That
loop is the fastest feedback in the build; get it running before anything is wired to
Discord.

## The rule that matters

Deterministic triggers decide **whether** to speak. The model decides only **what to
say**, and always has a template fallback — a slightly generic sentence delivered on
time beats a clever one that arrives after the moment has passed.

Thresholds live in the agenda's `policy` block so they can be tuned on stage without a
redeploy.

## Env

`NEBIUS_API_KEY`, `NEBIUS_BASE_URL`, `NEBIUS_MODEL`, `SLNG_API_KEY`, `FAL_KEY`,
`EARS_WIRE_URL`, `STAGE_PORT`.
