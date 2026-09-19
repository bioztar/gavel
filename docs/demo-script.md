# gavel — demo script (HackBarna, 20 Sep 2026)

Styled version, readable on a phone on stage: <https://gavel.pro7ocol.com/demo-script>

Target **6:30**, hard ceiling 7:00. Same script for the stage and for the submission
video — nothing in it depends on a live audience.

Four cold opens (§2). Everything after the open is identical in all four versions.

---

## 0. The one sentence this whole demo is making

> **Karen never writes your agenda. She refuses to work without one, and then she holds
> you to it.**

Four beats, in order, and they are one claim, not four features:

| | Beat | What it proves |
|---|---|---|
| 1 | **The gate** | Ask for a meeting with no agenda — she will not book it |
| 2 | **The invite** | Every topic ships with an owner and who must be heard: teeth *before* the call |
| 3 | **The drift catch** | Teeth *during* the call — on the person running the demo |
| 4 | **The floor handover** | The agenda's must-be-heard list is a promise she keeps |

Say the sentence in the open, prove it in the spine, say it again in the close. If a beat
falls over on stage, the sentence still lands — that is why it is written down first.

**Never claim the meetings people sit in have agendas.** They mostly don't. The point is
that they *should have*, and that nobody in the room is ever in a position to enforce one.

---

## 1. Pre-flight (do this before you stand up)

| # | Check | How |
|---|---|---|
| 1 | Policy overrides live | `CALENDAR_POLICY_OVERRIDES={"offAgendaGraceSeconds": 8, "requireStart": false}` — verified on the box: agenda goes out with 13 policy keys, grace **8**, requireStart **false**, gap **45** |
| 2 | The thin brief still gets refused | Say §4a into `/compose` once in rehearsal. It must come back with **no topic rows** and her pushback line. Measured 19 Sep: 5 different agenda-less briefs, 5 empty topic arrays |
| 3 | Topic types in the confirm table | row 1 **presentation**, row 2 **discussion**, row 3 **presentation** |
| 4 | Must-hear on row 2 | `Vitaly, Artem` — without it the handover has nobody to hand to |
| 5 | Purpose line | one sentence on the confirm page — it is the first thing an invitee reads |
| 6 | Invitees box | 3 addresses shown on the confirm page (page one is deliberately empty) |
| 7 | Attendee map | 3 entries mapped; Vitaly and Artem must both be in it or Karen cannot match a Discord speaker to an attendee |
| 8 | Persona | formal |
| 9 | Tabs, in this order | `/compose` · mailbox (showing the **HTML** invite, not a text preview) · calendar · Discord · `/architecture` (slide 1 showing) |
| 10 | Second screen (optional, judges like it) | ears console — the live event feed shows each trigger firing by name |

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

> **You:** "That is a chair taking the floor off a human mid-sentence. It can do that
> because it would not let this meeting be booked without an agenda in the first place.
> Next five minutes: how it got there — and I am going to make it do that to me, live."

*Strongest with judges. Weakest if the room is still settling — needs quiet.*

### B — The missing role
> "Most meetings get booked with a title, a time and nothing else. The few that do have
> an agenda have nobody enforcing it, because the person who could is the person talking.
> So we built a chair that will not let you schedule a meeting without an agenda — and
> then sits in the call and holds you to it. Including me. Watch."

*Safest. No dependencies, no numbers to defend. Use this if the room is noisy or you are
running late.*

### C — The refusal
> "In a minute I am going to ask for a meeting. Thirty minutes with Artem tomorrow at ten
> — a real request, the kind that goes out five times a day. It is going to say no,
> because I did not say what the meeting is for. That refusal is the product. What
> happens inside the call is the proof."

