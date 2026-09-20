/** The agenda — docs/CONTRACT.md §1. Lenient on input, like ears' console is. */
import { readFileSync } from "node:fs";
import { z } from "zod";
import type { Policy } from "../config";

export const Attendee = z.object({
  discordId: z.string(),
  name: z.string(),
  role: z.string().default("attendee"),
});
export type Attendee = z.infer<typeof Attendee>;

export const Topic = z.object({
  id: z.string(),
  title: z.string(),
  goal: z.string().default(""),
  budgetSeconds: z.number().nonnegative(),
  owner: z.string().nullish(),
  mustHear: z.array(z.string()).default([]),
  questions: z.array(z.string()).default([]),
  // discussion: the room talks it through, and the chair hands the floor on from anyone hogging
  // it (also when absent). presentation: one person has the floor by design, so no handovers.
  type: z.enum(["discussion", "presentation"]).optional().catch(undefined),
});
export type Topic = z.infer<typeof Topic>;

export const Agenda = z.object({
  sessionId: z.string().nullish(),
  purpose: z.string().default(""),
  totalSeconds: z.number().default(0),
  attendees: z.array(Attendee).default([]),
  topics: z.array(Topic).default([]),
  // Partial: anything absent falls back to config/policy.yaml defaults.
  policy: z.record(z.string(), z.unknown()).default({}),
});
export type Agenda = z.infer<typeof Agenda>;

export function loadAgendaFile(path: string): Agenda {
  return Agenda.parse(JSON.parse(readFileSync(path, "utf8")));
}

/** YAML defaults, overridden key by key by the agenda's own policy block. */
export function mergePolicy(defaults: Policy, agenda: Agenda | null): Policy {
  const out: Policy = { ...defaults };
  const own = agenda?.policy ?? {};
  for (const [key, value] of Object.entries(own)) {
    if (!(key in defaults)) continue;
    const want = typeof defaults[key as keyof Policy];
    if (typeof value === want) (out as Record<string, unknown>)[key] = value;
  }
  // Agendas written before the two thresholds: one gate, and `handover` fixing the style
  // of every handover. "hard" then meant cutting in as soon as the gate was passed.
  if (typeof own.floorMinSpeakingSeconds === "number" && typeof own.softHandoverSeconds !== "number") {
    out.softHandoverSeconds = own.floorMinSpeakingSeconds;
  }
  if (own.handover === "hard" && typeof own.hardHandoverSeconds !== "number") {
    out.hardHandoverSeconds = out.softHandoverSeconds;
  }
  return out;
}
