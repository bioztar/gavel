# contract

The two shared things: the agenda schema and the ears↔brain wire. The prose version in
[../../docs/CONTRACT.md](../../docs/CONTRACT.md) is authoritative.

## fixtures

| File | For |
|---|---|
| `agenda.demo.json` | The agenda the demo actually runs. Short budgets so overrun fires inside a few minutes |
| `replay.jsonl` | Three-person baseline stream, including the explicit “Karen, start” instruction |
| `replay.offagenda.jsonl` | Six-minute meeting covering opening, silence, topic moves, tangent parking, escalation, and wrap-up |

The current fixtures are deterministic development recordings; E4 will replace/add a
real exported multi-person call. Keep them honest:
if the real ears emit a frame the fixture does not, add it.

Either side may add to this package. Renaming or removing anything is a conversation
with the other side first.
