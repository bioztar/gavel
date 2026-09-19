# gavel — demo script (HackBarna, 20 Sep 2026)

Styled version, readable on a phone on stage: <https://gavel.pro7ocol.com/demo-script>

Target **6:00**, hard ceiling 7:00. Same script for the stage and for the submission
video — nothing in it depends on a live audience.

Four cold opens (§2). Everything after the open is identical in all four versions.

---

## 1. Pre-flight (do this before you stand up)

| # | Check | How |
|---|---|---|
| 1 | Policy overrides live | `CALENDAR_POLICY_OVERRIDES={"offAgendaGraceSeconds": 8, "requireStart": false}` — verified on the box: agenda goes out with 13 policy keys, grace **8**, requireStart **false**, gap **45** |
| 2 | Topic types in the confirm table | row 1 **presentation**, row 2 **discussion**, row 3 **presentation** |
| 3 | Must-hear on row 2 | `Vitaly, Artem` — without it the handover has nobody to hand to |
| 4 | Attendee map | 3 entries mapped; Vitaly and Artem must both be in it or Karen cannot match a Discord speaker to an attendee |
| 5 | Persona | formal |
| 6 | Tabs, in this order | `/compose` · mailbox · calendar · Discord · `/architecture` (slide 1 showing) |
| 7 | Second screen (optional, judges like it) | ears console — the live event feed shows each trigger firing by name |

**Why type matters:** in a `discussion` topic the brain's `floorHog` trigger fires at
≥45s of held floor with ≥60% of the last 120s. That is *you*, 45 seconds into your own
architecture walkthrough. `presentation` topics skip the trigger entirely — one person
holds the floor by design. Rows 1 and 3 are presentations for exactly this reason.

---

## 2. The four cold opens

Pick one. 12–18 seconds, then join the spine at §3. Screen: slide 1 of `/architecture`
in every version.

### A — Her voice first
*(Say nothing. Let Karen's voice be the first sound in the room — play the 7s clip, or
if running live, let the room sit in silence for three seconds first.)*

> **Karen (recorded):** "Vitaly, parked for later: pricing. Back to solution and
> architecture: what does the room need to understand first?"

> **You:** "That is an AI chair taking the floor off a human, mid-sentence. Everything
> in the next five minutes is how it got there — and I'm going to make it do that to me,
> live."

*Strongest with judges. Weakest if the room is still settling — needs quiet.*

### B — The one-line claim
> "Every meeting you have ever been in had an agenda. Nobody in the room was enforcing
> it, because the person who could is the person talking. We built the thing that does —
> it joins the call, it holds the agenda, and it interrupts. Including me. Watch."

*Safest. No dependencies. Use this one if the room is noisy or you are running late.*

### C — The cost
> "Pick any number you like for what a week of meetings costs your company — it is large
> and you already believe it. Here is the part nobody prices: every one of those meetings
> had an agenda, and not one had anyone whose job was to enforce it. That is not a
> note-taking problem. That is a missing role. We built it."

*Do not quote a statistic you cannot defend from the stage. This version wins the point
without one.*

### D — The prediction
> "In about three minutes I am going to go off-topic on purpose, in the middle of my own
> demo. I am not going to stop myself. Somebody else will. That is the product —
> everything else is plumbing."

*Highest tension, and it pre-sells the drift beat so the room is watching for it. Only
use it if you are confident the catch fires; it names the thing that must work.*

---

## 3. The spine (identical in all four versions)

| Clock | Beat | On screen | You say / do |
|---|---|---|---|
| 0:15 | **Dictate the meeting** | `/compose` | Hit the mic, speak the brief (§4, ~15s). "I am not filling in a form. I am telling it what the meeting is." |
| 0:35 | **Generate** | parse result | "That is a 70B model on Nebius turning speech into an agenda." |
| 0:45 | **The confirm table** | topic rows | Point at the **Type** column: "Row one and three are presentations — one person holds the floor on purpose. Row two is a discussion. She treats them differently, and you will see how." Point at **Must hear**: "These two both have to be heard on row two. That is a promise she will keep." |
| 1:05 | **Send** | success page | "Real invite, real .ics, real mailbox." |
| 1:15 | **Inbox → accept → calendar → join** | mailbox, calendar, Discord | Four clicks, one sentence each — never narrate silently. "Invite. Accepted. It is in my calendar with a join link. And the link is a Discord call." |
| 1:40 | **Karen opens the meeting herself** | Discord | Say nothing for 10 seconds. She reads the agenda unprompted — nobody typed "start". |
| 1:55 | **Topic 1 — architecture** | `/architecture` slide 1 | 60 seconds off the Hear / Think / Speak lanes. See §5 for the words. |
| 2:55 | **You drift, on purpose** | slide 1 still up | Slide into something adjacent and off-agenda (§6). Keep talking. |
| ~3:05 | **She catches you (8s grace)** | — | Let her finish. Then: "That was eight seconds. I did not cue her — and notice she parked it rather than binned it." |
| 3:20 | **Topic 2 — open discussion** | slide 1 or camera | "Artem, you have been building the Discord side — what breaks first at scale?" Then **stop talking.** No "mhm", no nodding noises — anything you say dilutes his share of the floor and delays her. |
| ~4:20 | **She takes the floor back** | — | She thanks Artem and hands it to you by name. Take one beat, then: "Sixty seconds, one voice, and the chair moved the floor. Nobody in this room had to be the person who interrupts." |
| 4:35 | **Topic 3 — roadmap** | slide 3 | 50 seconds (§7). |
| 5:25 | **Close** | slide 3 | §8. |

**Two timing rules that are not optional:**