*Pre-sells the new lead beat and puts the strongest idea in the first ten seconds. Use it
when the tabs are ready and you are confident of the parse.*

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
| 0:15 | **Ask for a meeting the way you actually ask** | `/compose` | One empty box. Hit the mic, say §4a (~8s). "No form, no invitee list. This is how a meeting really gets booked — a sentence, and somebody else's calendar." |
| 0:28 | **She refuses** | pushback page | Read her line off the screen, out loud. Then: "It is not being awkward. That is ninety minutes of three people's time, and it wants to know what the ninety minutes buys. Nothing gets into a calendar through this without an agenda." |
| 0:50 | **Say what it is for** | `/compose` | Hit **say it again** on her pushback — mic, §4b (~18s). "Same box. This time I say what has to come out of it." (Use the link, never the browser Back button: this page is a POST result.) |
| 1:12 | **The table is the contract** | confirm table | Point at **Type**: "Rows one and three are presentations — one person holds the floor on purpose. Row two is a discussion. She treats them differently and you will see how." Point at **Must hear**: "Both of us have to be heard on row two. That is a promise she keeps." Point at **Invitees**: "Read off the brief. I can still fix it here." |
| 1:40 | **Send** | success page | "Real invite, real .ics, real mailbox." |
| 1:48 | **The invite is not what I dictated** | mailbox | Open it. "I dictated a paragraph. They get this: purpose in one line, every topic numbered, with an owner, a time budget, and who has to be heard on it. The agenda has teeth before anybody joins." |
| 2:15 | **Accept → calendar → join** | mailbox, calendar, Discord | Three clicks, one sentence each — never narrate silently. "Accepted. In my calendar with a join link. And the link is a Discord call." |
| 2:35 | **She opens the meeting herself** | Discord | Say nothing for 10 seconds. She reads the agenda unprompted — nobody typed "start". |
| 2:50 | **Topic 1 — architecture** | `/architecture` slide 1 | 50 seconds off the Hear / Think / Speak lanes. See §5. |
| 3:40 | **You drift, on purpose** | slide 1 still up | Slide into something adjacent and off-agenda (§6). Keep talking. |
| ~3:50 | **She catches you (8s grace)** | — | Let her finish. Then: "That was eight seconds. I did not cue her — and notice she parked it rather than binned it." |
| 4:05 | **Topic 2 — open discussion** | slide 1 or camera | "Artem, you have been building the Discord side — what breaks first at scale?" Then **stop talking.** No "mhm", no nodding noises — anything you say dilutes his share of the floor and delays her. |
| ~5:05 | **She takes the floor back** | — | She thanks Artem and hands it to you by name. One beat, then: "Sixty seconds, one voice, and the chair moved the floor. Nobody in this room had to be the person who interrupts." |
| 5:20 | **Topic 3 — roadmap** | slide 3 | 45 seconds (§7). |
| 6:05 | **Close** | slide 3 | §8, 25 seconds. |

**Cut lines, in the order to use them** (if you are past 4:30 at the handover):
drop the roadmap's middle paragraph → drop the architecture's `Speak` sentence → land on
the close's first paragraph and "That is the product." Never cut the refusal or the
invite; they are beats 1 and 2 of the one sentence.

**Two timing rules that are not optional:**

- She will not speak twice inside **45 seconds** (`minSecondsBetweenInterventions`).
  Keep ≥45s between her opening line and your drift — the spine gives you 65s, so do not
  claw it back by rushing the architecture.
- Artem needs **~60 seconds of uninterrupted floor** for the handover to fire. Brief him:
  one answer, no pauses for agreement, keep going until she cuts in.

---

## 4. The two dictations, verbatim

### 4a — The thin brief (the one she refuses)

> "Karen, set up a meeting with Artem tomorrow at ten. Thirty minutes."

Deliberately ordinary — a title, a time, a length. **Nothing about what it is for.** It
comes back with a purpose line, a start, a duration, and **zero topics**, which is what
trips the gate:

> **Karen:** "There's no agenda in that brief. Karen won't put a meeting in three people's
> calendars without one — what does this call have to decide? Name the topics below, with
> who owns each."

Note out loud that the boxes are still there: "She is not blocking me, she is asking the
one question the meeting needs. A chair that only says no is just an obstacle."

### 4b — The real brief

It names everything the parser needs — start, duration, topics, minutes, owner, must-hear,
and which are presentations:

> "Karen, set up a meeting with Artem in fifteen minutes, fifteen minutes long, called
> gavel live demo. Three topics. One: solution and architecture, five minutes, I present
> it. Two: open discussion, six minutes — I want both Artem and me heard on it. Three:
> roadmap, four minutes, I present it."

If the parse comes back wrong, **do not re-record** — fix the row in the table and keep
moving. "The parse is a draft. The table is the contract." That line turns a miss into a
feature.

---

## 5. Topic 1 — the architecture, in 50 seconds

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

## 7. Topic 3 — roadmap, 45 seconds

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

