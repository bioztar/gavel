# gavel calendar

The demo's opening beat: Vitaly has a meeting on his calendar with an agenda in the
description. He opens the invite, clicks the link, and the chair is already in the call
with that agenda loaded.

This package turns a real `.ics` invite into the contract agenda
([`docs/CONTRACT.md`](../../docs/CONTRACT.md) §1) and serves a join page that starts the
session — either when someone clicks **Join**, or on its own at the event's start time.

## Run it

```
just setup   # uv sync
just run     # uvicorn on :8790 (CALENDAR_PORT)
```

or directly: `uv run python -m gavel_calendar`.

Needs `packages/ears-discord` running (default `http://localhost:8787`) — this package
calls it, never edits it.

## What it calls in `ears-discord`

Per the mission's own rule: read `ears`, never invent a second session concept.
`packages/ears-discord/src/ears/wire.py` already exposes the entry point:

```
POST http://localhost:8787/api/meetings   {title, context, agenda}   → {id, ...}
POST http://localhost:8787/api/sessions   {meetingId}                → {sessionId}
```

`service.start()` (`src/gavel_calendar/service.py`) calls both, in order, exactly once
per invite (locked, idempotent). The Join button and the scheduler both call it — see
`scheduler.py`. Nothing on this side stores a second copy of "the session"; the only
state kept here is the join-page record (title, agenda, whether it has been started, and
the `id`/`sessionId` `ears` handed back).

## HTTP surface

| | |
|---|---|
| `POST /invite` | Upload (`file`, multipart) or paste (`ics`, form field) a raw `.ics`. Returns `{sessionId, joinUrl}`. |
| `GET /m/{sessionId}` | **The meeting room** — one link for before, during and after. See below. |
| `GET /m/{sessionId}/state` | The JSON that page polls every 2 s: the chair's live view of *this* meeting, or the last one banked for it. |
| `POST /m/{sessionId}/join` | Forces the session to start now. Same call the scheduler makes automatically at the event's start time. |
| `GET /board` | Upcoming ingested meetings (manual invites and polled feed events alike), each with its own **Join** button — the demo path from "meeting exists" to "session running" when nothing wrote a join link back into the calendar. |
| `GET /health` | `{status, pending, feeds}` — `feeds` is per-`CALENDAR_ICS_FEEDS` entry, addressed by index only: `{feed, lastSuccess, eventCount, lastError}`. Never the feed URL. |
| `GET /` | 307 redirect to `/board`. |
| `GET /compose` | The "set up a meeting" front door: a plain-English brief form, prefilled with `COMPOSE_DEFAULT_ATTENDEES`. |
| `POST /compose/parse` | Sends the brief to the LLM, returns an editable confirmation form (title, start, duration, per-topic rows). No LLM configured, or the call fails: falls back to an empty/best-guess form instead of erroring — you can still fill it by hand and send. |
| `POST /compose/send` | Confirms the form. See below for what this does and in what order. |

## The meeting room — `GET /m/{sessionId}`

The link in the invite ("Agenda and live status") is the whole meeting's public face, and
**it is built to be screen-shared**: the organizer opens it and shares the tab, so the
board is what the room looks at for the whole meeting. One URL, three states:

| | |
|---|---|
| **before** | Karen's face, the agenda with budgets, and who is expected — with whoever has not arrived marked *not here yet*. |
| **during** | The topic and its clock against its budget; one line for who has the floor (and, if they have drifted, what off); what the chair has understood on this topic so far; the agenda ticking down; and along the bottom what has been decided, what is still open and what is parked. |
| **after** | The same board, frozen, with the picture dropped and the record given the screen: the report. |

**What is deliberately not on it:**

- *Anything Karen says.* The room can hear her; printing her lines next to a live meeting
  is one more thing pulling eyes off whoever is talking. Her log — every call, in her own
  words, labelled in English (`floorHog` → *Balanced the floor*) — is in the **Detail
  view**, one click away in the ⋯ menu and remembered per browser.
- *The talk-time meter.* It is what the chair acts on, not what the room needs to study
  mid-sentence, so the board keeps one line ("Vitaly is speaking · 66% of the floor") and
  the full per-person ledger lives in the detail view too.
- *Parked points*, in the topic summary. They are by definition not this topic; they have
  their own band.

