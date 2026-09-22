# gavel — architecture reset & platform plan

Strip the hackathon scaffolding. Keep the chair. Google Meet first, then Zoom, then Teams.

Working document for the Vitaly × Artem review · 21 September 2026 · working document, not a contract.
Visual version: **https://bioztar.github.io/gavel/blueprint.html**

---

## The thesis

The chair's core costs nothing to run. Everything expensive in the repo today is optional,
and most of it exists because of a 36-hour hackathon, not because of the product.

gavel decides **whether** to interrupt from two events and a clock — `speaking.start`,
`speaking.end`. No audio decoding, no model call, no vendor. Only **what she says** hits a
model: one sentence, under 20 words.

| | |
|---|---|
| Call-SDK imports in `brain` | **0** |
| Lines being deleted now | **~15,800** |
| Avatar cost removed per 45-min call | **$216** |
| New packages per platform | **1** |

---

## Decided since this document was first published — 21 September

- **The avatar is cut, completely.** No live video generation anywhere in the live path.
  `chair-video`, fal Director and the projector page all come out. Decision 2 below is settled.
- **Karen's presence becomes a screen share plus a still, not a generated face.** The live
  meeting board — agenda,
  talk-time bars, decisions — is presented from Karen's own participant tile. Nobody navigates
  to a second page; the thing that makes the time-governance claim visible is simply on screen
  inside the meeting. See section 5.
- **We build `ears-meet` rather than buying bot infrastructure.** Decision 1 below is settled.
  All five autonomous build lanes are reviewed and accepted — see section 10.

---

## 1. The seam that makes all of this possible

`brain` imports no call SDK. Verified, not asserted — grepping `packages/brain/src` for any
Discord reference returns nothing but the `discordId` field name carried on the wire.

```
  ears-*  (swappable, one per platform)        brain  (written once)
  ├ owns one call connection            ⇄      ├ agenda + topic clock
  ├ who is in the call                         ├ talk-time per person
  ├ who is speaking, right now          WS     ├ interrupt policy (plain code)
  ├ transcribes utterances            frozen   ├ the one sentence (model)
  └ plays her audio into the room     contract └ notes, decisions, parking lot

  ears-discord │ ears-meet │ ears-zoom │ ears-teams       5,265 lines, untouched
```

**Adding Google Meet is one new package and nothing else.** Agenda format, floor clock,
triggers, voice, notes, evals and console all stay as they are.

---

## 2. The cost ladder

| Tier | What | Cost |
|---|---|---|
| **0** | **Floor governance — the judged moment.** Talk-time share, monologue detection, topic over budget, silent must-hear attendee, dead air. Runs on `speaking.start`/`speaking.end` plus a clock. Plain code, unit-tested against a scripted replay. | **free** (CPU only) |
| **1** | **The sentence she says.** One model call per intervention, capped under 20 words. Nebius, OpenAI-compatible, driven by `config/models.yaml`. | ~$0.001 / intervention |
| **2** | **Understanding the room.** Continuous STT. Buys wake-word, notes, decisions, tangent detection, the record with numbers. Degradable — switch it off and Tier 0 still chairs the meeting. | metered / audio-minute |
| **3** | ~~**Lip-synced live avatar.**~~ **Cut.** fal `minimax/h3-max/director` at $0.08/s / 768p, $1.20 session minimum, ~15 min session cap forcing mid-meeting rotation, billed on wall-clock. Replaced by a shared screen that costs nothing to render. | **$0** (was $216 / call) |

### The avatar is the largest cost and the most fragile machinery in the repo

It exists for one reason: **Discord blocks bot video outright**, so the chair needed a face on
a separate projector page. That constraint does not exist on Meet, Zoom or Teams — a bot
participant has its own tile and a static image fills it for $0.

