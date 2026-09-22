# @gavel/extension — "Chair this meeting"

A Manifest V3 browser extension that puts the `/compose` flow where meetings
are actually created: a **Chair this meeting** button in the Google Calendar
event editor and on the Google Meet pre-join screen. The host writes the brief
in place; the server turns it into an agenda; the extension writes that agenda
into the real invite, adds the gavel bot as a guest, and registers the
contract-shaped `agenda.json` (`docs/CONTRACT.md` §1) against the meeting.

The refusal gate from `/compose` moves with it, unchanged: if the reading of
the brief has no topics, nothing is written and the panel asks, inline,
**"What does this call have to decide?"**

The extension never calls a model and holds no provider credential. The only
thing it sends off the page is the brief (plus the guest list), to
`packages/calendar`; the model call, the provider keys and the database stay
there. The server half is *specified* below and *mocked* in `mock/` — it is
not implemented in this package (see "Server endpoints").

## Layout

```
public/manifest.json      MV3 manifest — permissions: identity, storage; no host_permissions
public/options.html       options page: server origin, (dev) mock sign-in, sign out
src/background/           service worker: sign-in, tokens, server calls, Calendar API
  auth.ts                 getAuthToken → launchWebAuthFlow; tokens in chrome.storage.session
  gcal.ts                 the three Calendar API calls (get, list-by-Meet-code, patch)
  index.ts                message handler: whoami / config / lookup / draft / register
  settings.ts             non-secret settings in chrome.storage.local
src/content/              content scripts: Calendar editor and Meet pre-join
  calendar-dom.ts         reads title / guests / times / description out of the editor
  meet-dom.ts             reads the Meet code and title off the pre-join screen
  launcher.ts, panel.ts   the injected button and the brief → gate → confirm → done panel
src/lib/                  pure, tested: sanitize, gate, agenda (contract §1), description
mock/server.mjs           dependency-free stand-in for the server and for Google's API
mock/fixtures/            static pages shaped like the Calendar editor and Meet pre-join
scripts/build.mjs         esbuild → dist/ (prod) or dist-dev/ (--dev)
scripts/audit-bundle.mjs  tripwires: no eval/remote code/credential-shaped strings/broad matches
test/                     vitest, no network
```

## Prerequisites

- Node 22+ (`engines` in `package.json`); the mock has no dependencies.
- Chrome 116+ (or Edge / any Chromium with `chrome.identity`).

## Load and test it locally (no Google account, no model)

```bash
cd packages/extension
npm ci
npm run build:dev            # → dist-dev/ (adds the mock's fixture pages to `matches`)
npm run mock                 # http://localhost:8790, keep it running
```

Then in Chrome:

1. `chrome://extensions` → turn on **Developer mode** → **Load unpacked** →
   pick `packages/extension/dist-dev`.
2. Open <http://localhost:8790/fixtures/> and follow a link:
   - **Calendar editor, new event** — `/fixtures/calendar.html`. Type a title,
     add guests (`ana@example.com`, `artem@example.com`), then click
     **Chair this meeting** next to *Save*.
   - **Calendar editor, existing event** — `/fixtures/eventedit/…` prefilled
     from the seeded event `abc123def456ghi`; the "Done" step patches it through
     the mock Calendar API instead of editing the DOM.
   - **Meet pre-join** — `/fixtures/meet/abc-defg-hij`. The extension resolves
     the Meet code to the seeded event through the (mock) Calendar API and reads
     the guests from there.
3. The dev build signs in with a fixed mock bearer (options page → *Use the
   mock sign-in*). Turn it off to exercise the real `chrome.identity` path —
   you then need a Google OAuth client id, see "Building for real".

### Two briefs to try

Refusal (no decidable topic — the gate):

```
Weekly sync
Catch up with the team on how the week went.
```

Agenda (mock "model" is rule-based: one topic per line shaped like
`Topic — Owner, N min`, or a sentence with decide/agree/pick/choose/approve/settle):

```
Ship review
Decide whether we ship Thursday.
Pricing — Ana, 10 min
Rollout — Artem, 15 min
```

Answering the gate's question with one or more topic lines re-drafts with the
brief + `Agenda:` + your lines, exactly as `/compose` does. A useless answer
refuses again.

