# Your part — what only Vitaly can do for the Meet demo

Everything else is running without you (four lanes, bottom of this page).
This is the short list of things an agent cannot do for you.

## 1. Pick the Google account that becomes Karen

You said you have several. Pick **one you don't mind being seen in a meeting**:
the display name on that account is the name every participant sees in the
Meet roster — `MEET_BOT_NAME` only applies when joining anonymously, and we are
joining signed in.

- Rename that account's profile to **Karen** (Google account → Personal info →
  Name) before the first login. Cosmetic, but it is the whole joke.
- A plain @gmail.com is fine. A Workspace account is *better* if the meeting is
  hosted on the same Workspace — same-domain participants are usually admitted
  without anyone clicking "Admit".
- Do **not** use your main account. The profile directory this creates is a
  live session for that account.

## 2. Make the signed-in profile (on a machine with a screen — your Mac)

The container has no screen and Google's login form fights automation. So this
happens once, by hand, on your Mac:

```bash
git clone https://github.com/bioztar/gavel.git   # if you don't have it
cd gavel/packages/ears-meet
just setup                                        # uv sync + Playwright Chromium
MEET_PROFILE_DIR=~/gavel-meet-profile just login
```

A visible Chromium opens at the Google sign-in page. Sign in as Karen, finish
any 2-step prompt, then press Enter in the terminal. The script checks
meet.google.com actually shows the account menu, then closes.

**That directory is the credential.** It is a live Google session. It is
gitignored on both ends and must never enter an image or a commit.

## 3. Copy the profile to the VPS

```bash
scp -r ~/gavel-meet-profile coder@uk-lon-1:/home/coder/DEV/gavel/secrets/meet-profile
ssh coder@uk-lon-1 'chmod -R go-rwx /home/coder/DEV/gavel/secrets/meet-profile'
```

`secrets/` is already in `.gitignore` (committed today, `19fde09`).

Profiles go stale after a long gap — if Meet asks to sign in again, re-run
step 2 and re-copy.

## 4. Set four lines in `.env` on the VPS

```
MEET_URL=https://meet.google.com/xxx-yyyy-zzz
MEET_PROFILE_HOST_DIR=./secrets/meet-profile
EARS_WIRE_URL=ws://ears-meet:8787
EARS_HTTP_URL=http://ears-meet:8787
```

The last two are what swap the brain off Discord and onto Meet. Without them
the stack boots and chairs a Discord call instead. Everything else has a
default — see the MEET block in `.env.example`.

Then: `docker compose --profile meet up -d`

## 5. The rehearsal needs a second human

Karen needs someone to interrupt and someone to cut off. One browser tab of
yourself is not a rehearsal — the turn-taking logic keys off other people
actually speaking.

- Book 30 minutes with one other person.
- **Record it** (Meet's own recording, or screen capture). The pitch depends on
  her timing, and the only way to tune timing is to watch it back.
- Do the rehearsal at least a day before the real pitch. First live call with a
  browser-driving bot always surfaces something.

---

## Decisions I need from you

| # | Question | Why it's yours |
|---|---|---|
| 1 | **Devin "ultra" mode** — the v3 API has no model/effort/tier parameter. Only `max_acu_limit`. If ultra exists it is a plan or UI setting. Check app.devin.ai settings and tell me, or set it there yourself. | Billing + account access |
| 2 | **Which face?** `assets/persona/karen-formal.png` is the default. There are three "funky" variants. Formal reads enterprise; funky reads demo. | Taste, and it's the first thing the audience sees |
| 3 | **`brain/_config/lanes.yaml` has no `gavel` lane.** Missions are being written with `lane: gavel` against a lane that does not exist. Add it, or tell me which existing lane gavel belongs under. | Brain taxonomy is yours |

## Running without you

| Lane | Who | What |
|---|---|---|
| Compose boot proof | Devin A | Bring up `--profile meet` with no Google account, prove Xvfb, PulseAudio sinks, `/health`, and the stage tab. PR, no merge. |
| Demo runner | Devin B | `scripts/demo-preflight.sh` + `scripts/demo-up.sh`, and correct the docs that still say ears-meet has no compose service. |
| New name | naming agent | 15+ candidates screened against companies, USPTO/EUIPO, .com/.ai, GitHub/npm/PyPI. Ranked top 5 with the strongest argument *against* each. |
| Chrome Web Store | crewmate `gavel-extension-store` | Package `packages/extension`, honest minimal-permission manifest, update `docs/EXTENSION.md`. Worktree, local-only. |

Shipped today: `compose.yaml` now has real `stage` and `ears-meet` services
(`19fde09`). The Meet stack is one `docker compose --profile meet up` away from
running — it just has no account to be yet. That is step 1 above.