What comes out with it: a browser that owns the `RTCPeerConnection` because Python cannot, an
SSE command channel, a heartbeat that by the author's own note *"cannot billing-stop
anything"*, a token-gated fal proxy, and a committed esbuild bundle. 7,487 lines of the most
failure-prone code in the system, serving a feature no buyer asked for.

**Decided, 21 September:** Director is cut from the live path on every platform, and the
package is deleted rather than flagged off. The persona artwork stays. What replaces her
presence in the room is a shared screen — see section 5.

---

## 3. Teardown

### Keep

| Package | Lines | Why |
|---|---|---|
| `brain` | 5,265 | The product. Zero platform coupling. Untouched by all of this. |
| `ears-discord` | 5,696 | The only surface that works end to end today, and therefore the regression harness that proves `ears-meet` is correct. Costs nothing to keep. |
| `calendar` | 4,022 | **Promote, don't just keep.** On Meet this gets *more* valuable — Calendar is where the agenda natively lives. Already emits the frozen contract shape, already refuses to send an invite with no topics. |

### Decide

| Thing | Position |
|---|---|
| ~~fal / `chair-video`~~ | **Settled: delete.** 7,487 lines out; a Devin lane is doing it now on `chore/cut-avatar`. The audio path is untouched — only the side-call that produced video goes. |
| Mastra | Removable behind an interface that already exists (`chair/llm.ts` vs `chair/mastraLlm.ts`). Cost of removal: the Langfuse exporter rides Mastra's tracing (`@mastra/langfuse` in `mastra/index.ts`), so losing one loses the other. Not urgent. Not free. |
| SLNG | Keep the *capability*, name the *adapter*. STT in ears, TTS in brain, both adapter-shaped. Note the cross-project coupling — the Karen chat site reuses this same TTS. |
| Nebius | Keep. OpenAI-compatible endpoint already driven by config. Not lock-in. |

### Delete

| Thing | Lines | Why |
|---|---|---|
| `stream-vonage` | 777 | HLS restream + archive of the stage, published from a browser screen-capture. Built to satisfy a sponsor and produce the submission video. A time-governance product has no restream requirement. |
| `ears-vonage` | 0 | A README describing a package that was never written. Credentials never arrived. |
| plus | — | the compose service, `scripts/set-vonage-key.sh`, the `VONAGE_*` settings, ~15 documents that still name it. |