### What to check after "Done"

- The description in the editor (or, for existing events, in the mock event —
  `GET http://localhost:8790/mock/gcal/calendar/v3/calendars/primary/events/abc123def456ghi`
  with any `Authorization: Bearer …`) contains one `— gavel agenda — … — end of
  agenda —` block. Running the flow again replaces the block; text the host
  wrote around it survives.
- `gavel-bot@example.com` is on the guest list.
- <http://localhost:8790/mock/agendas> shows the registered contract agenda:
  `sessionId`, `purpose`, `totalSeconds`, `attendees[].{discordId,name,role}`,
  `topics[].{id,title,goal,budgetSeconds,owner,mustHear,questions,type}`,
  `policy`.

Force the other server outcomes without changing the brief by sending the
header `X-Mock-Draft: empty | null | error` to `/ext/v1/agenda/draft` (e.g.
with curl; the extension itself does not set it).

## Checks

```bash
npm run typecheck                 # tsc --noEmit
npm test                          # vitest: gate, agenda mapping, description writer, sanitize
npm run build                     # → dist/ (production: no localhost, no mock sign-in)
node scripts/audit-bundle.mjs     # fails on eval / new Function / importScripts / remote
                                  # script or import / credential-shaped literals /
                                  # <all_urls> or *://*/* / weak CSP / undeclared bundles
node scripts/audit-bundle.mjs --dev   # same on dist-dev/
npm run check                     # all of the above on dist/
```

## Building for real

```bash
GAVEL_GOOGLE_CLIENT_ID=<the OAuth client id> npm run build     # → dist/
```

`GAVEL_GOOGLE_CLIENT_ID` is the **client id** of a Google Cloud OAuth client of
type *Chrome Extension* (item id = the extension id). A client id is public by
design — it is what the consent screen shows — and is the only value the build
reads from the environment. There is no client secret anywhere in this flow:
`getAuthToken` uses Chrome's own account, `launchWebAuthFlow` uses the implicit
grant (`response_type=token`). If the variable is unset the build still
succeeds with a visible placeholder and sign-in fails with an error naming the
setting.

Set the server origin on the options page (toolbar icon). Production builds
accept `https://` origins only.

### Scopes

| Scope | Why |
| --- | --- |
| `https://www.googleapis.com/auth/calendar.events.owned` | read and write the events the signed-in user owns — the ones they can put an agenda into |
| `https://www.googleapis.com/auth/userinfo.email` | the server binds the session to an address |

Nothing org-wide, nothing read-all-calendars, no Directory, no Drive.

### Where things live

| Thing | Where | Never |
| --- | --- | --- |
| Google access token | service worker, `chrome.storage.session` | `localStorage`, content script, page |
| Our session token | service worker, `chrome.storage.session` | same |
| Server origin, mock flag | `chrome.storage.local` (not secret) | — |
| Model call, provider keys, DB writes | `packages/calendar` | the extension |

Content scripts talk to the worker with `chrome.runtime.sendMessage` only and
carry no URL and no token. Everything read off the page goes through
`src/lib/sanitize.ts` before it is rendered (`textContent` only) or sent.

## Server endpoints (to be implemented in `packages/calendar`)

All under the origin set on the options page. JSON in and out. The server must
answer CORS preflights from `chrome-extension://<id>` (`Authorization`,
`Content-Type`); the extension declares no `host_permissions` for it on purpose.
Except for `POST /ext/v1/session`, every call carries
`Authorization: Bearer <sessionToken>`.

### `POST /ext/v1/session` — exchange a Google token for our session

No auth. Request:

```json
{ "provider": "google", "accessToken": "<Google OAuth access token>" }
```

Server: verify the token with Google (`tokeninfo`/`userinfo`), check the
`aud` is our client id and the scopes include `calendar.events.owned`, then
mint a session. Response `200`:

```json
{ "sessionToken": "…", "expiresAt": "2026-09-22T02:00:00Z", "user": { "email": "host@example.com", "name": "Vitaly" } }
```

`401` if the Google token is bad. The Google token is not stored server-side
beyond the exchange; the extension keeps it to write the event itself.

### `GET /ext/v1/config` — the bot account

