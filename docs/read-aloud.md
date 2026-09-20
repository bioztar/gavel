# gavel — your lines, to read out

Cold open **A**: Karen speaks first. You answer her.

Two topics: **solution and architecture** (6 min, you present), then **roadmap**
(8 min, open discussion, you and Artem both down as must-be-heard).

Your parts total about **3:05**; the whole thing runs **5:10** with Karen and Artem in it.

Lines in *italics* are not yours — they are the cue to start talking.

---

> *Karen — title card · 8s*
>
> *Vitaly, parked for later: cloud pricing. Back to solution and architecture. What does the room need to understand first?*

## 1. architecture — slide 1 · 11s

That is an AI chair, and it just took the floor off me in the middle of my own sentence. It can do that because it would not let this meeting be booked without an agenda in the first place. Here is the whole thing in five minutes.

## 2. /compose · 7s

I ask for a meeting the way I normally ask for one. Karen, set up a meeting with Artem tomorrow at ten. Thirty minutes.

> *Karen — the refusal page · 10s*
>
> *There's no agenda in that brief. Karen won't put a meeting in three people's calendars without one. What does this call have to decide? Name the topics below, with who owns each.*

## 3. the refusal page · 8s

A title, a time, a length, and nothing about what the meeting is for. She will not book it. She asks for the agenda instead of just saying no.

## 4. /compose · 15s

So I tell her. Karen, set up a meeting with Artem in fifteen minutes, fifteen minutes long, called gavel live demo. Two topics. One, solution and architecture, six minutes, I present it. Two, roadmap, eight minutes, open discussion, and I want both Artem and me heard on it.

## 5. the agenda table · 10s

Two topics, each with an owner, its minutes, and who has to be heard on it. I pick how hard she chairs. On high she cuts in mid-sentence. Nobody is exempt, including me.

## 6. the invite email · 11s

Send. Real invite, real calendar file, real inbox. I dictated a paragraph, and this is what the other two people get. There are two links in it. One opens the Discord call. The other opens the meeting room.

## 7. the meeting room · 12s

The room is the page you put on the shared screen. Karen and the agenda on the left. On the right, the topic running now, how much of its time it has used, and who is talking. Along the bottom, what got decided and what is still open.

> *Karen — the meeting room · 11s*
>
> *This is gavel live demo. Fifteen minutes, two topics. First: solution and architecture, six minutes, presented by Vitaly. Vitaly, the floor is yours.*

## 8. architecture — slide 1 · 23s

Nobody typed start. She opened it herself. Three parts. She sits in the Discord call the way a person does, and the audio goes out to speech to text. Then the decision to interrupt, which is ordinary code. It looks at who has held the floor and for how long, against the minutes on the agenda, and it runs four times a second. The model only writes the sentence she says. Her speech goes back into the same call, and fal moves her face.

## 9. architecture — slide 1 · 16s

And the interesting part is really the cost, because once you are running six containers you start looking at reserved instances against spot, and I compared three providers last month, and their pricing pages are impossible to line up, and then there are egress fees on top...

> *Karen — architecture — slide 1 · 8s*
>
> *Vitaly, parked for later: cloud pricing. Back to solution and architecture: what does the room need to understand first?*

## 10. the meeting room · 5s

Eight seconds, and I did not cue her. She parked it rather than dropped it, and she wrote that line herself.

> *Karen — the meeting room · 9s*
>
> *That is six minutes on solution and architecture. Moving to topic two: roadmap, eight minutes. Artem and Vitaly are both down to be heard on this one.*

## 11. the meeting room · 4s

Artem, you have been building the Discord side. Where does this go next?

> *Artem — the meeting room · 68s*
>
> *Discord was the fastest thing to build against, but it is not where this belongs. Only one container actually knows what a voice call is, so Meet or Zoom is the same piece of work again, maybe two days each. Teams is the one that matters, because the calendar and the org chart are already in there, and that is what tells you who owns a topic without anyone typing it in. Then there is the scaling side. Right now we buffer each speaker and send one clean stream each, and for six people that is fine, at thirty it is not, because transcription cost goes up with every speaker, so we would detect speech at the edge and only transcribe whoever has the floor. The brain checks the agenda four times a second, which is cheap, but every check reads the last two minutes out of Redis, and at a hundred meetings at once we would hold that in memory instead. And the thing nobody expects is reconnects. Discord drops the voice socket now and then, and if you come back without the floor state the chair forgets who has been talking and goes quiet exactly when you need it, so that state has to survive...*

> *Karen — the meeting room · 8s*
>
> *Artem, that is a minute and a half on this topic. Vitaly, the agenda says you must be heard on roadmap, and you have not spoken. Your turn.*

## 12. roadmap — slide 3 · 34s

She took the floor off the person who had it and gave it to the person who had not spoken. Nobody in the room had to be the one who interrupts. On roadmap, my answer is the part after the call. Everything she collected, the transcript, the decisions, the open items, should go straight into whatever the company already uses to keep its knowledge. She plugs into the team's own agent and hands over the result. And at company scale the rules stop being per meeting: no agenda, no booking, and how hard she chairs is set once, centrally.

## 13. roadmap — slide 3 · 21s

So I asked for a meeting the way everyone asks for one, and it said no. I told it what the meeting was for, and everyone got an agenda with an owner on every line. It started the call itself. It caught me going off topic in eight seconds. And it moved the floor when one person had held it too long. It never wrote my agenda. It refused to work without one, and then it held me to it. Thank you.

---

## While recording

- Do not re-take one of Karen's interventions for landing a second late. A real one at
  eleven seconds beats a perfect one nobody believes.
- If the parse comes back wrong, fix the row on screen and keep going.
- Keep at least 45 seconds between Karen opening the meeting and your drift, or the
  cooldown swallows the catch.
- Artem needs a full uninterrupted minute on roadmap, or she never breaks him off.
  No "mhm", no nodding noises — every sound you make delays it.
- Overrunning a take is fine. Dead air is not — talk through every click.
