/** Who the chair invites to talk. Pure. */
import type { PersonView, Snapshot } from "./snapshot";

export interface Pick {
  person: PersonView;
  reason: "mustHear" | "owner" | "leastOnTopic";
  /** Everyone present has already spoken on this topic. */
  everyoneHeard: boolean;
}

export function pickSpeaker(s: Snapshot, exclude: string[] = []): Pick | null {
  let pool = s.people.filter((p) => !exclude.includes(p.id));
  const avoid = [
    s.pick.avoidLastSpeaker ? s.lastSpeakerId : null,
    s.pick.avoidLastPrompted ? s.lastPromptedId : null,
  ].filter((x): x is string => !!x);
  const narrowed = pool.filter((p) => !avoid.includes(p.id));
  if (narrowed.length) pool = narrowed;
  if (!pool.length) return null;

  const unheard = (p: PersonView) => p.topicMs === 0;
  const everyoneHeard = s.people.every((p) => !unheard(p));
  for (const rule of s.pick.order) {
    if (rule === "mustHear") {
      const must = s.topic?.mustHear ?? [];
      const hit = pool.find((p) => must.includes(p.id) && unheard(p));
      if (hit) return { person: hit, reason: "mustHear", everyoneHeard };
    } else if (rule === "owner") {
      const hit = pool.find((p) => p.id === s.topic?.owner && unheard(p));
      if (hit) return { person: hit, reason: "owner", everyoneHeard };
    } else {
      const sorted = [...pool].sort((a, b) => a.topicMs - b.topicMs || a.totalMs - b.totalMs);
      if (sorted[0]) return { person: sorted[0], reason: "leastOnTopic", everyoneHeard };
    }
  }
  return null;
}

/** For a round: least heard on this topic first. */
export function roundOrder(s: Snapshot, max = 3): PersonView[] {
  return [...s.people].sort((a, b) => a.topicMs - b.topicMs || a.totalMs - b.totalMs).slice(0, max);
}