Response `200`: `{ "botEmail": "gavel-bot@example.com" }` — the account the
extension adds as a guest so the chair can join the Meet.

### `POST /ext/v1/agenda/draft` — the model call

Request (`Person` = `{ "name": string, "email": string }`):

```json
{
  "brief": "Ship review\nDecide whether we ship Thursday.\nPricing — Ana, 10 min\nRollout — Artem, 15 min",
  "attendees": [ { "name": "Vitaly", "email": "host@example.com" }, { "name": "Ana", "email": "ana@example.com" } ],
  "now": "2026-09-21T18:00:00.000Z",
  "timezone": "Europe/Madrid"
}
```

Response `200` — `packages/calendar`'s `llm.ParsedBrief`, camel-cased, or
`null` when the model failed or returned something unusable:

```json
{
  "parsed": {
    "title": "Ship review",
    "purpose": "Decide whether we ship Thursday",
    "start": "2026-09-25T10:00:00+02:00",
    "durationMinutes": 30,
    "topics": [
      { "title": "Pricing", "minutes": 10, "owner": "Ana", "mustHear": ["Ana"], "type": "discussion" }
    ]
  }
}
```

`topics: []` or `parsed: null` is the signal the gate refuses on — do not
invent topics server-side. The brief is untrusted user text; treat it as
prompt input only.

### `POST /ext/v1/agendas` — register the agenda

Request:

```json
{
  "meeting": { "provider": "google", "eventId": "abc123def456ghi", "meetCode": "abc-defg-hij",
               "title": "Ship review", "start": "2026-09-25T10:00:00+02:00", "end": "2026-09-25T10:30:00.000Z" },
  "agenda": { "…docs/CONTRACT.md §1 agenda.json…" : "sessionId, purpose, totalSeconds, attendees, topics, policy" },
  "attendees": [ { "name": "Vitaly", "email": "host@example.com" } ],
  "enforcement": "medium"
}
```

`eventId` and `meetCode` are `null` for a brand-new, unsaved event (the
extension then writes the description into the editor instead of through the
API). `agenda.attendees[].discordId` carries the **email** — the server maps
emails to Discord ids when the bot joins, as `compose.py` does today.

Response `201`:

```json
{ "sessionId": "a43cba0b116a", "joinUrl": "https://gavel.example.com/join/a43cba0b116a" }
```

**The server MUST answer `422` when `agenda.topics` is empty** (and when there
is no `role: "host"` attendee). This is the enforced half of the refusal gate,
not a nicety: `src/lib/gate.ts` runs in a content script, which is public code
anyone can edit, so until this endpoint rejects empty agendas the gate is
advisory and a modified client can register a meeting with nothing to decide.
`joinUrl` goes into the invite description.

## What is mocked

`mock/server.mjs` (Node, no dependencies) stands in for two things:

| Real thing | Mock | Behaviour |
| --- | --- | --- |
| `POST /ext/v1/session` | same path | any non-empty bearer → a session as `host@example.com` |
| `GET /ext/v1/config` | same path | `gavel-bot@example.com` |
| `POST /ext/v1/agenda/draft` (the model) | same path | **rule-based**: `Topic — Owner, N min` lines and decide/agree/pick/… sentences become topics; anything else → `topics: []` |
| `POST /ext/v1/agendas` | same path | in-memory; `422` on empty agenda; join URL on `localhost:8790` |
| Google Calendar API | `/mock/gcal/calendar/v3/…` | `GET events/:id`, `GET events?timeMin…` (Meet-code lookup), `PATCH events/:id` — two seeded events, one with Meet code `abc-defg-hij` |
| Google sign-in | dev build + *mock sign-in* | a fixed bearer instead of `chrome.identity` |
| calendar.google.com / meet.google.com | `/fixtures/…` | static pages using the same `aria-label`s the content scripts look for |

Not mocked, and worth knowing: Google's real editor DOM changes without notice.
`calendar-dom.ts` and `meet-dom.ts` look for stable accessible names
(`aria-label="Add title"`, `role="textbox"[aria-label="Description"]`,
`Join now`). Whatever cannot be read is left for the host to fill in the panel
(the brief and the confirm table are editable), and when a write into the
editor cannot be placed the "Done" step says what to do by hand instead of
claiming it happened.
