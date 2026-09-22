// A stand-in for the server half, so the extension can be loaded, clicked and
// reviewed with no Google account and no model. Node only, no dependencies.
//
//   node mock/server.mjs            → http://localhost:8790
//
// What it fakes, and how (see README "What is mocked"):
//   POST /ext/v1/session        any bearer → a session; user is host@example.com
//   GET  /ext/v1/config         { botEmail: "gavel-bot@example.com" }
//   POST /ext/v1/agenda/draft   a *rule-based* "model": topics are lines shaped
//                               like "Pricing — Artem, 10 min" or sentences that
//                               decide/agree/pick something. A brief with none
//                               of those returns topics: [] — which is how the
//                               refusal gate is exercised end to end.
//                               Header X-Mock-Draft: empty | null | error forces
//                               those outcomes regardless of the brief.
//   POST /ext/v1/agendas        422 on an empty agenda (the server-side gate),
//                               else stores it in memory and mints a join URL.
//   GET  /mock/agendas          what has been registered, for the reviewer.
//   /mock/gcal/calendar/v3/…    the three Calendar API calls the worker makes
//                               (get, list, patch) against two seeded events.
//   /fixtures/…                 static pages shaped like the Calendar editor and
//                               the Meet pre-join screen; the dev build's
//                               content scripts run on them.
//
// No credential is read or checked anywhere in this file. That is the point.

import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { randomUUID } from "node:crypto";

const here = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.GAVEL_MOCK_PORT ?? 8790);
const BOT_EMAIL = "gavel-bot@example.com";
const USER = { email: "host@example.com", name: "Vitaly" };

// --- state ---------------------------------------------------------------------

const sessions = new Set();
const agendas = [];
const EVENT_ID = "abc123def456ghi";
const MEET_CODE = "abc-defg-hij";
const start = new Date(Date.now() + 3 * 3600_000);
start.setMinutes(0, 0, 0);
const events = new Map([
  [
    EVENT_ID,
    {
      id: EVENT_ID,
      summary: "Launch go / no-go",
      description: "Thursday sync before the launch. Ana has the pricing numbers; Artem owns the rollout plan.",
      start: { dateTime: start.toISOString() },
      end: { dateTime: new Date(start.getTime() + 30 * 60_000).toISOString() },
      attendees: [
        { email: USER.email, displayName: USER.name, organizer: true, self: true, responseStatus: "accepted" },
        { email: "ana@example.com", displayName: "Ana Ruiz", responseStatus: "accepted" },
        { email: "artem@example.com", displayName: "Artem Ivanov", responseStatus: "needsAction" },
      ],
      conferenceData: { conferenceId: MEET_CODE },
      hangoutLink: `https://meet.google.com/${MEET_CODE}`,
    },
  ],
]);

// --- the rule-based "model" ---------------------------------------------------

