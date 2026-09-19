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
| `GET /m/{sessionId}` | The join page: title, start/end, purpose, agenda with budgets and owners, who is expected, one **Join** button. |
| `POST /m/{sessionId}/join` | Forces the session to start now. Same call the scheduler makes automatically at the event's start time. |
| `GET /board` | Upcoming ingested meetings (manual invites and polled feed events alike), each with its own **Join** button — the demo path from "meeting exists" to "session running" when nothing wrote a join link back into the calendar. |
| `GET /health` | `{status, pending, feeds}` — `feeds` is per-`CALENDAR_ICS_FEEDS` entry, addressed by index only: `{feed, lastSuccess, eventCount, lastError}`. Never the feed URL. |

## The `.ics` parser

`src/gavel_calendar/ics_parser.py` uses the `icalendar` library for the RFC 5545
mechanics (line folding, `TZID=`, text escaping) — that is what differs between Google,
Outlook and a hand-written invite, and it is not worth re-implementing. It pulls title
(`SUMMARY`), start/end (`DTSTART`/`DTEND`, normalized to UTC — a floating time with no
`TZID` and no `Z` is *assumed* UTC), and attendees (`ATTENDEE` → name from `CN`, else the
email's local part; `ORGANIZER` becomes the `host` attendee).

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

- An attendee's `discordId` defaults to their **email** — stable and unique, but it will
  not match a real speaker's `speaking.start` frames until someone maps it.
- Set `CALENDAR_ATTENDEE_MAP` in `.env` to override known people:
  ```
  CALENDAR_ATTENDEE_MAP="vitaly@example.com=100000000000000001,ana@example.com=100000000000000002"
  ```
  Applied once, at parse time (`settings.py:attendee_map`, used by `agenda.py`).

This is the one real seam in this package — worth checking before the demo run, not
after.

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

`scheduler.py`'s `poll_feeds` fetches each feed every `SCHEDULER_POLL_SECONDS`, walks its
`VEVENT`s, and — for each one whose `UID`+`SEQUENCE` hasn't been seen before — re-serializes
that single `VEVENT` (plus any `VTIMEZONE` it references) and runs it through the *same*
`ics_parser.parse_ics` → `agenda.build_agenda` path `POST /invite` uses. There is exactly
one place that turns a `VEVENT` into an agenda, whether it arrived by hand or by feed.

- **Dedupe**: `UID`+`SEQUENCE`. An unchanged event is a no-op on re-poll. A bumped
  `SEQUENCE` updates the same `InviteRecord` in place — same `sessionId`, same join link —
  without resetting it to pending if it has already started (that would start a second
  `ears` session for the same meeting).
- **Forward window**: only events starting within `CALENDAR_FEED_WINDOW_HOURS` of "now"
  are ingested. A feed carries a year of history; without this, every poll would try to
  build a session for last March's standup.
- **No topic lines**: skipped quietly, same as `POST /invite` would accept it — it just
  never gets pulled onto the board, since `agenda.build_agenda` needs at least the
  description to scrape.
- **Recurring events (`RRULE`) are not expanded.** A weekly recurring meeting's `DTSTART`
  is its *first* occurrence — if that was months ago, it will never fall inside the
  forward window and the event will never be ingested. Only single, non-recurring events
  (or a recurring series' very next un-elapsed instance, if the feed happens to list one)
  are picked up. Worth checking on the actual demo calendar before relying on it.
- **A down or malformed feed** only marks its own `/health` entry — the scheduler, the
  other feeds, and the manual `POST /invite` path are unaffected.

Zero feeds configured: nothing changes. `POST /invite` remains the only way an invite
arrives, exactly as before this feature existed.

## Tests

```
just test    # or: uv run pytest
```

`tests/test_ics_parser.py` — three invite shapes (Google-style, Outlook-style,
hand-written) plus malformed-line and timezone/all-day edge cases, offline.
`tests/test_agenda_schema.py` — `fixtures/demo.ics` → `build_agenda` → validated against
the contract shape (`schema.py:ContractAgenda`), asserting exact field values (seconds
not minutes, `totalSeconds` from event duration).
`tests/test_app.py` — `POST /invite` → `GET /m/{id}` → `POST /m/{id}/join`, with `ears`
mocked at the HTTP boundary, plus `/board` and `/health`.
`tests/test_feeds.py` — the feed poller against a stubbed feed (`pytest-httpx`, no real
network): first ingest, unchanged re-poll, a `SEQUENCE` bump (including one that must not
restart an already-started session), no-topics and out-of-window skips, a malformed feed,
and an unreachable feed that must not block a healthy one.
