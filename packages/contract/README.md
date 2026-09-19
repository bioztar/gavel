# contract

The two shared things: the agenda schema and the ears↔brain wire. The prose version in
[../../docs/CONTRACT.md](../../docs/CONTRACT.md) is authoritative.

## fixtures

| File | For |
|---|---|
| `agenda.demo.json` | The agenda the demo actually runs. Short budgets so overrun fires inside a few minutes |
| `replay.jsonl` | A recorded ears→brain stream — three people, one monologuing. The brain's offline development loop |

`replay.jsonl` is hand-built until `ears` records a real one (chunk E4). Keep it honest:
if the real ears emit a frame the fixture does not, add it.

Either side may add to this package. Renaming or removing anything is a conversation
with the other side first.
