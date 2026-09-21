// Shapes shared between the content scripts, the service worker and the server.
// The server half is specified in the PR / README ("Server endpoints"); the
// contract agenda is docs/CONTRACT.md §1 and is copied here field for field.

/** One person on the invite, as read off the editor or the Calendar API. */
export interface Person {
  name: string;
  email: string;
}

/** What the content script read out of the page. All strings are untrusted
 *  until they have been through `sanitize.ts`. */
export interface EventContext {
  surface: "calendar" | "meet";
  /** Google Calendar event id when the event already exists, else null
   *  (a new, unsaved event in the editor). */
  eventId: string | null;
  /** Google Meet code (`abc-defg-hij`) when known, else null. */
  meetCode: string | null;
  title: string;
  description: string;
  attendees: Person[];
  /** ISO 8601 with offset, or null when the editor's date could not be read. */
  start: string | null;
  durationMinutes: number | null;
  timezone: string;
}

// --- server: POST /ext/v1/agenda/draft ---------------------------------------------

export type TopicType = "discussion" | "presentation";

/** The model's reading of the brief — `packages/calendar`'s `llm.ParsedBrief`,
 *  camel-cased on the wire. `topics: []` is the signal the gate refuses on. */
export interface DraftTopic {
  title: string;
  minutes: number | null;
  owner: string | null;
  mustHear: string[];
  type: TopicType;
}

export interface Draft {
  title: string;
  purpose: string;
  /** ISO 8601 with offset. */
  start: string;
  durationMinutes: number;
  topics: DraftTopic[];
}

export interface DraftRequest {
  brief: string;
  attendees: Person[];
  now: string;
  timezone: string;
}

/** `parsed: null` means the model call failed or returned something unusable.
 *  The gate treats it exactly like an empty topic list — same as `compose.py`. */
export interface DraftResponse {
  parsed: Draft | null;
}

// --- the confirm table --------------------------------------------------------------

/** One editable row of the confirm table — `compose.py:_Row`. */
export interface TopicRow {
  title: string;
  minutes: string;
  owner: string;
  mustHear: string;
  type: TopicType;
}

export type Enforcement = "low" | "medium" | "high";

export interface ConfirmState {
  title: string;
  purpose: string;
  start: string | null;
  durationMinutes: number;
  attendees: Person[];
  rows: TopicRow[];
  enforcement: Enforcement;
}

// --- docs/CONTRACT.md §1 -------------------------------------------------------------

export interface ContractAttendee {
  discordId: string;
  name: string;
  role: "host" | "attendee";
}

export interface ContractTopic {
  id: string;
  title: string;
  goal: string;
  budgetSeconds: number;
  owner: string | null;
  mustHear: string[];
  questions: string[];
  type: TopicType;
}

export type Policy = Record<string, number | boolean | string>;

export interface ContractAgenda {
  sessionId: string;
  purpose: string;
  totalSeconds: number;
  attendees: ContractAttendee[];
  topics: ContractTopic[];
  policy?: Policy;
}

// --- server: POST /ext/v1/agendas --------------------------------------------------

export interface RegisterRequest {
  meeting: {
    provider: "google";
    eventId: string | null;
    meetCode: string | null;
    title: string;
    start: string | null;
    end: string | null;
  };
  agenda: ContractAgenda;
  attendees: Person[];
  enforcement: Enforcement;
}

export interface RegisterResponse {
  sessionId: string;
  joinUrl: string;
}

// --- server: GET /ext/v1/config ----------------------------------------------------

export interface ServerConfig {
  /** The bot account that is added to the event — how the chair gets in. */
  botEmail: string;
}

// --- server: POST /ext/v1/session --------------------------------------------------

export interface SessionResponse {
  sessionToken: string;
  /** ISO 8601. */
  expiresAt: string;
  user: { email: string; name?: string };
}
