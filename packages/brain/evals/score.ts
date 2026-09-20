/**
 * The rubric from docs/QUALITY.md, five dimensions over one generated line.
 *
 * Three are arithmetic and are computed here, never asked of a model: the word count, the
 * right person's name being in the line, and the floor going somewhere named. Two are
 * judgement — polite enough to survive a real meeting, and inventing nothing it never
 * heard — and go to a `Judge`. With no judge, those two come back `null` (not run) rather
 * than quietly passing.
 */
import type { Intervention } from "../src/policy/snapshot";
import type { Judge, JudgeRequest } from "./judge";
import type { EvalCase, FloorTarget, NameTarget } from "./types";

export interface Score {
  /** null: this dimension was not evaluated (no judge configured). */
  pass: boolean | null;
  detail: string;
}

export interface Scores {
  namesRightPerson: Score;
  underWordLimit: Score;
  handsFloorSomewhere: Score;
  polite: Score;
  inventsNothing: Score;
}

export const DIMENSIONS: Array<{ key: keyof Scores; label: string; judged: boolean }> = [
  { key: "namesRightPerson", label: "names the right person", judged: false },
  { key: "underWordLimit", label: "under 20 words", judged: false },
  { key: "handsFloorSomewhere", label: "hands the floor somewhere specific", judged: false },
  { key: "polite", label: "polite enough for a real meeting", judged: true },
  { key: "inventsNothing", label: "invents nothing", judged: true },
];

export function words(line: string): string[] {
  return line.trim().split(/\s+/).filter(Boolean);
}

/** Spoken aloud, people are addressed by first name — the same rule the templates use. */
export function firstName(name: string): string {
  return name.trim().split(/\s+/)[0] ?? "";
}

export function mentions(line: string, name: string): boolean {
  const first = firstName(name);
  if (!first) return false;
  return new RegExp(`(^|[^\\p{L}])${escape(first)}([^\\p{L}]|$)`, "iu").test(line);
}

function escape(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Does it name the person this intervention is about — and only them? */
export function scoreNames(line: string, target: NameTarget, everyone: string[]): Score {
  if (target.kind === "person") {
    const hit = mentions(line, target.name);
    const wrong = everyone.filter((n) => firstName(n) !== firstName(target.name) && mentions(line, n));
    if (!hit) return { pass: false, detail: `does not name ${firstName(target.name)}` };
    if (wrong.length) return { pass: true, detail: `names ${firstName(target.name)}, also ${wrong.map(firstName).join(", ")}` };
    return { pass: true, detail: `names ${firstName(target.name)}` };
  }
  // A group redirect or a topic move: singling anyone out is the failure.
  const named = everyone.filter((n) => mentions(line, n));
  return named.length
    ? { pass: false, detail: `singles out ${named.map(firstName).join(", ")}` }
    : { pass: true, detail: "addresses the room, names nobody" };
}

export function scoreLength(line: string, maxWords: number): Score {
  const n = words(line).length;
  return { pass: n > 0 && n <= maxWords, detail: `${n} words` };
}

/** The floor has to land somewhere a listener could act on: a person, or a named agenda item. */
export function scoreFloor(line: string, target: FloorTarget): Score {
  if (target.kind === "person") {
    return mentions(line, target.name)
      ? { pass: true, detail: `hands over to ${firstName(target.name)}` }
      : { pass: false, detail: `no handover to ${firstName(target.name)}` };
  }
  const hit = line.toLowerCase().includes(target.title.toLowerCase());
  return hit
    ? { pass: true, detail: `returns the room to "${target.title}"` }
    : { pass: false, detail: `does not name "${target.title}"` };
}

const NOT_RUN: Score = { pass: null, detail: "not run (no judge)" };

/**
 * The facts the chair was given for this intervention, in the same order the prompt lists
 * them — this, and nothing else, is what the grounding judge holds the line to.
 */
export function factsOf(iv: Intervention): string {
  return Object.entries(iv.vars)
    .filter(([k]) => k !== "quote")
    .map(([k, v]) => `${k}: ${v?.trim() || "(none)"}`)
    .join("\n");
}

export async function scoreLine(
  c: EvalCase,
  iv: Intervention,
  line: string,
  judge?: Judge,
): Promise<Scores> {
  const everyone = c.agenda.attendees.map((a) => a.name);
  const deterministic = {
    namesRightPerson: scoreNames(line, c.expect.names, everyone),
    underWordLimit: scoreLength(line, c.expect.maxWords),
    handsFloorSomewhere: scoreFloor(line, c.expect.floorTo),
  };
  if (!judge || !line.trim()) {
    return { ...deterministic, polite: NOT_RUN, inventsNothing: NOT_RUN };
  }
  const ask = async (dimension: JudgeRequest["dimension"]): Promise<Score> => {
    const verdict = await judge.judge({ dimension, line, facts: factsOf(iv) });
    return { pass: verdict.pass, detail: verdict.reason };
  };
  let polite: Score;
  let inventsNothing: Score;
  try {
    [polite, inventsNothing] = await Promise.all([ask("polite"), ask("grounded")]);
  } catch (error) {
    throw new Error("evaluation judge failed", { cause: error });
  }
  return { ...deterministic, polite, inventsNothing };
}