> "So: I asked for a meeting the way everybody asks for a meeting, and it said no. I said
> what it was for, and three people got an agenda with an owner on every line. It opened
> the call itself. It caught me going off-topic in eight seconds. And it took the floor
> off the person who had held it for a minute and gave it to the person who had not
> spoken.
>
> It never wrote my agenda. It refused to work without one, and then it held me to it.
> That is a role every company needs and nobody can afford to staff. Thank you."

*(If time is short, cut everything after the first paragraph and land on "It refused to
work without one, and then it held me to it.")*

---

## 9. Failure drills

| If | Then |
|---|---|
| She **accepts** the thin brief | "She took it — which tells you the parse is generous. The gate is the table: it still does not send until the agenda is filled." Fill it and move on. Measured 5/5 refusals on 19 Sep — never debug the gate on stage. |
| Nebius is down / parse returns nothing | Same pushback page, blank rows. Type the topics. "The model is a convenience. The table is the contract." |
| STT mangles the real brief | Fix the row in the table. "The parse is a draft, the table is the contract." Never re-record on stage. |
| The invite renders badly on the projector | Open the `.ics` instead — its DESCRIPTION carries the same agenda, owners included. |
| She misses the drift | Keep going — do **not** wait on her. The discussion handover is the money beat and has a much wider margin. If she lands it late, name it: "45-second cooldown between interventions — she had just opened the meeting." |
| Email is slow | Keep a second tab with the invite already open. Never stand in silence watching a mailbox. |
| Her face does not render | Ignore it. The voice is the product; the face is garnish. Do not debug on stage. |
| Discord join fails | Join from `/m/<session id>` directly. |
| Artem gets interrupted early | That is still the demo working — say so and move on. |
| Everything falls over | `/architecture` is three slides and tells the story standing still. Talk over the deck and finish on time. |

---

## 10. Pitch check

Validated against what actually works in a technical elevator pitch. Left column is the
rule; right column is where this script obeys it.

| Rule | Where |
|---|---|
| Open on a moment the room has lived, not a category | §2 B and C describe a meeting request everybody in the room sent this week |
| No number you cannot defend from the stage | The cost-of-meetings open was cut for exactly this — an unsourced statistic is the one thing that loses this room |
| One claim, stated inside the first 20 seconds | §0's sentence is the open in all four versions |
| Demonstrate the claim, never describe it | Every clause of §0 has a beat in §3 where it happens live |
| One idea per beat | Each spine row is one sentence out loud |
| Pre-empt the killer objection before it is asked | §5 says the interrupt decision is plain code at 250ms, not a model call — that is the "wrapper with a system prompt" objection answered before the Q&A |
| Concrete beats adjectives | 8 seconds, 250 ms, 45-second cooldown, 60-second floor, six containers — no "seamless", no "powerful" |
| Name the category and the wedge | §7: time governance, not meeting notes; Teams, where the calendar and the org chart already are |
| Tension then release, twice | Refusal → structured invite. Drift → catch. Both land inside 90 seconds of each other |
| Close by restating the claim, not by summarising features | §8's second paragraph is §0's sentence in the past tense |
| Fit the slot with room to spare | 6:30 against a 7:00 ceiling, with cut lines pre-chosen in §3 so cutting is not improvised |

### What the four-persona panel changed

**Hackathon judge** — "I have seen forty demos today; six of them were a wrapper with a
system prompt." → The `Think` lane says out loud that the interrupt decision is plain
code, not a model call, and that it runs at 250ms. Sponsor names land inside the
architecture sentence, not as a logo slide.

**Enterprise buyer** — "Why is this not a Teams feature in eighteen months?" → §7 answers
the wedge directly and names the category, so the comparison is not notes-bots.

**HN skeptic** — "So it is VAD plus a timer with a TTS voice." → Yes, and that is the
claim: the boring part is deterministic and testable, only the phrasing is generated.
Also killed the invented statistic that used to live in open C.

**Demo director** — "You have 40 seconds of dead air on mailbox and Discord clicks." →
Every click has its own sentence, the invite beat gives the mailbox something to *say*
instead of something to watch, and the two beats where you must be silent (her opening,
Artem's minute) are marked, because silence is what makes both triggers fire on time.

---

## 11. Recording the submission video

Same script, three differences:

1. Use open **B** or **C** — they need no room quiet and no reaction.
2. Screen-record everything; a second angle on you is optional and adds nothing.
3. Do not re-take a Karen intervention that lands slightly late. A real one that fires at
   eleven seconds is worth more than a perfect one nobody believes.