Everything clickable lives in that menu for the same reason: **Join the call** (straight to
the Discord voice channel, never hidden — people arrive late), **Copy this link**, the
view toggle, and, before the meeting, **Start the meeting now**.

It is light on white, not dark. A projector has no black, only "no light", so dark-on-white
is the only thing that survives a lit room, and a mostly-white screen is what a call's video
compression keeps sharpest. Type is sized in `vh` throughout, so the board scales to
whatever it is shared on rather than to a laptop.

**Karen's face.** The page embeds chair-video's stage (`CHAIR_VIDEO_STAGE_URL`, `/stage/`
on the deployed host). Discord does not let a bot publish video at all — the shared tab is
how she gets a face in the call.

**Where the state comes from.** The brain's `/state` (`BRAIN_STATE_URL`), fetched
server-side — the browser never needs the brain's address, and the ears console's HTTP
auth is left where it is. Two rules matter:

- The brain chairs **one** session at a time and its `/state` says which. A state whose
  `sessionId` is not this record's is not shown under this link, or the next meeting's
  numbers would appear under this one's URL.
- It keeps nothing once the next session starts, so every live poll **banks** the snapshot
  on the invite record. That banked copy is the report.

An unreachable brain is not an error: the page falls back to the banked report, or to the
invite's own agenda. The agenda is server-rendered into the shell, so the link is worth
opening before anything is live and before a byte of JS has run.

## The `.ics` parser

