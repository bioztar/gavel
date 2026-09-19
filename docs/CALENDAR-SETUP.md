# Getting a calendar invite into gavel

gavel reads your calendar through its **secret iCal feed** — a private URL Google gives every
calendar. No OAuth, no Google Cloud project, no "this app isn't verified" warning on stage.
Read-only: gavel can see your events, it can never write to your calendar.

## 1. Get the feed URL (Google — `vitaly.alt@gmail.com`)

**Desktop browser only.** The mobile app cannot do this.

1. Open <https://calendar.google.com>, signed in as `vitaly.alt@gmail.com`.
2. Left sidebar → hover the calendar you'll put the demo invite in → **⋮** → **Settings and sharing**.
3. Scroll to **Integrate calendar**.
4. Copy **Secret address in iCal format** — the long one ending in `.../basic.ics`.

> **That URL is a password.** Anyone holding it can read every event on that calendar,
> forever, with no login. Do not paste it into chat, a ticket, or a commit. If it leaks,
> the same page has **Reset** next to it, which invalidates the old one immediately.

## 2. Put it where gavel reads it

Append it to the repo-root `.env` **yourself**, in your own terminal — not through an agent:

```
printf 'CALENDAR_ICS_FEEDS=%s\n' 'PASTE_THE_URL_HERE' >> /home/coder/DEV/gavel/.env
```

Two calendars? Comma-separated, no spaces:

```
CALENDAR_ICS_FEEDS=https://…/basic.ics,https://…/basic.ics
```

`.env` is gitignored. Confirm it landed without revealing it:

```
grep -c '^CALENDAR_ICS_FEEDS=' /home/coder/DEV/gavel/.env     # expect 1
```

## 3. Write the invite so gavel understands it

Title and time come from the event. **The agenda lives in the description.** Topics are
bulleted or numbered lines; `goal:` and `q:` go on their own indented lines under a topic.

```
Decide the launch date and name an owner for each blocker

Agenda:
- Where we actually are — 2m (owner: Ana, must hear: Marc)
  goal: one clear picture everyone agrees on
- The date - 2m (owner: Vitaly)
  q: what happens if launch slips a week?
- Blocker owners (1 min)
```

Accepted shapes, because real invites vary:

| Shape | Example |
|---|---|
| dash + em-dash minutes | `- Pricing — 10m (owner: Artem)` |
| numbered + parens | `1. Pricing (10 min)` |
| star + hyphen | `* Pricing - 10 minutes` |
| owner and must-hear, order-free | `- Pricing — 10m (owner: Ana, must hear: Marc, Ana)` |

`owner:` and `must hear:` are both optional. `must hear:` is what arms the chair's "this
person hasn't spoken and we're 70% through the budget" nudge — without it that trigger is
dead for the meeting. Anything that isn't a bullet, and isn't a `goal:`/`q:` line under one,
is ignored rather than mis-parsed.

Attendee emails map to Discord speakers via `CALENDAR_ATTENDEE_MAP`
(`email1=discordId1,email2=discordId2`) — see `packages/calendar/README.md`.

## 4. What happens next

The scheduler polls each feed every `SCHEDULER_POLL_SECONDS` (default 30). A new event inside
the next 24 hours is parsed into the agenda, gets a join page, and starts on its own at the
event's start time. The board page lists what's upcoming with a Join button to start early.

**The one thing a read-only feed cannot do:** write the join link back into the calendar
event. So the flow is *open gavel's board → Join*, not *open the event → click a link inside
it*. Putting the link inside the event needs full Google Calendar OAuth — a Google Cloud
project and a consent screen, which is the trade we deliberately declined.

## `vitaly@pro7ocol.com` — different, and worse

pro7ocol mail is **Proton**, not Google, so step 1 doesn't apply. Proton Calendar can produce
a subscribable link (Settings → All settings → Calendars → pick the calendar → **Share with
anyone** → **Create link** → **Full view**, which is required — "Limited view" is busy/free
only and carries no description, so no agenda). Two catches:

- **Paid Proton plan only.**
- **Updates take up to eight hours to propagate.** That is Proton's documented ceiling, and
  it makes the feed unusable for a live demo where you create an invite and expect the chair
  to pick it up.

So: **demo from the Gmail calendar.** The Proton feed can be added as a second entry in
`CALENDAR_ICS_FEEDS` and will work for meetings scheduled well in advance. For anything
same-day on pro7ocol, export the `.ics` and hand it to `POST /invite` — that path still works
and is instant.