- She will not speak twice inside **45 seconds** (`minSecondsBetweenInterventions`).
  Keep ≥45s between her opening line and your drift, or the catch lands late.
- Artem needs **~60 seconds of uninterrupted floor** for the handover to fire. Brief him:
  one answer, no pauses for agreement, keep going until she cuts in.

---

## 4. The dictation, verbatim

Speak this into `/compose` — it names everything the parser needs (start, duration,
topics, minutes, owner, must-hear, and which are presentations):

> "Karen, set up a meeting with Artem in fifteen minutes, fifteen minutes long, called
> gavel live demo. Three topics. One: solution and architecture, five minutes, I present
> it. Two: open discussion, six minutes — I want both Artem and me heard on it. Three:
> roadmap, four minutes, I present it."

If the parse comes back wrong, **do not re-record** — fix the row in the table and keep
moving. "The parse is a draft. The table is the contract." That line turns a miss into a
feature.

---

## 5. Topic 1 — the architecture, in 60 seconds

Off slide 1, left to right, one sentence per lane:

> "Three moves. **Hear** — she is in the Discord call as a participant, audio goes to
> SLNG for speech-to-text, turns land in Postgres and Redis.
>
> **Think** — this is the part people assume is a model and isn't. Whether to interrupt
> is plain code: who has held the floor, for how long, against the agenda's own budget.
> Deterministic, testable, and it runs every 250 milliseconds. Mastra and Nebius are only
> asked for the *words* — the decision was already made.
>
> **Speak** — text to speech back through SLNG, into the same call, and fal lip-syncs her
> face so there is someone to look at.
>
> Six containers behind Traefik. One of them knows what Discord is. That is the whole
> reason this moves to Teams."

Then drift.

---

## 6. The drift, verbatim

Something adjacent and plausible — the catch reads as real precisely because it is not
absurd:

> "…and honestly the interesting part is the cost curve, because once you are running
> six containers you start thinking about whether it is cheaper on a reserved instance or
> spot, and I priced this out against three providers last month, and the pricing pages
> are all deliberately incomparable — which is a whole separate rant, actually let me
> tell you about the egress fees…"

She will say something close to:

> **Karen:** "Vitaly, parked for later: cloud pricing. Back to solution and architecture:
> what does the room need to understand first?"

*(That is the fallback template. The model usually paraphrases it — same meaning, its own
words. If she paraphrases, say so: "she wrote that line just now, it is not a canned
string.")*

---

## 7. Topic 3 — roadmap, 50 seconds

Off slide 3:

> "Discord is a demo choice, not a product choice. One container knows what a voice call
> is — everything else is platform-agnostic by construction. Meet and Zoom adapters are
> the same shape of work. Teams is where this actually belongs: an add-on inside the
> suite where the calendar, the agenda and the org chart already live.
>
> And the category is not meeting notes. Notes are a record of what happened. This changes
> what happens — inside the hour, while it can still be fixed. Time governance, sitting on
> top of a calendar that already knows what the meeting was for."

---

## 8. Close, 25 seconds

> "So: I dictated a meeting, it sent a real invite, she opened the call herself, she
> caught me going off-topic in eight seconds, and she took the floor off the person who
> had held it for a minute and handed it to the person who hadn't spoken.
>
> Every one of those is a rule you already wanted enforced and nobody in the room can
> afford to enforce. That is the product. Thank you."

*(If time is short, cut everything after the first paragraph and land on "That is the
product.")*

---

## 9. Failure drills

| If | Then |
|---|---|
| STT mangles the brief | Fix the row in the table. "The parse is a draft, the table is the contract." Never re-record on stage. |
| She misses the drift | Keep going — do **not** wait on her. The discussion handover is the money beat and has a much wider margin. If she lands it late, name it: "45-second cooldown between interventions — she had just opened the meeting." |
| Email is slow | Keep a second tab with the invite already open. Never stand in silence watching a mailbox. |
| Her face does not render | Ignore it. The voice is the product; the face is garnish. Do not debug on stage. |
| Discord join fails | Join from `/m/<session id>` directly. |
| Artem gets interrupted early | That is still the demo working — say so and move on. |
| Everything falls over | `/architecture` is three slides and tells the story standing still. Talk over the deck and finish on time. |

---

## 10. What the panel changed

Four personas reviewed the beat list. What each flagged, and what it cost:

**Hackathon judge** — "I have seen forty demos today; six of them were a wrapper with a
system prompt." → The `Think` lane now says out loud that the interrupt decision is plain
code, not a model call, and that it runs at 250ms. The sponsor names land inside the
architecture sentence, not as a logo slide.

**Enterprise buyer** — "Why is this not a Teams feature in eighteen months?" → §7 answers
the wedge directly (the calendar and the agenda already exist; she acts *inside* the hour)
and names the category — time governance — so the comparison is not notes-bots.

**HN skeptic** — "So it is VAD plus a timer with a TTS voice." → Yes, and that is the
claim: the boring part is deterministic and testable, only the phrasing is generated.
Stated that way it converts the objection into the design. Also killed the invented
statistic in open C — an unsourced number is the one thing that loses this room.

**Demo director** — "You have 40 seconds of dead air on mailbox and Discord clicks." →
Every click now has its own sentence, and the pre-flight tab order removes the hunting.
Two beats where you must be silent (her opening, Artem's minute) are marked explicitly,
because silence is what makes both triggers fire on time.

---

## 11. Recording the submission video

Same script, three differences:

1. Use open **B** or **D** — they need no room quiet and no reaction.
2. Screen-record everything; a second angle on you is optional and adds nothing.
3. Do not re-take a Karen intervention that lands slightly late. A real one that fires at
   eleven seconds is worth more than a perfect one nobody believes.