`src/gavel_calendar/ics_parser.py` uses the `icalendar` library for the RFC 5545
mechanics (line folding, `TZID=`, text escaping) — that is what differs between Google,
Outlook and a hand-written invite, and it is not worth re-implementing. It pulls title
(`SUMMARY`), start/end (`DTSTART`/`DTEND`, normalized to UTC — a floating time with no
`TZID` and no `Z` is *assumed* UTC), and attendees (`ATTENDEE` → name from `CN`, else the
email's local part; `ORGANIZER` becomes the `host` attendee). `parse_ics` reads one
invite as a single occurrence; `parse_ics_occurrences` expands a recurring one — see
[Recurring events](#recurring-events).

Agenda topics are scraped from `DESCRIPTION`. Accepted line shapes (a few, on purpose):

```
- Pricing — 10m (owner: Artem)
1. Pricing (10 min)
* Pricing - 10 minutes
- Pricing — 10m (owner: Artem, must hear: Marc, Ana)
```

`owner` and `must hear` may appear together in the same `(...)`, in either order, both
optional. A topic line may be followed by indented `goal:` (single line) and repeatable
`q:` lines — they attach to the topic bullet directly above them:

```
- Pricing — 10m (owner: Artem, must hear: Marc, Ana)
  goal: one honest number per region
  q: what breaks if we wait a week?
  q: who signs off?
```

Any line that is not bulleted/numbered, and not an indented `goal:`/`q:` line right after
a topic, is not a topic and is silently skipped — it never raises. A topic line with no
parseable duration gets an even split of whatever time is left after the topics that did
state one (`agenda.py:_budget_seconds`).

## The attendee identity gap

An `.ics` gives a name and an email. The contract agenda needs a Discord snowflake in
`discordId` (attendees, `topics[].owner`, `topics[].mustHear`). There is no directory
mapping one to the other, so:

- An attendee's `discordId` defaults to their **email** — stable and unique, but it is not
  a snowflake and matches no speaker by itself.
- Set `CALENDAR_ATTENDEE_MAP` in `.env` to name the people you already know:
  ```
  CALENDAR_ATTENDEE_MAP="vitaly@example.com=100000000000000001,ana@example.com=100000000000000002"
  ```
  Applied once, at parse time (`settings.py:attendee_map`, used by `agenda.py`). This is
  the exact route, and the only one that cannot be wrong.
- Unmapped, the gap is closed **by name** on the other side of the contract: ears binds
  each expected attendee to the speaker in the channel whose display name reads as theirs
  when the session starts (`meetings.py:bind_attendees`), and brain does the same on every
  `participants` frame for everyone who joins later (`engine.ts:bindAttendees`). "Artem"
  matches `artemshambalev`; one speaker answers for one attendee; an unrecognizable name
  is left unbound rather than guessed at, and shows on the room page as still to arrive.

This is the one real seam in this package — worth checking before the demo run, not
after. The names on the invite are what it runs on, so write them as people are called in
Discord.

## Compose — "set up a meeting" front door

`src/gavel_calendar/compose.py` is the plain-English path onto the board, for when
nothing put an invite on Vitaly's calendar in the first place. Flow:

1. `GET /compose` — a brief textarea plus an attendees field (prefilled from
   `COMPOSE_DEFAULT_ATTENDEES`).
2. `POST /compose/parse` — `src/gavel_calendar/llm.py`'s `NebiusClient` sends the brief to
   Nebius (chat completions) and asks for `{title, start, duration_minutes, topics[]}` as
   JSON. The result renders as an editable form — every field, including per-topic minutes,
   owner, and must-hear, can be corrected by hand before sending. `NEBIUS_API_KEY` unset, or
   the call fails or returns something that doesn't match the schema: the form still renders,
   just empty/best-guess instead of LLM-filled. This path never raises — a flaky or
   unconfigured LLM degrades to manual entry, it does not block the meeting.
3. `POST /compose/send` — in this exact order:
   1. Builds the contract agenda (`agenda.py:build_agenda`, same code `.ics` ingestion uses)
      and saves the `InviteRecord` to the in-memory `InviteStore`. The join URL
      (`/m/{sessionId}`) works from this point on, regardless of what happens next.
   2. Hands the meeting to ears and starts its session (`service.start`, the same call the
      Join button and the scheduler make, and idempotent with both). From here the chair is
      holding *this* meeting with *this* agenda, before anyone reaches the voice channel —
      what it opens is a lobby, not a running meeting (docs/CONTRACT.md §2). ears down or
      refusing costs the head start and nothing else: the record is already saved, the
      success page says Karen has not been handed it, and the scheduler starts it at the
      event's own time. `tests/test_compose.py::test_handle_send_survives_ears_being_down`.
   3. Builds a `.ics` file (`ics_writer.py:build_ics`) — the same topic-line format
      `ics_parser.py` reads, so a compose-created invite round-trips exactly like a
      hand-written one (see `tests/test_ics_writer.py`).
   4. Best-effort emails that `.ics` via Resend (`mailer.py:send_invite`) to the parsed
      attendees. **A mailer failure — missing key, bad request, network error, even an
      unexpected exception — is caught and never fails the meeting.** No `RESEND_API_KEY` or
      no `COMPOSE_FROM_EMAIL`: the mailer dry-runs (logs what it would have sent, returns
      `sent=False`) instead of calling out. See `tests/test_compose.py`'s
      `test_handle_send_survives_mailer_raising` for the worst case this guards.
   5. Renders a success page: the meeting room URL, the Discord link
      (`DISCORD_MEETING_URL`), the parsed agenda, whether the email actually sent, and
      whether Karen is holding the room.

Resend setup: create an API key at resend.com, verify a sending domain there, and set
`COMPOSE_FROM_EMAIL` to an address on that domain — Resend rejects sends from an unverified
domain, which is exactly the failure `_safe_mail` is built to absorb without touching the
meeting.

## Config (`.env`, repo root — never printed, never committed)

| Var | Default | |
|---|---|---|
| `CALENDAR_HOST` / `CALENDAR_PORT` | `127.0.0.1` / `8790` | this service |
| `CALENDAR_PUBLIC_URL` | `http://localhost:8790` | used to build the `joinUrl` in `POST /invite`'s response |
| `EARS_API_URL` | `http://localhost:8787` | ears-discord's HTTP API (same host/port as `EARS_WIRE_URL`, `http://` not `ws://`) |
| `CALENDAR_ATTENDEE_MAP` | empty | see above |
| `SCHEDULER_POLL_SECONDS` | `30` | upper bound on how late the scheduler notices a new invite, and the feed poll interval |
| `CALENDAR_ICS_FEEDS` | empty | comma-separated Google Calendar feed URLs — see below |
| `CALENDAR_FEED_WINDOW_HOURS` | `24` | only feed events starting within this window from "now" are ingested |
| `NEBIUS_API_KEY` | empty | shared with `packages/brain` — powers `POST /compose/parse`. Empty: compose still works, form starts blank/best-guess instead of LLM-filled |
| `RESEND_API_KEY` | empty | powers `POST /compose/send`'s email step. Empty: mailer dry-runs, meeting is still created and the join link still works |
| `COMPOSE_FROM_EMAIL` | empty | must be on a Resend-verified sending domain |
| `COMPOSE_DEFAULT_ATTENDEES` | see `.env.example` | `"Name <email>, Name <email>, ..."` — prefills `GET /compose` |
| `DISCORD_MEETING_URL` | see `.env.example` | the `.ics` `LOCATION`, the success page's Discord link, and the room page's **Join the call** |
| `BRAIN_STATE_URL` | `http://localhost:8788/state` | the chair's live view, for the meeting room. Unreachable: the room shows the banked report or the agenda |
| `CHAIR_VIDEO_STAGE_URL` | `/stage/` | Karen's face, embedded in the room. Relative by default — Traefik routes `/stage/` to chair-video on the deployed host |
| `COMPOSE_TIMEZONE` | `Europe/Madrid` | IANA name — what relative times like "in an hour" resolve against |

Missing/invalid config fails with the setting's name — no value is ever read into a log
or an error message.

## Google Calendar, read-only

No OAuth, no Google Cloud project, no consent screen — Vitaly picked this over full
Calendar API access deliberately, to avoid an unverified-app warning mid-demo. Instead:
Google Calendar → Settings → a calendar → **Integrate calendar** → **Secret address in
iCal format**. That URL is a bearer credential: anyone holding it can read the whole
calendar, forever (there is no scoped read-only alternative short of full OAuth). Put it
in `CALENDAR_ICS_FEEDS` in the repo-root `.env`, comma-separated for more than one
calendar. It is never logged, never returned by `/health`, never put in an error message;
code that needs to name a feed uses its index (`feed[0]`), never the URL. **Never commit
a real feed URL** — `.env.example` carries the variable name only.

`scheduler.py`'s `poll_feeds` fetches each feed every `SCHEDULER_POLL_SECONDS`, groups its
`VEVENT`s by `UID`, and re-serializes each group (plus any `VTIMEZONE` it references) into
its own `.ics`, which it expands into occurrences and runs through the *same*
`ics_parser` → `agenda.build_agenda` path `POST /invite` uses. There is exactly one place
that turns a `VEVENT` into an agenda, whether it arrived by hand or by feed.

- **Dedupe**: occurrence id + `SEQUENCE`. An unchanged event is a no-op on re-poll. A bumped
  `SEQUENCE` updates the same `InviteRecord` in place — same `sessionId`, same join link —
  without resetting it to pending if it has already started (that would start a second
  `ears` session for the same meeting).
- **Forward window**: only events starting within `CALENDAR_FEED_WINDOW_HOURS` of "now"
  are ingested. A feed carries a year of history; without this, every poll would try to
  build a session for last March's standup.
- **No topic lines**: skipped quietly, same as `POST /invite` would accept it — it just
  never gets pulled onto the board, since `agenda.build_agenda` needs at least the
  description to scrape.
- **Recurring events are expanded** inside the forward window — see below.
- **A down or malformed feed** only marks its own `/health` entry — the scheduler, the
  other feeds, and the manual `POST /invite` path are unaffected.

Zero feeds configured: nothing changes. `POST /invite` remains the only way an invite
arrives, exactly as before this feature existed.

## Recurring events

A weekly standup's `DTSTART` is its *first* occurrence, usually months in the past, so a
series has to be expanded before anything about "the next one" is true.
`ics_parser.parse_ics_occurrences` does that for the feed poller: it takes the master
`VEVENT` plus any `RECURRENCE-ID` overrides sharing its `UID` and returns one
`ParsedInvite` per occurrence starting inside the query window (the same
`CALENDAR_FEED_WINDOW_HOURS` window, both ends inclusive). The recurrence maths is
`python-dateutil`'s `rruleset` — none of it is hand-rolled here.

Supported:

- `RRULE` with `FREQ=DAILY|WEEKLY|MONTHLY|YEARLY`, `INTERVAL`, `COUNT`, `UNTIL`, and the
  `BY*` parts dateutil implements (`BYDAY`, `BYMONTHDAY`, `BYMONTH`, …).
- `RDATE` extra occurrences and `EXDATE` exclusions, date- or datetime-valued.
- `RECURRENCE-ID` overrides: a moved or edited instance **replaces** the generated one
  (same occurrence id, keyed on the instance's *original* start), wherever it moved to,
  and never appears twice. An override dragged into the window from outside it shows up;
  one dragged out of it does not.
- Timezones: a `TZID` `DTSTART` expands in its own zone, so 09:30 Madrid stays 09:30
  Madrid across a DST change; `UNTIL` is read as UTC-anchored even then; a floating
  `DTSTART` (no `TZID`, no `Z`) is assumed UTC, same as everywhere else in this package;
  an all-day (`VALUE=DATE`) series lands on UTC midnight and keeps its whole-day length.
- Occurrence ids: `UID` for a single event, `UID::<start, UTC basic form>` for one
  instance of a series, exposed as `ParsedInvite.occurrence_uid` and hashed into the
  `sessionId` by `scheduler._session_id_for`. Deterministic, so polling the same
  occurrence twice is the same meeting, and distinct, so two occurrences are never one
  record. Dedupe is now `occurrence_uid`+`SEQUENCE` (a series shares the highest
  `SEQUENCE` of its `VEVENT`s, so any edit re-ingests the whole series in place).
- Runaway guard: an `RRULE` with neither `COUNT` nor `UNTIL` is infinite. Generation is
  lazy and bounded first by the window and then by `ics_parser.MAX_OCCURRENCES_PER_EVENT`
  (500), so a decade-wide window or a minutely rule cannot flood the board.

Not implemented:

- `RRULE` parts dateutil does not handle, and `BYSETPOS`-heavy or `WKST`-sensitive rules
  are only as correct as dateutil is — untested here.
- `RANGE=THISANDFUTURE` on a `RECURRENCE-ID`: the override is applied to that one
  instance only, not to the rest of the series.
- `VEVENT`s of the same series split across *different* feeds, or an override arriving in
  a later poll than its master (it is applied from the poll where both are present).
- `EXRULE` (deprecated in RFC 5545), `VALARM`, `DURATION` instead of `DTEND` (an event
  with no `DTEND` is zero-length, as before), and non-Gregorian `CALSCALE`.
- Nothing rewrites the calendar: this is read-only expansion, and occurrences live in the
  in-memory store like any other invite.

`tests/fixtures/*.ics` + `tests/test_recurrence.py` cover each of the supported cases
against fixed dates. No test touches the network, and no fixture contains a feed URL.

## Tests

```
just test    # or: uv run pytest
```

`tests/test_ics_parser.py` — three invite shapes (Google-style, Outlook-style,
hand-written) plus malformed-line and timezone/all-day edge cases, offline.
`tests/test_recurrence.py` — recurrence expansion against `tests/fixtures/*.ics`: a weekly
`BYDAY` standup (including across a DST change), monthly, `COUNT`+`INTERVAL`, a UTC-anchored
`UNTIL`, `EXDATE`, a `RECURRENCE-ID` override, an all-day series, a non-recurring event, and
the window/cap bounds on an endless `RRULE` — all with exact expected datetimes, offline.
`tests/test_agenda_schema.py` — `fixtures/demo.ics` → `build_agenda` → validated against
the contract shape (`schema.py:ContractAgenda`), asserting exact field values (seconds
not minutes, `totalSeconds` from event duration).
`tests/test_app.py` — `POST /invite` → `GET /m/{id}` → `POST /m/{id}/join`, with `ears`
mocked at the HTTP boundary, plus `/board` and `/health`.
`tests/test_feeds.py` — the feed poller against a stubbed feed (`pytest-httpx`, no real
network): first ingest, unchanged re-poll, a `SEQUENCE` bump (including one that must not
restart an already-started session), no-topics and out-of-window skips, a malformed feed,
and an unreachable feed that must not block a healthy one.
`tests/test_ics_writer.py` — `build_ics` round-trips through our own `ics_parser.parse_ics`
byte-for-byte on agenda content, including an uneven whole-minute topic split.
`tests/test_llm.py` — `NebiusClient.parse_brief` against a stubbed Nebius endpoint: success,
fenced-markdown JSON, malformed JSON, HTTP errors, and schema mismatches all resolve to
`None` rather than raising.
`tests/test_mailer.py` — `send_invite` dry-runs on missing key/from-address, and never raises
on a bad status or a network error.
`tests/test_compose.py` — the compose helpers and `handle_send` in isolation (fake
`Settings`, no real `.env`/network), including the mailer-raises-but-meeting-survives case.
`tests/test_compose_routes.py` — the three compose routes through the real app
(`TestClient`), proving the join link works immediately after `POST /compose/send`.
