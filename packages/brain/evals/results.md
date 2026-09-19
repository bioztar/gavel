# Chair eval results

Ten frozen chair states (`evals/cases/`) through the chair's own trigger and prompt path, scored against the rubric in [QUALITY.md](../../../docs/QUALITY.md). Regenerate with `pnpm evals`.

Generated: 2026-09-19 · lines: offline, YAML templates · judged dimensions **not run**

| Case | Trigger | Generated line | names the right person | under 20 words | hands the floor somewhere specific | polite enough for a real meeting | invents nothing | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Floor hog at 62%<br><sub>`01-floor-hog-62`</sub> | `floorHog`<br><sub>floorHog</sub> | Thanks Vitaly, love the passion. Marc, floor's yours before this becomes a podcast. What is not done?<br><sub>[template]</sub> | pass | pass | pass | — | — | — |
| Floor hog at 81%<br><sub>`02-floor-hog-81`</sub> | `floorHog`<br><sub>floorHog</sub> | Thanks Vitaly, love the passion. Ana, floor's yours before this becomes a podcast. What date can you defend?<br><sub>[template]</sub> | pass | pass | pass | — | — | — |
| Topic 1.2x over budget<br><sub>`03-topic-over-budget`</sub> | `topicOverrun`<br><sub>topicOverrun</sub> | The date just got a red card for overtime. Onward to Blocker owners. What's your take on Blocker owners?<br><sub>[template]</sub> | pass | pass | pass | — | — | — |
| Topic at risk with two agenda items left<br><sub>`04-topic-at-risk-two-left`</sub> | `topicOverrun`<br><sub>topicOverrun</sub> | Where we actually are just got a red card for overtime. Onward to The date. What date can you defend?<br><sub>[template]</sub> | pass | pass | pass | — | — | — |
| A mustHear attendee silent at 70% through the meeting<br><sub>`05-musthear-silent-70pct`</sub> | `silence`<br><sub>silence</sub> | Ana, you've been suspiciously quiet on The date. What date can you defend?<br><sub>[template]</sub> | pass | pass | pass | — | — | — |
| 15 seconds of silence<br><sub>`06-silence-15s`</sub> | `silence`<br><sub>silence</sub> | Vitaly, you've been suspiciously quiet on Blocker owners. What's your take on Blocker owners?<br><sub>[template]</sub> | pass | pass | pass | — | — | — |
| The fire drill<br><sub>`07-fire-drill`</sub> | `offAgenda`<br><sub>offAgenda</sub> | Marc, I've bagged the building fire drill at four; the agenda's jealous. The date: What date can you defend?<br><sub>[template]</sub> | pass | pass | pass | — | — | — |
| Crosstalk<br><sub>`08-crosstalk`</sub> | `groupOffAgenda`<br><sub>offAgenda</sub> | Everyone, I've parked vendor pricing tiers for later. Back to Where we actually are: What is not done?<br><sub>[template]</sub> | pass | pass | pass | — | — | — |
| A monologue by the meeting's own host<br><sub>`09-host-monologue`</sub> | `floorHog`<br><sub>floorHog</sub> | Thanks Vitaly, love the passion. Marc, floor's yours before this becomes a podcast. What's your take on Blocker owners?<br><sub>[template]</sub> | pass | pass | pass | — | — | — |
| An empty agenda<br><sub>`10-empty-agenda`</sub> | `floorHog`<br><sub>floorHog</sub> | Thanks Vitaly, love the passion. Marc, floor's yours before this becomes a podcast.<br><sub>[template]</sub> | pass | pass | pass | — | — | — |

## What each case is for

- **Floor hog at 62%** (`01-floor-hog-62`) — Just over the 0.6 share threshold. The mildest hog in the set: the line has to hand over without making Vitaly sound scolded, and Marc is the mustHear who has not spoken on this topic.
- **Floor hog at 81%** (`02-floor-hog-81`) — The judged moment from the README, on topic two. Four fifths of the window is one voice; Ana is the mustHear who has not been heard on the date yet.
- **Topic 1.2x over budget** (`03-topic-over-budget`) — Topic two's 120 s budget times the 1.2 overrun factor, to the second, with the room quiet. One item is left, so the move is to 'Blocker owners' and its fallback question.
- **Topic at risk with two agenda items left** (`04-topic-at-risk-two-left`) — Topic one is over budget while two thirds of the agenda is still unstarted — the failure mode the product exists to stop. Read 'at risk' as: the overrun has fired and two items are still waiting, so the line must move the room on quickly instead of summarising.
- **A mustHear attendee silent at 70% through the meeting** (`05-musthear-silent-70pct`) — 210 s into a 300 s meeting, Ana is a mustHear on 'The date' and has not said a word on it. The room has gone quiet, so the invitation must be hers and must carry the topic's own question.
- **15 seconds of silence** (`06-silence-15s`) — Dead air at exactly the silenceSeconds threshold on the last topic, which has no questions of its own — so the chair has to open with the rendered fallback question and invite the topic owner without inventing an item.
- **The fire drill** (`07-fire-drill`) — Marc has been off the agenda for longer than the grace period, but what he is off about is the building's fire drill at four. The policy parks it like any tangent; the eval asks whether the line stays civil about a real-world interruption and parks it without dismissing it or inventing a plan for it.
- **Crosstalk** (`08-crosstalk`) — Two people have taken the room into the same tangent and both still hold the floor. The group redirect exists so nobody is singled out: naming one of them is the failure this case catches.
- **A monologue by the meeting's own host** (`09-host-monologue`) — Vitaly is the host and the owner of this topic, and has 88% of the window. The policy has no exemption for hosts, so yes, it still interrupts — this case checks it does, and that the line stays respectful of the person who called the meeting.
- **An empty agenda** (`10-empty-agenda`) — A session with attendees and no topics and no stated purpose: the chair has nothing to steer by. The floor-hog trigger still fires, but topicTitle and question are empty — so every noun in the line has to come from the room. Inventing an agenda item here is the worst failure in the set.

## Reading the scores

- *names the right person*, *under 20 words* and *hands the floor somewhere specific* are counted in code (`evals/score.ts`) against each case's expectations — never asked of a model.
- *polite enough for a real meeting* and *invents nothing* are judged by the model and read `—` until someone runs `pnpm evals -- --model --judge` with a key.
