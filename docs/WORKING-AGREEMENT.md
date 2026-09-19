# Working agreement

Two people, each running their own agents, one repo, thirteen hours. What goes wrong in
this shape is rarely code — it is two sides editing one file, or waiting on each other,
or finding at 21:00 that they built halves of different products. These rules make that
impossible rather than unlikely.

## Ownership is by directory and it is absolute

| Path | Who writes it |
|---|---|
| `packages/ears/**` | the voice owner |
| `packages/brain/**` | the moderation owner |
| `packages/concierge/**` | whoever picks it up, if anyone does |
| `packages/contract/**` | either, but say so out loud first |
| `docs/**`, root files | either, small edits, commit immediately |

Nobody edits the other's package. Not to fix a typo, not to unblock themselves. That is
the entire reason the seam is a WebSocket and not a shared module.

## Neither side ever waits for the other

- **brain** runs against `packages/contract/fixtures/replay.jsonl` from minute one. The
  whole policy — talk-time, triggers, the sentence, the stage — is developed and demoed
  with no Discord, no voice channel, no second person.
- **ears** runs against a stub brain: accept the WebSocket, print frames, send a `speak`
  with a canned WAV every 30 seconds. Thirty lines.

Integration is then changing a URL, not discovering what the other person built.

## The split is for development, not deployment

On stage both halves run on **one machine** — whoever is presenting. Two processes, one
laptop, one `npm start` each, localhost WebSocket between them. Nobody deploys anything
and nobody depends on venue wifi holding a connection between two laptops. Decide whose
machine at 16:00, not at 22:00.

## Two Discord applications, not one

If the Concierge ever gets built it is a **separate bot with its own token**. One process
with a shared token is how two agents end up fighting over one gateway connection at
19:00. The `ears` bot needs the voice intents; the Concierge needs messages and DMs.

## Branches

- `main` is always runnable. Both sides pull from it.
- Work on `ears/<thing>` or `brain/<thing>`. Merge to `main` yourself when the chunk
  works — no review gate, there is no time, and directory ownership means you cannot
  break the other side by merging.
- Pull `main` before starting a chunk and after the other side announces a merge.
- Never force-push `main`.

## Secrets

**This repo is public** — the sponsor tracks want a public repo with a README. `.env` is
gitignored and stays that way; `.env.example` holds names with empty values. Check the
diff for anything key-shaped before every push. A leaked Nebius or fal key on a
hackathon weekend is a boring way to lose a morning.

## Talking to each other

- One line in chat per merge to `main`: what landed, whether it touches the contract.
- Integration checkpoint at **16:00** — both people, one real voice call, real interrupt
  end to end. Not a status update, an actual run.
- The **21:00 cut line** in [PLAN.md](PLAN.md) binds both sides.

## Commits

`feat:`, `fix:`, `docs:`, `chore:`. Commit per working chunk, not per file and not once
at the end. The history is also the only evidence of what was built during the event,
which the rules care about.
