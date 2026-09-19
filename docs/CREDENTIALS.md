# What Vitaly needs to register

Everything the build is blocked on, in the order it blocks. Nothing here takes long —
but four of the six are sponsor conversations, and the mentors are on site today only.

**Get the sponsor keys in the first hour.** A three-hour chunk blocked at 19:00 on a
five-minute conversation that could have happened at 13:00 is the standard way to lose a
hackathon evening.

Keys go in `.env`, which is gitignored. This repo is public — no key ever gets pasted
into a file that is tracked, an issue, or a chat message.

---

## 1. Discord — blocks `ears-discord`, which blocks everything

Discord Developer Portal → New Application → Bot.

- **Bot token** → `DISCORD_EARS_TOKEN`
- **Privileged intents:** Server Members. The bot also needs the Guilds and Guild Voice
  States intents, which are not privileged.
- **Invite it** to a test server with: Connect, Speak, Use Voice Activity, View Channel.
- **Server id** → `DISCORD_GUILD_ID` (enable Developer Mode, right-click the server).

A second application will be needed only if the Concierge is ever revived. Do not share
one token across two processes.

## 2. Vonage — blocks `ears-vonage`

Gold sponsor, mentors on site. Ask them for Video API credentials for the hackathon.

- **Application ID** → `VONAGE_APP_ID`, plus the **private key** file for generating
  tokens server-side (older accounts issue an API key + secret instead — either is fine,
  say which you got).
- A **session id** and a **token** for the demo session → `VONAGE_SESSION_ID`,
  `VONAGE_TOKEN`. These can be generated from the dashboard or a five-line script; ask
  the mentor for the fastest path they recommend.
- Worth asking them directly: whether **archiving** is enabled on the hackathon account.
  It records the call, and the recording doubles as the submission video.

## 3. SLNG — blocks the chair having a voice

Silver sponsor, on site.

- **API key** → `SLNG_API_KEY`
- Ask for: the TTS endpoint and the voice list, the STT endpoint, and **whether the
  `unmute` framework applies to what we are building** — their track gives a bonus for
  it, and it is worth thirty seconds of a mentor's time to find out before building
  against the plain API.
- Also ask about **latency** — round-trip matters more here than quality. An
  interruption that lands three seconds late is not an interruption.

## 4. Nebius — blocks what the chair actually says

Silver sponsor, Token Factory.

- **API key** → `NEBIUS_API_KEY`, base URL → `NEBIUS_BASE_URL`
- **Which model** to use → `NEBIUS_MODEL`. Ask the mentor which of their hosted models is
  fastest for a one-sentence completion; the chair's line is short and latency-sensitive,
  so the biggest model is the wrong choice.
- Their track wants Token Factory used "meaningfully, contributing to core
  functionality" — generating what the chair says qualifies; make sure the README says so.

## 5. fal.ai — blocks the chair having a face

Silver sponsor.

- **API key** → `FAL_KEY`
- Their own track is an *infinite livestream* challenge using **MiniMax H3 Max
  Director** — ask the mentor whether a continuously generated talking presence counts,
  because that decides whether the face is worth building for the track or only for the
  demo.

## 6. GitHub — blocks Artem

- His **GitHub handle**, so he gets collaborator access on `bioztar/gavel`.

---

## Not credentials, but also blocking

- **A test Discord server** with a voice channel, and **three people willing to sit in a
  call** for ten minutes around 22:30 for the dry run. Recruit them early — at 22:30
  everyone is busy with their own submission.
- **Which laptop presents.** Both halves run on one machine on stage. Decide at 16:00.