**Reviewed:** [PR #4](https://github.com/bioztar/gavel/pull/4) — 40 files, branch
`chore/excise-vonage`, verified and open. It will **not** be merged before the review.

### Off the live path — no action

Devin (3 PRs merged), Quality Clouds (findings fixed before freeze), Galtea (ten frozen eval
cases), Langfuse (one trace session per meeting). None run during a meeting. Evidence
artifacts and dev tooling — leave them.

---

## 4. Target architecture

1. **Before** — `calendar`: host dictates a brief → model writes purpose, topics, owners,
   minutes, must-hear → refuses if there are no topics → agenda lands in the real invite and
   in `agenda.json`.
2. **Hear** — `ears-<platform>`: joins the call, emits who is speaking and when, transcribes,
   plays her audio back into the room.
3. **Think** — `brain`: floor clock and triggers in plain code, one model call writes the
   sentence, notes/decisions/open items/parking lot. Postgres + Redis behind it.
4. **Show** — console + record: live transcript, agenda progress, her exact words, and the
   number that sells it — floor time per person, per topic, per meeting.

**Container count drops from eight to five** — Postgres, Redis, `ears-*`, `brain`, `calendar` —
plus one headless browser per concurrent meeting. Removed: `stream-vonage`, `chair-video`.

> **The unit cost moves.** With the avatar gone, inference is not the scale driver — the
> browser is. Every concurrent meeting on Meet needs its own headless Chromium: roughly 1 vCPU
> and 0.5–1 GB RAM for the duration of the call. That number decides whether gavel is priced
> per room, per seat, or per meeting-hour — and it is the number a managed bot vendor is
> quoting you when they charge per bot-hour.

---

## 5. Karen's presence — a shared screen, and a still rather than a generated face

**The demo moment survives the cut, and gets better.** The avatar answered a question nobody
was asking: *what does Karen look like?* The question a room actually asks is *am I talking too
much?* — and a face cannot answer it. A live board can, and it is the only artefact that makes
an invisible claim about time visible while there is still time to act on it.

So Karen joins with a static persona image in her tile, and **presents**. What the room sees is
the meeting's own state, updating as they speak.

### What is on the screen

- **Talk-time per person** — a bar each, updating continuously. The dominant element on the
  page. Someone holding 60% of the floor is obvious from across a room, without Karen saying a
  word.
- **The agenda** — every topic, its owner, its budget, which is live, which is done, which will
  not be reached. Over-budget is unmistakable.
- **The clock** — time on this topic against its budget, and time left in the meeting.
- **Karen's last line**, verbatim, so the room can read what she just said.
- **Decisions, open items and the parking lot** as they accumulate — the minutes, written live,
  in front of the people who can correct them.

### How it gets into the call

The bot already runs a real browser to be in the meeting at all. A second tab holds the board;
the bot presents that tab. No extra infrastructure, no second vendor, no per-minute meter.

- New package `packages/stage` serves the board and pushes state over SSE.
- Its `document.title` is pinned to `gavel-stage` — that exact string is how the bot selects
  which surface to present.
- Chromium auto-selects the capture source rather than showing a picker dialog, so no human is
  in the loop.
- If the board is unreachable, Karen joins and chairs the meeting anyway. **The share is an
  enhancement, never a precondition.**

### Design constraints, because this is video and not a dashboard

It will be seen as a compressed stream at roughly 720p, in a small window, on someone else's
laptop. That rules out most of what a dashboard normally does. Big type, high contrast, nothing
small. **It never scrolls and never overflows** — everything visible at once, content
truncating gracefully rather than pushing anything off screen. No navigation, no controls, no
hover states: nobody can click a video. Motion carries the meaning, because compression
destroys small moving text — a bar that jumps reads where a ticking number does not. And every
failure mode needs a legible fallback, because a blank screen here is being broadcast into a
customer's meeting.

---

## 6. Platform onboarding

| | Audio **out** of the call | Her voice **into** the call | Per-speaker timing | Gatekeeper | Effort |
|---|---|---|---|---|---|
| **Google Meet** *(first)* | Headless Chromium joins as a participant; capture the tab's mixed audio. Media API is receive-only — out. | **Solved.** Virtual mic (PulseAudio null sink) fed by brain TTS; bot unmuted. | **DOM.** Speaking indicator per tile maps straight onto `speaking.start/end` — no audio decoding, so Tier 0 stays free. | Google account for the bot, plus lobby admission or a calendar invite. Workspace orgs can block external participants. | 2–3 wks |
| **Zoom** *(second)* | **Best of the three.** Meeting SDK for Linux, Raw Data: a dedicated PCM 16LE stream *per participant*. | **Verify.** Capture is documented; raw audio *send* from the Meeting SDK is not. One spike settles it. Video SDK has full raw control but is a different product. | **Native.** Per-participant streams — attribution is exact, not inferred. | OBF token for external meetings (authorizing user must stay present), host consent prompt on recording, 4–6 week app review before production. | 3–4 wks + review |
| **Teams** *(third)* | Graph Communications, application-hosted media: 50 audio frames/sec, 20 ms each, raw. | **First-class.** The only platform with a real documented bidirectional bot — declares `sendrecv` on join. | **Native.** | **Windows-only hosting, .NET/C# only** — no Python, REST or WebSocket path. Needs `Calls.AccessMedia.All` and tenant admin consent. Microsoft's 2026 guidance steers AI scenarios away from this API toward Copilot Studio. | 6–8 wks, new stack |

### Google Meet — priority 1

The wedge. Not because it is the easiest surface — because the agenda already lives next door
in Calendar, and `calendar` is already built.

- **Route** — headless Chromium bot, joined as a participant
- **Ingress** — tab audio → STT; speaking indicator per tile → contract frames
- **Egress** — PulseAudio null sink as the bot's microphone
- **Face** — static persona image in the bot's tile, $0
- **Agenda** — the Calendar invite the organiser already sent
- **Risk** — Meet UI changes break DOM selectors. Mitigate by pinning the contract at the
  frame level and keeping selectors in one file.

### Zoom — priority 2

Clearest pain, best media access, slowest gate. Start the app review the week Meet ships so
the clock runs in parallel. RTMS (Zoom-native, no bot) is receive-only and needs the host org
to enable it — a complement, never the whole answer.

### Teams — priority 3

The suite play. Technically the cleanest bot API, organisationally the most expensive to
reach: a Windows/.NET service in an otherwise Python + TypeScript estate. Hedge to evaluate
first: **ACS Call Automation** — a bot joins the Teams meeting and streams audio to a server
over WebSocket. Cheaper to reach, less raw control.

### Why the Google Meet Media API is not the route

It is the obvious first answer and fails on three independent counts, any one of which is fatal:

1. **It cannot speak.** The client's SDP offer must contain *receive-only* media descriptions —
   `a=recvonly` from the client, `a=sendonly` from Meet. gavel's entire product is a chair who
   interrupts out loud.
2. **It cannot count the floor.** The cap is exactly three virtual audio streams, allocated to
   the most relevant speakers and reassigned as the conversation moves. Talk-time share per
   person over a whole meeting is structurally unobtainable from three rotating slots. This one
   is architectural, not a preview limitation — it does not go away at GA.
3. **It is not generally available.** Developer Preview enrolment is required for the Cloud
   project, the OAuth principal, *and every participant in the conference*. Blocked for
   encrypted or watermarked meetings, blocked when an underage account is present, capped at
   eight hours, and the host can terminate it mid-call.

A headless browser bot is visible in the participant list — the honest behaviour for an AI
chair anyway — and works across every platform with the same playbook.

---

## 7. `/compose` becomes a browser extension

Today `/compose` is a page on our server: the host types a brief into one box, a model turns it
into a purpose, topics, owners, minutes and a must-hear list, and it refuses to send an invite
that has no topics. That gate is the reason the in-call triggers have anything to enforce — and
it is currently a page nobody visits, in a product whose users already live in a calendar tab.

**What the extension does**

- Adds a **"Chair this meeting"** control directly into Google Calendar's event editor and
  Meet's pre-join screen — where the meeting is actually being created.
- Reads the event the user is already editing: title, attendees, duration, existing description.
- Sends the brief to our server, which does the model call and returns the structured agenda.
- Writes the agenda into the real invite description, and registers the contract-shaped
  `agenda.json` against the meeting id.
- Shows the refusal inline when the brief has no decidable topics — the gate moves to the point
  of creation instead of a separate page.
- Invites the bot account to the event, which is how gavel gets into the call.

**How sign-in works**

- **Manifest V3**, service worker background, content scripts scoped to the calendar and
  meeting hosts only.
- **Google:** `chrome.identity.getAuthToken` on Chrome, `launchWebAuthFlow` for cross-browser
  and for Microsoft and Zoom. The user signs in with the account they already use.
- Scopes stay minimal and are named in the consent screen: read and write the events the user
  is editing. Nothing org-wide.
- **The extension holds no API key.** It holds a user OAuth token and nothing else — every
  model call, every provider credential and every database write stays server-side. An
  extension is client code; anything shipped in it is public.
- Tokens live in `chrome.storage.session`, never `localStorage`, and are exchanged server-side
  for our own session.

**Distribution is two doors.** Chrome Web Store + Edge Add-ons is the self-serve route — an
individual installs it, no admin involved, which is how you get the first hundred users. Google
Workspace Marketplace is the enterprise route — an admin deploys it org-wide, which is how you
get the first paying contract. Build for the first, design the permissions so the second needs
no rewrite.

---

## 8. Sequence and effort

| Workstream | Owner | Effort | Starts |
|---|---|---|---|
| Vonage excision | Devin (ultra) | done | now — PR open, unmerged |
| Cut Director from live path | Devin | 1 wk | after the decision, behind a flag first |
| Meet egress spike (virtual mic) | helm | 3 d | immediately — proves she can speak |
| `ears-meet` | crewmate / Devin | 2–3 wks | after the egress spike |
| Contract conformance suite | crewmate | 1 wk | once `ears-meet` reaches first frames |
| Browser extension | Devin | 2 wks | parallel with `ears-meet` |
| Zoom app review | Vitaly / Artem | 4–6 wks elapsed, no engineering | **the week Meet ships** |
| Zoom egress spike + `ears-zoom` | crewmate | 3–4 wks | after Meet lands |

**Dependencies that actually bind:** the Meet egress spike blocks `ears-meet` — if she cannot
speak, nothing else matters. The conformance suite depends on `ears-meet` reaching first
frames, not on it being finished. Zoom's app review is a wall-clock queue with no engineering
on it: start it the week Meet ships, not the week Zoom work starts, or it becomes the critical
path for no reason. Teams is deliberately not scheduled — it needs the .NET decision first.

---

## 9. What needs deciding, with Artem

### 1 · Build `ears-meet`, or buy bot infrastructure? — **settled**

**Decided 21 September: build.** Recorded here with the reasoning intact so the trade can be
revisited if Meet's DOM churn turns out worse than expected.

Managed meeting-bot vendors (Recall.ai, MeetStream, Meeting BaaS) run the Chromium fleet,
handle joining, speaker attribution and transcripts across all three platforms behind one
integration — priced per bot-hour.

- **Buy** — days instead of weeks, all three platforms at once, someone else owns the breakage
  when Meet changes its DOM. Costs per meeting-hour forever, and the speaking-event granularity
  Tier 0 needs must be verified against their API before committing.
- **Build** — owns the margin, owns the data, no per-hour floor under the pricing. Weeks per
  platform, and we own every UI change Google ships.

Worth stating plainly: *"no sponsor-specific solutions"* means dropping vendors chosen for
hackathon prize eligibility. It does not mean refusing all third parties. A bot vendor is a
legitimate option and may be the efficient answer for reaching a first customer.

### 2 · Does Karen keep a face? — **settled**

**Decided 21 September: no generated face.** The video pipeline is cut entirely, not flagged
off. **Amended 22 September:** the *static* still is not just configured, it is published — the
bot joins Meet with its camera on and a real video track carrying `karen-formal.png`. The face
is a picture, not a render; §5's shared screen is still what carries the argument.

$216 per 45-minute call, ~7,500 lines, the most fragile subsystem in the repo — against a demo
moment that genuinely lands in a room.

- **Cut for v1** *(recommended)* — static persona image in the bot's tile. Reversible: the
  package stays in git history and the audio path is unchanged.
- **Keep for sales demos only** — behind a flag, off by default, never on a customer meeting.

### 3 · Whose account does the bot use?

- **Bring your own** — the customer creates a bot account in their own Workspace. Solves
  external-participant blocks and data residency instantly; adds an onboarding step that loses
  self-serve users.
- **Managed by us** — one click to install, then a fight with every Workspace that blocks
  external participants.

A go-to-market decision wearing a technical costume: it decides whether gavel is self-serve or
sales-led.

### 4 · Mastra: keep or unwind?

Not urgent, but a decision rather than a drift. The swap seam already exists.

- **Keep** — Langfuse tracing comes free through its exporter, and "the chair is debuggable" is
  a real claim we make.
- **Unwind** — `chair/llm.ts` already defines the interface; direct calls are a small change.
  Then Langfuse needs wiring directly, or we lose per-meeting traces.

### The one open technical question

**Can a Zoom Meeting SDK bot on Linux send raw audio into the meeting?** Capture is thoroughly
documented; injection is not. Half-day spike, and it should happen before any Zoom date is
given to anyone. Google Meet and Teams egress are both settled — virtual mic and native
`sendrecv` respectively.

---

### 5. What does the chair actually know?

Building the shared screen surfaced two gaps in the chair's own view model. Neither blocked the
board, both change what it can honestly display, and neither should be patched without a decision.

- **Topic owners** — the agenda carries a budget per topic but no owner, so the board's owner
  column is blank in a live meeting. Either the chair starts tracking who owns each item (which
  makes "Marc, this one is yours and you have four minutes" possible) or the column comes out and
  the board never claims to know.
- **Wall-clock vs plan** — there is no meeting start time in the view, so "time left" is the sum of
  the remaining budgets, not real minutes against a 45-minute booking. Those diverge the moment a
  topic overruns. A start timestamp is a one-line addition and turns the clock into the thing
  people assume it already is.

Both are small. They are here because the board is the first surface that made the chair's blind
spots visible to a room, and a screen shared into a customer's meeting should not display a field
it cannot fill.

## 10. What is already moving

| Item | Owner | State |
|---|---|---|
| Vonage excision — `chore/excise-vonage` | Devin (ultra) | **Reviewed.** [PR #4](https://github.com/bioztar/gavel/pull/4) — 40 files, verified, open and unmerged. |
| Avatar cut — `chore/cut-avatar` | Devin (ultra) | **Reviewed.** [PR #5](https://github.com/bioztar/gavel/pull/5) — 10,760 deletions; persona stills proven byte-identical after a correction. |
| `ears-meet` — `feat/ears-meet` | Devin (ultra) | **Reviewed.** [PR #8](https://github.com/bioztar/gavel/pull/8) — 91 tests; brain reaches identical decisions from Meet frames as from Discord. |
| Karen's screen — `feat/karen-screen` | Devin (ultra) | **Reviewed.** [PR #6](https://github.com/bioztar/gavel/pull/6) — no clipped text at 720p or 1080p, re-verified in the pixels. |
| Compose extension — `feat/compose-extension` | Devin (ultra) | **Reviewed.** [PR #7](https://github.com/bioztar/gavel/pull/7) — 56 tests; no provider key in the bundle; server endpoints specified, not built. |
| gavel containers on the VPS | helm | **Stopped.** Database dumped first, volume intact, one command to revive. |
| This document | helm | **Published.** Committed and served from GitHub Pages. |
| Zoom raw-audio injection spike | — | **Held.** Half a day; must precede any Zoom commitment. |
| Teams / .NET hosting decision | — | **Held.** No engineering until it is made. |

---

*Verified in this document: `brain` contains zero call-SDK imports; Meet Media API offers are
receive-only with a three-stream audio cap; fal Director list price is $0.08/s at 768p with a
$1.20 session minimum. Verified since first publication, by measurement on 21 September: Chromium auto-selects the
`gavel-stage` tab for Karen's screen share with no picker dialog — real headful Chromium on Xvfb,
a track at 1280x720 and `displaySurface: "browser"`. Desktop capture on the same virtual display
fails outright, so tab capture is the only route and the "A tab" menu item is load-bearing. Measured 22 September: Chromium's own fake-camera flags are unusable here — `--use-fake-device-for-media-stream` also replaces the audio manager, leaving only "Fake Audio Input" devices where the PulseAudio monitors have to be, and `--use-file-for-fake-video-capture` alone is inert. Karen's still is therefore published by patching `getUserMedia` with a canvas track; the frame the page received was compared pixel-by-pixel against the source image and matched exactly. Still
unverified, and to be proven by a live call rather than by this document: Zoom Meeting SDK
raw-audio injection, and the two Meet DOM selectors behind the present menu.*
