# Cloture — the investor pitch

*Cloture — the motion that cuts off debate. 4 minutes. Karen opens from inside a live Google
Meet, you carry, Karen cuts you off to close.*

> **The one sentence the whole pitch makes:** Karen never writes your agenda. **She refuses to
> work without one, and then she holds you to it — including on the person pitching her.**

Say it in the open. Prove it in the middle. She says it back to you in the close. If any beat
falls over on stage, the sentence still lands.

## The shape

| Time | Who | Beat | Proves |
|---|---|---|---|
| 0:00–0:30 | **Karen** | Takes the floor before you speak | She is not a slide |
| 0:30–1:10 | You | The moment everyone has lived | The problem is theirs |
| 1:10–2:00 | You | What she just did, and why it isn't a wrapper | Defensible tech |
| 2:00–2:50 | You | Wedge, distribution, who pays | It's a business |
| 2:50–3:30 | You | Deliberate drift — keep talking past your point | Sets the trap |
| 3:30–3:55 | **Karen** | Interrupts mid-sentence, closes, hands back | The claim, live, on you |

## 1 · Karen opens — 0:00

> "Stop. This session has **no agenda on file**, and I do not let meetings start without one.
>
> I'm Karen. I chair meetings. Vitaly filed one four minutes long, three points, and an ask at
> the end. **He is not exempt from it.** I'm holding the clock.
>
> Vitaly — you have three minutes twenty-five. Go."

**You stay silent.** The silence is the demo. Don't nod, don't smile at the screen, don't say
"thanks, Karen". Let the room work out that nobody cued her.

## 2 · You carry — 0:30

**The moment (0:30)**

> "Every one of you was in a meeting this week where the first ten minutes were people working
> out what the meeting was for.
>
> Nobody in that room can fix it. Not the most senior person — **especially** not the most senior
> person, because the one who overruns is usually the one who called it.
>
> There is **no authority in the room** whose job is the clock. That's the gap. She's it."

**Why it isn't a wrapper (1:10)**

> "What she just did is the whole product, so let me take the obvious shot at it myself.
>
> The decision to cut someone off is **not a model call**. It's ordinary code, running four times
> a second: who has the floor, how long they've had it, what the agenda promised. Deterministic,
> testable, fails the same way twice.
>
> The model writes **one thing** — the sentence she says out loud. Take the model away and she
> still chairs the meeting; she just does it rudely."

**Wedge, distribution, who pays (2:00)**

> "We are not a notes bot. Notes are what you read **after** the meeting already went badly. This
> is **time governance** — it acts during, and it acts before.
>
> Before is the important half. The gate isn't in the call, it's at the moment you book: a browser
> extension on the calendar you already use. **No agenda, no invite.** The teeth are in the booking
> flow, which is why this isn't a feature you bolt on later.
>
> She joins as a participant, not as a platform integration — Meet today, Zoom and Teams the same
> way, because the part that decides never imports a call SDK. **One brain, thin ears.** Who pays:
> anyone who pays salaries and buys back the hours."

**The drift, on purpose (2:50)**

> "...and on the architecture side, once you're running containers per call you end up comparing
> reserved against spot, and I priced three providers last month and their pages don't line up at
> all, and then egress on top of that, and honestly the whole..."

**Keep going.** Don't wind down, don't glance at the screen, don't leave a gap for her. She has to
take it off you. If you trail off politely the beat dies.

## 3 · Karen closes — 3:30

> "Vitaly. **That's your four minutes, and cloud pricing was not one of your three points.**
>
> I didn't write his agenda. He wrote it, I refused to book the meeting until he did, and then I
> held him to it — **in front of the people he's asking for money.**
>
> The agenda says the last item is the ask. Vitaly — **ask.**"

Then you say the ask, in one sentence, and stop talking.

## 4 · If it breaks on stage

| What fails | What you say | Then |
|---|---|---|
| She never joins | "She won't start a meeting that isn't ready. Fair enough." | Play the recorded run — one keystroke away |
| She joins, stays silent | Carry on; at 3:30 cut yourself off: "— and she'd stop me right there." | Claim survives, you delivered her line |
| Audio broken one way | Read her line off the shared board out loud | The board shows the interrupt |
| She interrupts too early | "That's the setting. High. Nobody's exempt." | Take the ask early |

**Rule:** never apologise for her. Every failure above is in character for a strict chair. The
recording is the only real fallback — have it open.

## 5 · Investor questions, pre-loaded

| They ask | You answer |
|---|---|
| "Why isn't this a Google/Zoom feature in a year?" | They ship notes, not authority. The gate is at booking, in the calendar — and a neutral third party is the point. A platform can't chair against its own customer's boss. |
| "What's the moat?" | The boring half: a deterministic chairing engine with a frozen seam, adapters per platform. Not the prompt — the prompt is deliberately the replaceable part. |
| "Will people accept being interrupted?" | They accept it from the agenda they wrote. That's why she never writes it. Strictness is a dial, per meeting. |
| "Isn't it VAD plus a timer plus TTS?" | Yes. That's the claim. The deterministic part is the product; generated phrasing is the surface. |
| "Where is it today?" | Discord end-to-end, Meet built and running, the booking extension against a mock. See `status.html`. |

## 6 · What must be true before you walk on

**Blocking — Google Meet has never run in a real call.**

- **Only you can do this:** `just login` on a machine with a screen, signed in as Karen's Google
  account. The profile directory *is* the credential.
- **Only you can do this:** a second human in the rehearsal call. Meet misbehaves with one participant.
- A Linux host with PulseAudio. **Now unblocked:** the container ships it, so this runs in Docker on
  the VPS — no root on the host needed.
- **Record the rehearsal.** That recording is the §4 fallback and it is not optional.

**Rehearse these three, in order:** she takes the floor cold with no cue · she cuts you off mid-word
during the drift (practise not stopping) · the handover — she says "ask", you have it in one sentence.

---

Cloture · `bioztar/gavel` (repo, unchanged). Build status: [status.md](status.md) ·
architecture: [blueprint.md](blueprint.md) · older HackBarna run sheet: [demo-script-full.md](demo-script-full.md).
