# gavel — your lines, to read out

Cold open **A**: Karen speaks first. You answer her.

Your parts total about **4:32**; the whole thing runs **6:18** with Karen and Artem in it.

Lines in *italics* are not yours — they are the cue to start talking.

---

> *Karen — title card · 8s*
>
> *Vitaly, parked for later: cloud pricing. Back to solution and architecture. What does the room need to understand first?*

## 1. architecture — slide 1 · 11s

That is an AI chair, and it just took the floor off me in the middle of my own sentence. It can do that because it would not let this meeting be booked without an agenda in the first place. Let me show you how that works.

## 2. /compose · 10s

I ask for a meeting the way I normally ask for one. Karen, set up a meeting with Artem tomorrow at ten. Thirty minutes.

> *Karen — the refusal page · 10s*
>
> *There's no agenda in that brief. Karen won't put a meeting in three people's calendars without one. What does this call have to decide? Name the topics below, with who owns each.*

## 3. the refusal page · 12s

A title, a time, a length. Nothing about what the meeting is for. So she will not book it. She still gives me the box to fix it, right there. She asks for the agenda instead of just saying no.

## 4. /compose · 19s

So I tell her. Karen, set up a meeting with Artem in fifteen minutes, fifteen minutes long, called gavel live demo. Three topics. One, solution and architecture, five minutes, I present it. Two, open discussion, six minutes, and I want both Artem and me heard on it. Three, roadmap, four minutes, I present it.

## 5. the agenda table · 13s

She comes back with three topics. Each one has an owner, a number of minutes, and a type. Topic two is a discussion, and it says who has to be heard on it. Artem and me. If she got a row wrong, I just fix the row.

## 6. the enforcement dial · 16s

Then I choose how hard she chairs. Low, medium, high. On medium she waits for a pause. On high she cuts in mid-sentence, and she can mute someone who ignores a warning. Nobody is exempt. If I am the one running over, she chairs me. I am putting this on high.

## 7. the invite email · 14s

Send. That is a real invite, a real calendar file, a real inbox. I dictated a paragraph. What everyone gets is this. The purpose on one line, every topic numbered, with an owner, its minutes, and who has to speak on it.

## 8. calendar / the invite · 8s

I accept it, and it lands in my calendar. There are two links inside. One takes me into the Discord call. The other one opens the meeting room.

## 9. the meeting room · 20s

This is the room, and this is the page you put on the shared screen. Karen is on the left with the agenda under her. Topic one is already crossed off. On the right is whatever is running right now, how much of its six minutes it has used, and who is doing the talking. Along the bottom: what got decided, what is still open, and anything she parked.

> *Karen — the meeting room · 11s*
>
> *Good afternoon. This is gavel live demo, fifteen minutes, three topics. First: solution and architecture, five minutes, presented by Vitaly. Vitaly, the floor is yours.*

## 10. the meeting room · 3s

Nobody typed start. She opened the meeting herself.

## 11. architecture — slide 1 · 33s

Three parts. She sits in the Discord call the same way a person does. The audio goes out to speech to text, and the turns land in Postgres and Redis. Then the decision to interrupt, which is ordinary code. It looks at who has held the floor, for how long, against the minutes on the agenda, and it runs four times a second. The model is only asked to write the sentence she says. Her speech goes back into the same call, and fal moves her face so there is someone to look at. Six containers. One of them knows what Discord is, which is why putting this into Teams is a realistic job.

## 12. architecture — slide 1 · 17s

And the really interesting thing here is the cost, because once you are running six containers you start looking at reserved instances against spot, and I compared three providers last month, and their pricing pages are impossible to line up, and then there are egress fees on top, which honestly deserve their own talk...

> *Karen — architecture — slide 1 · 8s*
>
> *Vitaly, parked for later: cloud pricing. Back to solution and architecture: what does the room need to understand first?*

## 13. the meeting room · 8s

Eight seconds, and I did not cue her. She parked the topic rather than dropping it, and she wrote that sentence herself just now.

## 14. the meeting room · 4s

Artem, you have been building the Discord side. What breaks first at scale?

> *Artem — the meeting room · 61s*
>
> *The voice connection, before anything else. Discord gives you one gateway per server, and the audio comes in as separate packets per speaker. So the first thing that struggles is not the model, it is decoding four people at once and keeping their streams apart. Right now we buffer each speaker and hand over one clean stream each, and for six people in a room that is fine. At thirty it stops being fine, because transcription cost goes up with every speaker. So we would detect speech on the edge and only transcribe whoever has the floor. Second thing is the tick. The brain checks the agenda four times a second, and that part is cheap, but every check reads the last two minutes of turns out of Redis. At a hundred meetings at once we would hold that window in memory and write through. And the third one nobody expects: reconnects. Discord drops the voice socket now and then, and if you come back without the floor state, the chair forgets who has been talking and goes quiet exactly when you need it.*

> *Karen — the meeting room · 6s*
>
> *Thank you Artem. Vitaly, you have not spoken on this topic yet, and the agenda says you must be heard. Your turn.*

## 15. the meeting room · 8s

One person talked for a minute, and she moved the floor without anyone asking her to. The board was tracking the share the whole time.

## 16. roadmap — slide 3 · 34s

Discord is where we built it. It is not where it belongs. Only one container knows what a voice call is, so Meet, Zoom or Teams is the same piece of work again. Teams is the one worth doing, because the calendar, the agenda and the org chart are already sitting there. The other half is what happens after the call. Everything she collected, the transcript, the decisions, the open items, should go straight into whatever the company already uses to keep its knowledge. She plugs into the team's own agent and hands it the result. And a notes tool writes the meeting up afterwards. This one fixes the meeting while it is still running.

## 17. roadmap — slide 3 · 33s

So I asked for a meeting the way everyone asks for a meeting, and it said no. I told it what the meeting was for, and three people got an agenda with an owner on every line. It started the call itself. It caught me going off topic in eight seconds. And it took the floor off the person who had held it for a minute and gave it to the person who had not spoken. It never wrote my agenda. It refused to work without one, and then it held me to it. Every company needs someone doing that job, and nobody can afford to pay a person to do it. Thank you.

---

## While recording

- Do not re-take one of Karen's interventions for landing a second late. A real one at
  eleven seconds beats a perfect one nobody believes.
- If the parse comes back wrong, fix the row on screen and keep going. Never re-record
  for a parse miss.
- Keep at least 45 seconds between Karen's opening line and your drift, or the cooldown
  swallows the catch.
- Artem needs a full uninterrupted minute, or the floor handover never fires. No "mhm".
- Overrunning a take is fine. Dead air is not — talk through every click.