const TOPIC_LINE = /^[\s\-*\u2022]*(.+?)\s*[\u2014\u2013-]\s*([A-Za-z][\w'\-. ]*?)(?:,|\s)\s*(\d{1,3})\s*min(?:ute)?s?\b\.?\s*$/i;
const DECIDES = /\b(decide|agree|pick|choose|approve|sign off|go\s*\/\s*no-go|settle)\b/i;

function draftFrom(brief, attendees) {
  const topics = [];
  for (const raw of brief.split("\n")) {
    const line = raw.trim();
    if (!line || /^agenda:?$/i.test(line)) continue;
    const m = TOPIC_LINE.exec(line);
    if (m) {
      const owner = /^(me|myself|i)$/i.test(m[2].trim()) ? (attendees[0]?.name ?? null) : m[2].trim();
      topics.push({ title: m[1].trim(), minutes: Number(m[3]), owner, mustHear: owner ? [owner] : [], type: "discussion" });
      continue;
    }
    for (const sentence of line.split(/(?<=[.;!?])\s+/)) {
      if (DECIDES.test(sentence) && sentence.length < 160) {
        topics.push({ title: sentence.replace(/[.;!?]+$/, "").trim(), minutes: null, owner: null, mustHear: [], type: "discussion" });
      }
    }
  }
  const explicit = brief.match(/\b(\d{1,3})[\s-]*(?:min|minute)s?\b(?:\s+(?:call|meeting|sync))/i);
  const budgeted = topics.reduce((n, t) => n + (t.minutes ?? 0), 0);
  const title = brief.split("\n").find((l) => l.trim())?.replace(/[.;!?]+$/, "").trim().slice(0, 80) ?? "Meeting";
  const decision = topics.find((t) => DECIDES.test(t.title));
  return {
    title,
    purpose: decision ? decision.title : topics.length ? `Decide: ${topics[0].title}` : "",
    start: start.toISOString(),
    durationMinutes: explicit ? Number(explicit[1]) : Math.max(30, Math.ceil(budgeted / 15) * 15),
    topics,
  };
}

// --- plumbing -------------------------------------------------------------------

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, PATCH, OPTIONS",
  "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Mock-Draft",
  "Access-Control-Max-Age": "600",
};

function send(res, status, body, headers = {}) {
  const text = typeof body === "string" ? body : JSON.stringify(body, null, 2);
  res.writeHead(status, { "Content-Type": typeof body === "string" ? "text/html; charset=utf-8" : "application/json", ...CORS, ...headers });
  res.end(text);
}

async function readJson(req) {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  const text = Buffer.concat(chunks).toString("utf8");
  return text ? JSON.parse(text) : {};
}

function bearer(req) {
  const m = /^Bearer\s+(\S+)$/.exec(req.headers.authorization ?? "");
  return m ? m[1] : null;
}

function requireSession(req, res) {
  const token = bearer(req);
  if (!token || !sessions.has(token)) {
    send(res, 401, { error: "no session" });
    return false;
  }
  return true;
}

async function serveFixture(res, name) {
  try {
    const html = await readFile(path.join(here, "fixtures", name), "utf8");
    send(res, 200, html);
  } catch {
    send(res, 404, { error: "no such fixture" });
  }
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const { pathname } = url;
  if (req.method === "OPTIONS") return send(res, 204, "");

  try {
    // ---- our server -----------------------------------------------------------
    if (req.method === "POST" && pathname === "/ext/v1/session") {
      const body = await readJson(req);
      if (body.provider !== "google" || typeof body.accessToken !== "string" || !body.accessToken) {
        return send(res, 400, { error: "provider and accessToken required" });
      }
      const sessionToken = `mock-session-${randomUUID()}`;
      sessions.add(sessionToken);
      return send(res, 200, { sessionToken, expiresAt: new Date(Date.now() + 8 * 3600_000).toISOString(), user: USER });
    }
    if (pathname.startsWith("/ext/v1/") && !requireSession(req, res)) return;

    if (req.method === "GET" && pathname === "/ext/v1/config") return send(res, 200, { botEmail: BOT_EMAIL });

    if (req.method === "POST" && pathname === "/ext/v1/agenda/draft") {
      const body = await readJson(req);
      if (typeof body.brief !== "string" || !body.brief.trim()) return send(res, 400, { error: "brief required" });
      const mode = req.headers["x-mock-draft"];
      if (mode === "error") return send(res, 502, { error: "model unavailable (forced by X-Mock-Draft)" });
      if (mode === "null") return send(res, 200, { parsed: null });
      const parsed = draftFrom(body.brief, Array.isArray(body.attendees) ? body.attendees : []);
      if (mode === "empty") parsed.topics = [];
      console.log(`draft: ${parsed.topics.length} topic(s) from ${body.brief.length} chars`);
      return send(res, 200, { parsed });
    }

    if (req.method === "POST" && pathname === "/ext/v1/agendas") {
      const body = await readJson(req);
      const agenda = body.agenda;
      if (!agenda || !Array.isArray(agenda.topics) || agenda.topics.length === 0) {
        return send(res, 422, { error: "agenda has no topics" });
      }
      if (!Array.isArray(agenda.attendees) || !agenda.attendees.some((a) => a.role === "host")) {
        return send(res, 422, { error: "agenda has no host" });
      }
      const sessionId = typeof agenda.sessionId === "string" && agenda.sessionId ? agenda.sessionId : randomUUID().replace(/-/g, "").slice(0, 12);
      const record = { sessionId, receivedAt: new Date().toISOString(), meeting: body.meeting, enforcement: body.enforcement, agenda: { ...agenda, sessionId } };
      agendas.push(record);
      console.log(`registered ${sessionId}: ${agenda.topics.length} topic(s), event ${body.meeting?.eventId ?? "-"}, meet ${body.meeting?.meetCode ?? "-"}`);
      return send(res, 201, { sessionId, joinUrl: `http://localhost:${PORT}/join/${sessionId}` });
    }

    if (req.method === "GET" && pathname === "/mock/agendas") return send(res, 200, agendas);
    if (req.method === "GET" && pathname.startsWith("/join/")) {
      return send(res, 200, `<!doctype html><meta charset="utf-8"><title>gavel</title><p>Join link for session <code>${pathname.slice(6).replace(/[^a-f0-9]/g, "")}</code>. In production this is where the chair joins.</p>`);
    }

    // ---- Google Calendar API stand-in ----------------------------------------------
    const gcal = pathname.match(/^\/mock\/gcal\/calendar\/v3\/calendars\/primary\/events(?:\/([^/]+))?$/);
    if (gcal) {
      if (!bearer(req)) return send(res, 401, { error: { message: "Login Required" } });
      const id = gcal[1] ? decodeURIComponent(gcal[1]) : null;
      if (req.method === "GET" && id === null) return send(res, 200, { items: Array.from(events.values()) });
      if (id === null) return send(res, 405, { error: { message: "method" } });
      const event = events.get(id);
      if (!event) return send(res, 404, { error: { message: "Not Found" } });
      if (req.method === "GET") return send(res, 200, event);
      if (req.method === "PATCH") {
        const patch = await readJson(req);
        if (typeof patch.description === "string") event.description = patch.description;
        if (Array.isArray(patch.attendees)) event.attendees = patch.attendees;
        console.log(`gcal: patched ${id} (sendUpdates=${url.searchParams.get("sendUpdates") ?? "-"}), ${event.attendees.length} attendee(s)`);
        return send(res, 200, event);
      }
    }

    // ---- fixtures ------------------------------------------------------------------
    if (pathname === "/" || pathname === "/fixtures" || pathname === "/fixtures/") return serveFixture(res, "index.html");
    if (pathname === "/fixtures/calendar.html" || /^\/fixtures\/eventedit(\/|$)/.test(pathname)) return serveFixture(res, "calendar.html");
    if (pathname === "/fixtures/meet.html" || /^\/fixtures\/meet\//.test(pathname)) return serveFixture(res, "meet.html");
    if (pathname === "/fixtures/fixtures.js" || pathname === "/fixtures/fixtures.css") {
      const asset = await readFile(path.join(here, "fixtures", path.basename(pathname)), "utf8");
      res.writeHead(200, { "Content-Type": pathname.endsWith(".js") ? "text/javascript; charset=utf-8" : "text/css; charset=utf-8", ...CORS });
      return res.end(asset);
    }
    if (pathname === "/fixtures/event.json") {
      return send(res, 200, { eventId: EVENT_ID, meetCode: MEET_CODE, event: events.get(EVENT_ID), editUrl: `/fixtures/eventedit/${Buffer.from(`${EVENT_ID} ${USER.email}`).toString("base64url")}` });
    }

    send(res, 404, { error: `no route for ${req.method} ${pathname}` });
  } catch (err) {
    console.error(err);
    send(res, 500, { error: err instanceof Error ? err.message : String(err) });
  }
});

server.listen(PORT, () => {
  const edit = Buffer.from(`${EVENT_ID} ${USER.email}`).toString("base64url");
  console.log(`gavel mock on http://localhost:${PORT}`);
  console.log(`  calendar editor, new event:      http://localhost:${PORT}/fixtures/calendar.html`);
  console.log(`  calendar editor, existing event: http://localhost:${PORT}/fixtures/eventedit/${edit}`);
  console.log(`  meet pre-join:                   http://localhost:${PORT}/fixtures/meet/${MEET_CODE}`);
  console.log(`  registered agendas:              http://localhost:${PORT}/mock/agendas`);
});
