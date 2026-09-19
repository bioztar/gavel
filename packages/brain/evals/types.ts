/**
 * The shape of one eval case: a frozen chair state plus the trigger that fired, and what
 * a good line has to do with it. Every field is validated against the brain's own types —
 * `people` is a real `PersonView`, `episodes` hold real `Episode`s, `agenda` is the real
 * `Agenda` — so a fixture that drifts from the code stops typechecking, not just failing.
 */
import { z } from "zod";
import { INTERVENTION_KINDS, TRIGGERS } from "../src/config";
import { Agenda } from "../src/contract/agenda";
import type { Episode } from "../src/state/relevance";
import type { PersonView, Redirect } from "../src/policy/snapshot";

/** `B` must be assignable to `A`: how the zod shapes below are pinned to the real types. */
type Assert<A, B extends A> = B;

const PersonState = z.object({
  id: z.string(),
  name: z.string(),
  role: z.string().default("attendee"),
  totalMs: z.number().nonnegative(),
  topicMs: z.number().nonnegative(),
  windowMs: z.number().nonnegative(),
  holding: z.boolean(),
  holdingSince: z.number().nullable(),
});
export type _PersonIsPersonView = Assert<PersonView, z.infer<typeof PersonState>>;

const EpisodeState = z.object({
  offSince: z.number(),
  verdict: z.enum(["otherTopic", "offAgenda"]),
  topicId: z.string().nullable(),
  summary: z.string(),
  quote: z.string(),
});
export type _EpisodeIsEpisode = Assert<Episode, z.infer<typeof EpisodeState>>;

const RedirectState = z.object({
  targetId: z.string(),
  topicId: z.string().nullable(),
  spokenAt: z.number().nullable(),
});
export type _RedirectIsRedirect = Assert<Redirect, z.infer<typeof RedirectState>>;

const Note = z.object({ name: z.string(), summary: z.string() });

/** The frozen instant. Everything the policy reads that is not already in the agenda. */
export const CaseState = z.object({
  /** The clock at the moment the trigger fired; every other time in the case is relative to it. */
  nowMs: z.number(),
  topicIndex: z.number().int().nonnegative(),
  topicStartedAtMs: z.number(),
  people: z.array(PersonState),
  silenceMs: z.number().nonnegative().default(0),
  episodes: z.array(z.object({ id: z.string(), episode: EpisodeState })).default([]),
  redirect: RedirectState.nullable().default(null),
  escalatedAt: z.record(z.string(), z.number()).default({}),
  lastInterventionAtMs: z.number().nullable().default(null),
  lastSpeakerId: z.string().nullable().default(null),
  lastPromptedId: z.string().nullable().default(null),
  asked: z.record(z.string(), z.array(z.string())).default({}),
  recaps: z.record(z.string(), z.string()).default({}),
  parked: z.array(Note).default([]),
  carried: z.array(Note).default([]),
});
export type CaseState = z.infer<typeof CaseState>;

/**
 * Who the line has to name. `person`: that first name must be in the line. `nobody`: a
 * shared tangent or a topic move, where the chair addresses the room and singling anyone
 * out is the failure.
 */
export const NameTarget = z.discriminatedUnion("kind", [
  z.object({ kind: z.literal("person"), name: z.string() }),
  z.object({ kind: z.literal("nobody") }),
]);
export type NameTarget = z.infer<typeof NameTarget>;

/** Where the floor has to go: to a named person, or to a named agenda item. */
export const FloorTarget = z.discriminatedUnion("kind", [
  z.object({ kind: z.literal("person"), name: z.string() }),
  z.object({ kind: z.literal("topic"), title: z.string() }),
]);
export type FloorTarget = z.infer<typeof FloorTarget>;

export const EvalCase = z.object({
  id: z.string(),
  title: z.string(),
  /** Why this case is in the set, and what it is trying to catch. Lands in results.md. */
  notes: z.string(),
  agenda: Agenda,
  sessionTitle: z.string().nullable().default(null),
  state: CaseState,
  expect: z.object({
    trigger: z.enum(TRIGGERS),
    kind: z.enum(INTERVENTION_KINDS),
    names: NameTarget,
    floorTo: FloorTarget,
    maxWords: z.number().int().positive().default(20),
  }),
});
export type EvalCase = z.infer<typeof EvalCase>;
