# Working agreement

Two people, each running their own agents, one repo, thirteen hours. Most of what goes
wrong in this shape is not code — it is two sides editing the same file, or waiting on
each other, or discovering at 20:00 that they built different halves of different
products. These rules exist to make that impossible rather than unlikely.

## Ownership is by directory, and it is absolute

| Path | Who writes it |
|---|---|
| `packages/concierge/**` | side A only |
| `packages/chair/**` | side B only |
| `packages/contract/**` | either, but only after saying so out loud |
| `docs/**`, root files | either, small edits, commit immediately |

Nobody edits the other side's package. Not to fix a typo, not to unblock themselves. If
side B needs something changed in the Concierge, they ask. This is the whole reason the
seam is HTTP and not shared code.

## Branches

- `main` is always runnable. Both sides pull from it.
- Work on `a/<thing>` or `b/<thing>`. Merge to `main` yourself when your chunk works —
  no review gate, there is no time for one, and directory ownership means you cannot
  break the other side by merging.
- Pull `main` before you start a chunk and after the other side announces a merge.
- Never force-push `main`.

## Two Discord applications, not one

Side A's Concierge and side B's Chair are separate bots with separate tokens, in the
same guild. One process, two responsibilities, shared token is how you get two agents
fighting over one gateway connection at 19:00. Create both in the Discord developer
portal now.

The Chair needs the voice intents and to be in the voice channel. The Concierge needs
message and DM permissions. Neither needs the other's.

## Secrets

`.env` is gitignored and stays that way. **This repo is public** — the tracks require a
public repo with a README. Every key lives in `.env.example` as an empty name only.
Before any push, check the diff for anything key-shaped. A leaked Nebius or fal key in a
public repo on a hackathon weekend is a real and boring way to lose a morning.

## The seam is frozen early

[CONTRACT.md](CONTRACT.md) is agreed before either side writes code against it. After
that, additive changes are free and anything else needs both sides to say yes. The
agenda JSON is the single most important object in the build — if it is right, the two
halves compose even if everything around them is held together with tape.

## Mock the other side from minute one

Side A builds against a fake Chair: a 30-line HTTP server that accepts `POST
/v1/sessions` and returns canned state. Side B builds against a fixture `agenda.json`
committed in `packages/contract/fixtures/`. Neither side waits for the other, ever.
Integration at 19:00 is then a matter of changing a base URL, not of discovering what
the other person built.

## Talking to each other

- Every merge to `main` gets one line in the team chat: what landed, whether it changes
  the seam.
- One integration checkpoint at 19:00, everyone in a real voice call, full path run end
  to end. Not a status meeting — an actual run.
- The 20:00 cut line in [PLAN.md](PLAN.md) is binding on both sides.

## Commits

Conventional prefixes: `feat:`, `fix:`, `docs:`, `chore:`. Commit per working chunk, not
per file and not once at the end. At a hackathon the history is also the only record of
what was built during the event, which the rules care about.
