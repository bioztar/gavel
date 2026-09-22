// The one seam between a content script (untrusted page context) and the
// service worker (holds the session token). Every request crosses here through
// `chrome.runtime.sendMessage`; the worker validates the shape before acting and
// only ever answers with data — never a token.

import type {
  ConfirmState,
  ContractAgenda,
  Draft,
  EventContext,
  Person,
  RegisterResponse,
  ServerConfig,
} from "./types.js";

export type Request =
  | { type: "whoami" }
  | { type: "config" }
  | { type: "lookup"; eventId: string | null; meetCode: string | null }
  | { type: "draft"; brief: string; attendees: Person[]; timezone: string }
  | { type: "register"; context: EventContext; state: ConfirmState; agenda: ContractAgenda }
  | { type: "sign-out" };

export type Response =
  | { ok: true; type: "whoami"; user: { email: string; name?: string } | null }
  | { ok: true; type: "config"; config: ServerConfig }
  | { ok: true; type: "lookup"; event: LookedUpEvent | null }
  | { ok: true; type: "draft"; parsed: Draft | null }
  | { ok: true; type: "register"; result: RegisterResponse; description: string; botEmail: string; wrote: WriteReport }
  | { ok: true; type: "sign-out" }
  | { ok: false; error: ErrorKind; detail: string };

export type ErrorKind =
  | "not-signed-in"
  | "auth-cancelled"
  | "server-unreachable"
  | "server-refused"
  | "calendar-write-failed"
  | "bad-request";

/** The saved event behind an editor or a Meet code, read through the Calendar
 *  API so the brief has the guests and description even where the page shows
 *  none (the Meet pre-join screen). */
export interface LookedUpEvent {
  eventId: string;
  title: string;
  description: string;
  attendees: Person[];
  start: string | null;
  durationMinutes: number | null;
}

/** Which of the two writes to the real event happened. In the Meet surface
 *  (and any editor without a saved id) the description is handed back for the
 *  content script to paste, so `description` may be `false` without an error. */
export interface WriteReport {
  description: boolean;
  botInvited: boolean;
}

export function isRequest(value: unknown): value is Request {
  if (typeof value !== "object" || value === null) return false;
  const t = (value as { type?: unknown }).type;
  return t === "whoami" || t === "config" || t === "lookup" || t === "draft" || t === "register" || t === "sign-out";
}

export function send(request: Request): Promise<Response> {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(request, (reply: Response | undefined) => {
      if (chrome.runtime.lastError || reply === undefined) {
        resolve({
          ok: false,
          error: "server-unreachable",
          detail: chrome.runtime.lastError?.message ?? "The extension did not answer.",
        });
        return;
      }
      resolve(reply);
    });
  });
}
