# Persona replay proof

Same fixture (`packages/contract/fixtures/replay.offagenda.jsonl`), same engine, same
intervention sequence and timings — only the persona differs. Both runs use `--stub-llm`
(no network calls) so every line shown is a template, chosen by the same deterministic
rotation in both runs. Real output below, pasted verbatim.

Run commands:

```
CHAIR_PERSONA=formal pnpm replay ../contract/fixtures/replay.offagenda.jsonl --stub-llm
CHAIR_PERSONA=funky  pnpm replay ../contract/fixtures/replay.offagenda.jsonl --stub-llm
```

## Formal Karen

```
00:50  silence       [template] Vitaly, we haven't heard from you on Where we actually are yet. What is not done that you expected to be done?
01:48  topicOverrun  [template] We're over time on Where we actually are, so let's move on to The date. What date can you defend?
02:41  offAgenda     [template] Vitaly, good point, I've parked honestly pricing page need full redesign for later. Let's get back to The date. What date can you defend?
03:01  escalateFirm  [template] Vitaly, I need to stop you there. We have to get back to The date. What date can you defend?
04:12  topicOverrun  [template] The date is over budget. Moving to Blocker owners. What's your take on Blocker owners?
05:03  silence       [template] Vitaly, let's hear from you. What's your take on Blocker owners?
06:00  wrapUp        [template] That's the agenda, thank you all. Parked for later: Vitaly on honestly pricing page need full redesign.

— talk time (s) —
Vitaly     total  100
Ana        total  104
Marc       total   72

— parked —
Vitaly: honestly pricing page need full redesign
```

## Funky Karen

```
00:50  silence       [template] Vitaly, you've been suspiciously quiet on Where we actually are. What is not done that you expected to be done?
01:48  topicOverrun  [template] Where we actually are just got a red card for overtime. Onward to The date. What date can you defend?
02:41  offAgenda     [template] Vitaly, I've bagged honestly pricing page need full redesign for later — the agenda's a little jealous. Back to The date: What date can you defend?
03:02  escalateFirm  [template] Vitaly, cutting in — The date filed a missing-persons report. What date can you defend?
04:12  topicOverrun  [template] The clock beat The date. Say hello to Blocker owners. What's your take on Blocker owners?
05:03  silence       [template] Vitaly, is that you on mute or just enjoying the quiet? What's your take on Blocker owners?
06:00  wrapUp        [template] That's a wrap, team — thanks for showing up and behaving mostly on schedule. Parked for later: Vitaly on honestly pricing page need full redesign.

— talk time (s) —
Vitaly     total  100
Ana        total  104
Marc       total   72

— parked —
Vitaly: honestly pricing page need full redesign
```

Same 7 interventions, same timing, same talk-time and parked-item numbers (the engine's
decisions don't change) — only the words do. Formal states the fact and hands the floor
back; funky lands one line of situational humor first, never aimed at a participant.
