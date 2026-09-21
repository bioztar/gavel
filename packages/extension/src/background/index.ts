// The service worker. It is the only place that holds a token, the only place
// that talks to our server or to Google's API, and the only place that trusts
// its own inputs — everything arriving from a content script is re-validated.

import { ApiError, createApi } from "../lib/api.js";
import { isRegistrable } from "../lib/agenda.js";
import { writeAgenda } from "../lib/description.js";
import { isRequest, type ErrorKind, type Request, type Response, type WriteReport } from "../lib/messages.js";
import { cleanEmail, cleanEventId, cleanMeetCode, cleanText, dedupePeople, personFrom } from "../lib/sanitize.js";
import type { ContractAgenda, Person, RegisterRequest } from "../lib/types.js";
import { AuthCancelled, NotSignedIn, currentUser, googleToken, signOut, withSession } from "./auth.js";
import { CalendarApiError, GOOGLE_CALENDAR_BASE, createCalendar } from "./gcal.js";
import { loadSettings } from "./settings.js";

const CALENDAR_ORIGINS = new Set(["https://calendar.google.com", "https://meet.google.com"]);

function fromOurContentScript(sender: chrome.runtime.MessageSender): boolean {
  if (sender.id !== chrome.runtime.id || !sender.url) return false;
  const origin = new URL(sender.url).origin;
  if (origin === `chrome-extension://${chrome.runtime.id}`) return true; // options page
  if (!sender.tab) return false;
  if (CALENDAR_ORIGINS.has(origin)) return true;
  // Dev builds also inject into the fixture pages served by the mock.
  return __DEV_BUILD__ && /^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(origin);
}

function fail(error: ErrorKind, detail: string): Response {
  return { ok: false, error, detail };
}

function classify(err: unknown): Response {
  if (err instanceof AuthCancelled) return fail("auth-cancelled", err.message);
  if (err instanceof NotSignedIn) return fail("not-signed-in", err.message);
  if (err instanceof CalendarApiError) return fail("calendar-write-failed", err.message);
  if (err instanceof ApiError) {
    if (err.status === 0) return fail("server-unreachable", err.message);
    if (err.status === 401 || err.status === 403) return fail("not-signed-in", err.message);
    return fail("server-refused", err.message);
  }
  return fail("server-unreachable", err instanceof Error ? err.message : String(err));
}

function cleanPeople(raw: unknown): Person[] {
  if (!Array.isArray(raw)) return [];
  return dedupePeople(
    raw
      .map((p: unknown) => {
        const o = (p ?? {}) as { name?: unknown; email?: unknown };
        return personFrom(o.name, o.email);
      })
      .filter((p): p is Person => p !== null),
  );
}

/** The agenda is built in the content script from the confirm table the host
 *  edited; re-check the shape before it goes anywhere. */
function cleanAgenda(raw: ContractAgenda): ContractAgenda | null {
  if (typeof raw !== "object" || raw === null) return null;
  const attendees = (Array.isArray(raw.attendees) ? raw.attendees : [])
    .map((a) => ({
      discordId: cleanText(a.discordId, 254),
      name: cleanText(a.name, 120),
      role: a.role === "host" ? ("host" as const) : ("attendee" as const),
    }))
    .filter((a) => a.discordId);
  const ids = new Set(attendees.map((a) => a.discordId));
  const topics = (Array.isArray(raw.topics) ? raw.topics : [])
    .map((t, i) => ({
      id: `t${i + 1}`,
      title: cleanText(t.title, 300).trim(),
      goal: cleanText(t.goal, 1000),
      budgetSeconds: Number.isInteger(t.budgetSeconds) && t.budgetSeconds >= 0 ? t.budgetSeconds : 0,
      owner: typeof t.owner === "string" && ids.has(t.owner) ? t.owner : null,
      mustHear: (Array.isArray(t.mustHear) ? t.mustHear : []).filter((id): id is string => typeof id === "string" && ids.has(id)),
      questions: (Array.isArray(t.questions) ? t.questions : []).map((q) => cleanText(q, 500)).filter(Boolean),
      type: t.type === "presentation" ? ("presentation" as const) : ("discussion" as const),
    }))
    .filter((t) => t.title);
  const agenda: ContractAgenda = {
    sessionId: /^[a-f0-9]{12}$/.test(raw.sessionId) ? raw.sessionId : "",
    purpose: cleanText(raw.purpose, 1000),
    totalSeconds: Number.isInteger(raw.totalSeconds) && raw.totalSeconds > 0 ? raw.totalSeconds : 0,
    attendees,
    topics,
  };
  if (raw.policy && typeof raw.policy === "object") agenda.policy = raw.policy;
  return agenda.sessionId && isRegistrable(agenda) ? agenda : null;
}

