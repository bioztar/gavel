// The two things the extension does to the real event through the Calendar API:
// write the description and add the bot as a guest. Runs in the service worker
// with the Google token from `auth.ts`; the scope is `calendar.events.owned`,
// so this can only touch events the signed-in user owns — which is exactly the
// set of events they can edit an agenda into.
//
// Google's API answers CORS for any origin, so no `host_permissions` entry is
// needed for `www.googleapis.com`.

import type { Person } from "../lib/types.js";
import { cleanText, dedupePeople, personFrom } from "../lib/sanitize.js";

export const GOOGLE_CALENDAR_BASE = "https://www.googleapis.com/calendar/v3";

export class CalendarApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

interface ApiAttendee {
  email?: string;
  displayName?: string;
  responseStatus?: string;
  organizer?: boolean;
  self?: boolean;
  resource?: boolean;
}

interface ApiEvent {
  id: string;
  summary?: string;
  description?: string;
  start?: { dateTime?: string; date?: string; timeZone?: string };
  end?: { dateTime?: string; date?: string; timeZone?: string };
  attendees?: ApiAttendee[];
  conferenceData?: { conferenceId?: string };
  hangoutLink?: string;
  organizer?: { email?: string; displayName?: string; self?: boolean };
}

export interface CalendarEvent {
  id: string;
  title: string;
  description: string;
  start: string | null;
  end: string | null;
  attendees: Person[];
  meetCode: string | null;
  rawAttendees: ApiAttendee[];
}

type Fetch = typeof fetch;

async function request<T>(fetchImpl: Fetch, base: string, token: string, path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetchImpl(`${base}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { error?: { message?: string } };
      if (body.error?.message) msg = body.error.message;
    } catch {
      /* keep status text */
    }
    throw new CalendarApiError(res.status, msg);
  }
  return (await res.json()) as T;
}

function toEvent(e: ApiEvent): CalendarEvent {
  const attendees = dedupePeople(
    (e.attendees ?? [])
      .filter((a) => !a.resource)
      .map((a) => personFrom(a.displayName, a.email))
      .filter((p): p is Person => p !== null),
  );
  return {
    id: e.id,
    title: cleanText(e.summary ?? "", 200),
    description: cleanText(e.description ?? "", 20_000),
    start: e.start?.dateTime ?? null,
    end: e.end?.dateTime ?? null,
    attendees,
    meetCode: meetCodeFrom(e),
    rawAttendees: e.attendees ?? [],
  };
}

function meetCodeFrom(e: ApiEvent): string | null {
  const id = e.conferenceData?.conferenceId;
  if (id && /^[a-z]{3}-[a-z]{4}-[a-z]{3}$/.test(id)) return id;
  const m = e.hangoutLink?.match(/meet\.google\.com\/([a-z]{3}-[a-z]{4}-[a-z]{3})/);
  return m?.[1] ?? null;
}

/** `base` is Google's API in production; a dev build pointed at the mock uses
 *  `<serverUrl>/mock/gcal/calendar/v3`, which speaks the same three routes. */
export function createCalendar(base: string = GOOGLE_CALENDAR_BASE, fetchImpl: Fetch = fetch) {
  return {
    async get(token: string, eventId: string): Promise<CalendarEvent> {
      const e = await request<ApiEvent>(fetchImpl, base, token, `/calendars/primary/events/${encodeURIComponent(eventId)}`);
      return toEvent(e);
    },

    /** The event whose Meet code this is, if the user owns one within ±12h. */
    async findByMeetCode(token: string, meetCode: string, now = new Date()): Promise<CalendarEvent | null> {
      const from = new Date(now.getTime() - 12 * 3600_000).toISOString();
      const to = new Date(now.getTime() + 12 * 3600_000).toISOString();
      const q = new URLSearchParams({ timeMin: from, timeMax: to, singleEvents: "true", maxResults: "50" });
      const page = await request<{ items?: ApiEvent[] }>(fetchImpl, base, token, `/calendars/primary/events?${q}`);
      const hit = (page.items ?? []).find((e) => meetCodeFrom(e) === meetCode);
      return hit ? toEvent(hit) : null;
    },

    /** One PATCH: the new description and, if missing, the bot as a guest.
     *  `sendUpdates=all` so the guests get the agenda in the update mail, the
     *  same way a compose-created `.ics` reached them. */
    async writeAgenda(token: string, event: CalendarEvent, description: string, botEmail: string): Promise<{ botInvited: boolean }> {
      const already = event.rawAttendees.some((a) => (a.email ?? "").toLowerCase() === botEmail.toLowerCase());
      const attendees = already ? event.rawAttendees : [...event.rawAttendees, { email: botEmail }];
      await request<ApiEvent>(fetchImpl, base, token, `/calendars/primary/events/${encodeURIComponent(event.id)}?sendUpdates=all`, {
        method: "PATCH",
        body: JSON.stringify({ description, attendees }),
      });
      return { botInvited: true };
    },
  };
}

export type Calendar = ReturnType<typeof createCalendar>;
