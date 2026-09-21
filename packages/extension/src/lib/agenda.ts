// The confirm table → the contract agenda (docs/CONTRACT.md §1).
//
// A port of three pieces of `packages/calendar`, kept in the same order so a
// diff against the Python reads line for line:
//   compose.py:_fill_topic_minutes / _topic_drafts   → fillTopicMinutes / topicDrafts
//   agenda.py:build_agenda                           → buildAgenda
//   schema.py:EARS_DEFAULT_POLICY / ENFORCEMENT_LEVELS → the two tables below
//
// Pure: no DOM, no network, no chrome.*. `test/agenda.test.ts` pins it against
// the fixture values the Python tests use.

import { cleanMinutes } from "./sanitize.js";
import type {
  ConfirmState,
  ContractAgenda,
  ContractAttendee,
  ContractTopic,
  Enforcement,
  Person,
  Policy,
  TopicRow,
  TopicType,
} from "./types.js";

/** Mirrors `ears-discord`'s `DEFAULT_POLICY` via `schema.EARS_DEFAULT_POLICY`.
 *  The wire payload always carries every key: `ears`'s own `Agenda.policy` does
 *  not deep-merge, so a partial dict would silently drop the rest. */
export const EARS_DEFAULT_POLICY: Policy = {
  floorShareThreshold: 0.6,
  floorWindowSeconds: 120,
  softHandoverSeconds: 45,
  hardHandoverSeconds: 90,
  topicOverrunFactor: 1.2,
  silenceSeconds: 15,
  minSecondsBetweenInterventions: 45,
  offAgendaGraceSeconds: 20,
  allowMute: false,
  escalateAfterSeconds: 10,
  muteSeconds: 15,
  requireStart: false,
  timed: true,
};

/** The gauge on the confirm view — `schema.ENFORCEMENT_LEVELS`, verbatim. */
export const ENFORCEMENT_LEVELS: Record<Enforcement, Policy> = {
  low: {
    offAgendaGraceSeconds: 45,
    minSecondsBetweenInterventions: 90,
    topicOverrunFactor: 1.5,
    softHandoverSeconds: 90,
    hardHandoverSeconds: 0,
    silenceSeconds: 25,
    escalateAfterSeconds: 20,
    allowMute: false,
  },
  medium: {
    offAgendaGraceSeconds: 8,
    minSecondsBetweenInterventions: 45,
    topicOverrunFactor: 1.2,
    softHandoverSeconds: 45,
    hardHandoverSeconds: 90,
    silenceSeconds: 15,
    escalateAfterSeconds: 10,
    allowMute: false,
  },
  high: {
    offAgendaGraceSeconds: 5,
    minSecondsBetweenInterventions: 25,
    topicOverrunFactor: 1.05,
    softHandoverSeconds: 30,
    hardHandoverSeconds: 30,
    silenceSeconds: 10,
    escalateAfterSeconds: 6,
    allowMute: true,
    muteSeconds: 15,
  },
};

export const DEFAULT_ENFORCEMENT: Enforcement = "medium";

export function policyFor(level: Enforcement): Policy {
  return { ...EARS_DEFAULT_POLICY, ...(ENFORCEMENT_LEVELS[level] ?? ENFORCEMENT_LEVELS[DEFAULT_ENFORCEMENT]) };
}

/** `compose.py:_fill_topic_minutes`. Named durations are kept; the rest of the
 *  meeting splits evenly, in whole minutes, across the rows that did not say,
 *  and the last of those absorbs the remainder. Whole minutes matter: the
 *  description round-trips through `ics_parser`, which reads minutes only. */
export function fillTopicMinutes(minutes: (number | null)[], totalMinutes: number): number[] {
  const known = minutes.filter((m): m is number => m !== null);
  const remaining = Math.max(totalMinutes - known.reduce((a, b) => a + b, 0), 0);
  const unknownCount = minutes.length - known.length;
  if (unknownCount === 0) return known;
  const share = Math.floor(remaining / unknownCount);
  const extra = remaining - share * unknownCount;
  let given = 0;
  return minutes.map((m) => {
    if (m !== null) return m;
    given += 1;
    return share + (given === unknownCount ? extra : 0);
  });
}

export interface TopicDraft {
  title: string;
  budgetSeconds: number;
  ownerName: string | null;
  mustHearNames: string[];
  type: TopicType;
}