async function handle(req: Request): Promise<Response> {
  const settings = await loadSettings();
  const api = createApi(settings.serverUrl);
  const gcal = createCalendar(__DEV_BUILD__ && settings.mockAuth ? `${settings.serverUrl}/mock/gcal/calendar/v3` : GOOGLE_CALENDAR_BASE);

  switch (req.type) {
    case "whoami":
      return { ok: true, type: "whoami", user: await currentUser() };

    case "sign-out":
      await signOut();
      return { ok: true, type: "sign-out" };

    case "config": {
      const config = await withSession((t) => api.config(t), true);
      const botEmail = cleanEmail(config.botEmail);
      if (!botEmail) return fail("server-refused", "The server did not name a bot account.");
      return { ok: true, type: "config", config: { botEmail } };
    }

    case "lookup": {
      const eventId = cleanEventId(req.eventId);
      const meetCode = cleanMeetCode(req.meetCode);
      if (!eventId && !meetCode) return { ok: true, type: "lookup", event: null };
      // Interactive: this is the first thing the panel asks for, so it is where
      // the consent screen appears on a fresh profile.
      const token = await googleToken(true);
      const event = eventId ? await gcal.get(token, eventId) : await gcal.findByMeetCode(token, meetCode!);
      if (!event) return { ok: true, type: "lookup", event: null };
      const startMs = event.start ? Date.parse(event.start) : NaN;
      const endMs = event.end ? Date.parse(event.end) : NaN;
      const durationMinutes = Number.isFinite(startMs) && Number.isFinite(endMs) && endMs > startMs ? Math.round((endMs - startMs) / 60_000) : null;
      return {
        ok: true,
        type: "lookup",
        event: { eventId: event.id, title: event.title, description: event.description, attendees: event.attendees, start: event.start, durationMinutes },
      };
    }

    case "draft": {
      const brief = cleanText(req.brief);
      if (!brief.trim()) return fail("bad-request", "Empty brief.");
      const body = {
        brief,
        attendees: cleanPeople(req.attendees),
        now: new Date().toISOString(),
        timezone: cleanText(req.timezone, 64) || "UTC",
      };
      const { parsed } = await withSession((t) => api.draft(t, body), true);
      return { ok: true, type: "draft", parsed };
    }

    case "register": {
      const agenda = cleanAgenda(req.agenda);
      if (!agenda) return fail("bad-request", "That agenda has no topics — the gate should have caught this.");
      const eventId = cleanEventId(req.context?.eventId);
      const meetCode = cleanMeetCode(req.context?.meetCode);
      const attendees = cleanPeople(req.state?.attendees);
      const enforcement = req.state?.enforcement === "low" || req.state?.enforcement === "high" ? req.state.enforcement : "medium";

      // 1. Register with our server first; it mints the join URL we write into
      //    the description. A server refusal (422 on an empty agenda, say) stops
      //    everything before the real event is touched.
      const config = await withSession((t) => api.config(t), true);
      const botEmail = cleanEmail(config.botEmail);
      if (!botEmail) return fail("server-refused", "The server did not name a bot account.");

      const start = typeof req.state?.start === "string" ? req.state.start : null;
      const end = start && agenda.totalSeconds ? new Date(Date.parse(start) + agenda.totalSeconds * 1000).toISOString() : null;
      const body: RegisterRequest = {
        meeting: { provider: "google", eventId, meetCode, title: cleanText(req.state?.title, 300), start, end: Number.isNaN(Date.parse(end ?? "")) ? null : end },
        agenda,
        attendees,
        enforcement,
      };
      const result = await withSession((t) => api.register(t, body), true);
      const joinUrl = typeof result.joinUrl === "string" ? result.joinUrl : "";

      // 2. Then the real event. Only possible when it already exists (has an
      //    id, or a Meet code we can resolve); a brand-new, unsaved event gets
      //    the text handed back for the content script to put in the editor.
      const description = writeAgenda(cleanText(req.context?.description, 20_000), agenda, joinUrl);
      const wrote: WriteReport = { description: false, botInvited: false };
      const token = await googleToken(true);
      const event = eventId ? await gcal.get(token, eventId) : meetCode ? await gcal.findByMeetCode(token, meetCode) : null;
      if (event) {
        const merged = writeAgenda(event.description, agenda, joinUrl);
        const r = await gcal.writeAgenda(token, event, merged, botEmail);
        wrote.description = true;
        wrote.botInvited = r.botInvited;
      }
      return { ok: true, type: "register", result: { sessionId: result.sessionId, joinUrl }, description, botEmail, wrote };
    }
  }
}

chrome.runtime.onMessage.addListener((message: unknown, sender, sendResponse: (r: Response) => void) => {
  if (!fromOurContentScript(sender) || !isRequest(message)) {
    sendResponse(fail("bad-request", "Unexpected message."));
    return false;
  }
  handle(message)
    .catch(classify)
    .then(sendResponse);
  return true;
});

// The toolbar icon has no popup; it opens the options page.
chrome.action.onClicked.addListener(() => {
  void chrome.runtime.openOptionsPage();
});
