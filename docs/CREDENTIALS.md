# What Vitaly needs to register

Everything the build is blocked on, in the order it blocks. Nothing here takes long —
but three of the five are sponsor conversations, and the mentors are on site today only.

**Get the sponsor keys in the first hour.** A three-hour chunk blocked at 19:00 on a
five-minute conversation that could have happened at 13:00 is the standard way to lose a
hackathon evening.

Keys go in `.env`, which is gitignored. This repo is public — no key ever gets pasted
into a file that is tracked, an issue, or a chat message.

---

## 1. Discord — blocks `ears-discord`, which blocks everything — ✅ done

Discord Developer Portal → New Application → Bot.
Full walkthrough, including invite links for other servers: [DISCORD-SETUP.md](DISCORD-SETUP.md).

- **Bot token** → `DISCORD_EARS_TOKEN`
- **Privileged intents:** none needed. ears uses Guilds and Guild Voice States, which are not privileged.
- **Invite it** with the **`bot`** scope, not just `applications.commands`:
  `https://discord.com/oauth2/authorize?client_id=<APP_ID>&scope=bot&permissions=40914176`
  (View Channel, Connect, Speak, Use Voice Activity, Mute Members, Priority Speaker,
  Send Messages, Embed Links).
- Once ears is running, select the meeting voice channel for each server in the operator
  console. The selection is stored in Postgres; no server/channel IDs are needed in `.env`.
- Test server: **https://discord.gg/qR6RwKuAh**

A second application will be needed only if the Concierge is ever revived. Do not share
one token across two processes.

## 2. SLNG — blocks the chair having a voice — ✅ done

Silver sponsor, on site. The key works, and ears-discord uses it for streaming STT
(`deepgram/nova:3`, `soniox/speech-ai:rt-v5`) and for TTS in the console say-box
(`slng/fish/tts:s2.1-pro`, about 1.2 s from Barcelona). The brain's B7 can use the same
TTS endpoint. `packages/ears-discord/src/ears/tts.py` shows the request shape.

- **API key** → `SLNG_API_KEY`
- Ask for: the TTS endpoint and the voice list, the STT endpoint, and **whether the
  `unmute` framework applies to what we are building** — their track gives a bonus for
  it, and it is worth thirty seconds of a mentor's time to find out before building
  against the plain API.
- Also ask about **latency** — round-trip matters more here than quality. An
  interruption that lands three seconds late is not an interruption.

## 3. Nebius — powers what Karen says — ✅ done

Silver sponsor, Token Factory.

- **API key** → `NEBIUS_API_KEY`
- Models live in `packages/brain/config/models.yaml`; `BRAIN_MODEL_FAST` and
  `BRAIN_MODEL_NORMAL` override them for an A/B run. The default is
  `deepseek-ai/DeepSeek-V4.1-Flash` (thinking off) for relevance, notes and spoken lines;
  the calendar's brief parser uses it too.
- The bake-off (2026-09-19) is recorded in models.yaml. Qwen is not used.
- Their track wants Token Factory used "meaningfully, contributing to core
  functionality" — generating what the chair says qualifies; make sure the README says so.

## 5. GitHub — blocks Artem — ✅ done

- His **GitHub handle**, so he gets collaborator access on `bioztar/gavel`.

---

## Not credentials, but also blocking

- **A test Discord server** with a voice channel, and **three people willing to sit in a
  call** for ten minutes around 22:30 for the dry run. Recruit them early — at 22:30
  everyone is busy with their own submission.
- **Which laptop presents.** Both halves run on one machine on stage. Decide at 16:00.