/** `compose.py:_topic_drafts` — blank-title rows are dropped, everything else
 *  gets an explicit whole-minute budget before it reaches `buildAgenda`. */
export function topicDrafts(rows: TopicRow[], totalMinutes: number): TopicDraft[] {
  const named = rows.filter((r) => r.title.trim());
  const minutes = named.map((r) => cleanMinutes(r.minutes));
  const filled = fillTopicMinutes(minutes, totalMinutes);
  return named.map((r, i) => ({
    title: r.title.trim(),
    budgetSeconds: filled[i]! * 60,
    ownerName: r.owner.trim() || null,
    mustHearNames: r.mustHear
      .split(",")
      .map((n) => n.trim())
      .filter(Boolean),
    type: r.type === "presentation" ? "presentation" : "discussion",
  }));
}

/** Twelve hex characters, like `uuid.uuid4().hex[:12]` in `compose.handle_send`. */
export function newSessionId(random: () => string = () => crypto.randomUUID()): string {
  return random().replace(/-/g, "").slice(0, 12);
}

export interface BuildInput {
  state: ConfirmState;
  /** The signed-in user — `role: "host"`. Added to the attendees if the editor
   *  did not list them (Google shows the organiser as a chip only sometimes). */
  host: Person;
  sessionId: string;
}

/** `agenda.py:build_agenda`, for one meeting. `discordId` is the e-mail — the
 *  same stable fallback the Python uses until `CALENDAR_ATTENDEE_MAP` maps it. */
export function buildAgenda({ state, host, sessionId }: BuildInput): ContractAgenda {
  const people: Person[] = state.attendees.some((a) => a.email === host.email)
    ? state.attendees
    : [host, ...state.attendees];

  const attendees: ContractAttendee[] = people.map((p) => ({
    discordId: p.email,
    name: p.name,
    role: p.email === host.email ? "host" : "attendee",
  }));

  const byName = new Map<string, string>();
  for (const a of attendees) byName.set(a.name.trim().toLowerCase(), a.discordId);
  const byEmail = new Map(attendees.map((a) => [a.discordId, a.discordId] as const));
  const resolve = (name: string): string | undefined => {
    const key = name.trim().toLowerCase();
    return byName.get(key) ?? byEmail.get(key) ?? uniqueFirstName(attendees, key);
  };

  const hostId = attendees.find((a) => a.role === "host")?.discordId ?? attendees[0]?.discordId ?? null;

  const totalSeconds = state.durationMinutes * 60;
  const topics: ContractTopic[] = topicDrafts(state.rows, state.durationMinutes).map((draft, i) => {
    const ownerId = (draft.ownerName ? resolve(draft.ownerName) : undefined) ?? hostId;
    // Unmatched names are dropped, not passed through — the brain resolves
    // mustHear against ids, not free text.
    let mustHear = draft.mustHearNames.map(resolve).filter((id): id is string => id !== undefined);
    if (mustHear.length === 0 && ownerId !== null) mustHear = [ownerId];
    return {
      id: `t${i + 1}`,
      title: draft.title,
      goal: "",
      budgetSeconds: draft.budgetSeconds,
      owner: ownerId,
      mustHear,
      questions: [],
      type: draft.type,
    };
  });

  // The host's own one-liner wins; the title stands in when there is none,
  // as `agenda._purpose` falls back to `invite.title`.
  const purpose = state.purpose.trim() || state.title.trim();
  return {
    sessionId,
    purpose,
    totalSeconds,
    attendees,
    topics,
    policy: policyFor(state.enforcement),
  };
}

/** The Python's `by_name` is exact. Chip labels off Google are full names while
 *  the model writes what the brief said ("Artem"), so a first name is accepted
 *  when it names exactly one person on the invite. */
function uniqueFirstName(attendees: ContractAttendee[], key: string): string | undefined {
  if (!key || key.includes(" ")) return undefined;
  const hits = attendees.filter((a) => a.name.trim().toLowerCase().split(/\s+/)[0] === key);
  return hits.length === 1 ? hits[0]!.discordId : undefined;
}

/** What `POST /ext/v1/agendas` refuses with a 422, checked here first so the
 *  panel never gets as far as the network with an empty agenda. */
export function isRegistrable(agenda: ContractAgenda): boolean {
  return agenda.topics.length > 0 && agenda.totalSeconds > 0 && agenda.attendees.length > 0;
}
