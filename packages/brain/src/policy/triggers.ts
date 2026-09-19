/**
 * Whether the chair speaks, and what it does. Pure and deterministic: the same snapshot
 * always gives the same answer, so it fires predictably in front of a room. The model is
 * never asked *whether* — only, later, *how to say it*.
 */
import type { Topic } from "../contract/agenda";
import { render } from "../template";
import { pickSpeaker, roundOrder } from "./pickSpeaker";
import type { Episode } from "../state/relevance";
import type { Intervention, PersonView, Snapshot } from "./snapshot";

const S = 1000;

export function evaluate(s: Snapshot): Intervention | null {
  // The chair never talks over itself.
  if (s.chairBusy) return null;
  for (const name of s.engine.triggerOrder) {
    // Escalation follows up a redirect already made, so it is exempt from the gap.
    if (name !== "escalate" && inCooldown(s)) continue;
    const hit = TRIGGERS[name](s);
    if (hit) return hit;
  }
  return null;
}

function inCooldown(s: Snapshot): boolean {
  return s.lastInterventionAt !== null && s.now - s.lastInterventionAt < s.policy.minSecondsBetweenInterventions * S;
}

const TRIGGERS: Record<Snapshot["engine"]["triggerOrder"][number], (s: Snapshot) => Intervention | null> = {
  escalate,
  offAgenda,
  floorHog,
  topicOverrun,
  silence,
};

// --- the triggers ----------------------------------------------------------------------

/** Redirected, and still talking `escalateAfterSeconds` after the chair finished. */
function escalate(s: Snapshot): Intervention | null {
  const r = s.redirect;
  if (!r || r.spokenAt === null || r.topicId !== topicId(s)) return null;
  const target = person(s, r.targetId);
  if (!target?.holding) return null;
  // Only talking that started (or carried on) after the redirect counts.
  if (s.now - r.spokenAt < s.policy.escalateAfterSeconds * S) return null;
  const last = s.escalatedAt[target.id];
  if (last !== undefined && s.now - last < s.engine.escalateCooldownSeconds * S) return null;

  const mayMute = s.policy.allowMute && !s.engine.neverMuteRoles.includes(target.role);
  const question = nextQuestion(s, s.topic);
  return {
    trigger: "escalate",
    kind: mayMute ? "escalateMute" : "escalateFirm",
    topicId: topicId(s),
    targetId: target.id,
    vars: { ...base(s, target), question, seconds: String(Math.round(s.policy.muteSeconds)) },
    actions: mayMute ? ["speak", "mute"] : ["speak"],
    priority: true,
    muteSeconds: mayMute ? s.policy.muteSeconds : undefined,
    question: mayMute ? undefined : question,
  };
}

/** Off the agenda for longer than the grace period, and still holding the floor. */
function offAgenda(s: Snapshot): Intervention | null {
  const grace = s.policy.offAgendaGraceSeconds * S;
  const due = s.episodes
    .map(({ id, episode }) => ({ p: person(s, id), episode }))
    .filter(({ p, episode }) => p?.holding && s.now - episode.offSince >= grace)
    .sort((a, b) => a.episode.offSince - b.episode.offSince)[0];
  if (!due?.p) return null;
  return redirectFor(s, due.p, due.episode);
}

/**
 * The redirect for one off-agenda episode. Also used the moment an episode opens, to
 * pre-compose the line while the grace period runs.
 */
export function redirectFor(s: Snapshot, p: PersonView, episode: Episode): Intervention {
  const question = nextQuestion(s, s.topic);
  const vars = { ...base(s, p), question, summary: episode.summary, quote: episode.quote };

  const other = episode.verdict === "otherTopic" ? s.topics.findIndex((t) => t.id === episode.topicId) : -1;
  if (other >= 0) {
    return {
      trigger: "offAgenda",
      kind: "otherTopic",
      topicId: topicId(s),
      targetId: p.id,
      vars: { ...vars, otherTopicTitle: s.topics[other]!.title, otherTopicNumber: String(other + 1) },
      actions: ["speak"],
      priority: true,
      redirects: true,
      question,
    };
  }
  return {
    trigger: "offAgenda",
    kind: "offAgenda",
    topicId: topicId(s),
    targetId: p.id,
    vars,
    actions: ["park", "speak"],
    priority: true,
    redirects: true,
    question,
    park: { discordId: p.id, name: p.name, summary: episode.summary, quote: episode.quote, topicId: topicId(s) },
  };
}

/** One person holds most of the recent speaking time while someone else is quiet. */
function floorHog(s: Snapshot): Intervention | null {
  if (s.people.length < 2) return null;
  const windowMs = s.policy.floorWindowSeconds * S;
  const total = s.people.reduce((sum, p) => sum + p.windowMs, 0);
  if (!total) return null;
  // Someone already drifting off the agenda gets the targeted redirect (and the parking
  // lot) from offAgenda once their grace runs out, not a generic floor handover.
  const drifting = new Set(s.episodes.map((e) => e.id));
  const hog = s.people.find(
    (p) =>
      p.holding &&
      !drifting.has(p.id) &&
      p.windowMs >= Math.min(s.policy.floorMinSpeakingSeconds * S, windowMs) &&
      p.windowMs / total >= s.policy.floorShareThreshold,
  );
  if (!hog) return null;
  const pick = pickSpeaker(s, [hog.id]);
  if (!pick) return null;
  const question = nextQuestion(s, s.topic);
  return {
    trigger: "floorHog",
    kind: "floorHog",
    topicId: topicId(s),
    targetId: hog.id,
    addresseeId: pick.person.id,
    vars: { ...base(s, hog), question, addresseeName: pick.person.name, recap: s.recaps[hog.id] ?? "" },
    actions: ["speak"],
    priority: true,
    redirects: true,
    question,
  };
}

/** The topic ran past budget × factor: move on — or, after the last one, wrap up. */
function topicOverrun(s: Snapshot): Intervention | null {
  const t = s.topic;
  if (!t || !t.budgetSeconds) return null;
  if (s.now - s.topicStartedAt < t.budgetSeconds * s.policy.topicOverrunFactor * S) return null;
  const next = s.topics[s.topicIndex + 1];
  if (!next) {
    return {
      trigger: "topicOverrun",
      kind: "wrapUp",
      topicId: t.id,
      vars: {
        ...base(s),
        parkedList: s.parked.map((p) => `${p.name} on ${p.summary}`).join(", "),
        carriedList: s.carried.map((p) => `${p.name} on ${p.summary}`).join(", "),
      },
      actions: ["speak", "advance"],
      priority: false,
    };
  }
  const nextQ = nextQuestion(s, next);
  return {
    trigger: "topicOverrun",
    kind: "topicOverrun",
    topicId: t.id,
    vars: { ...base(s), nextTopicTitle: next.title, nextQuestion: nextQ },
    actions: ["speak", "advance"],
    priority: false,
    question: nextQ,
  };
}

/** Dead air inside a topic: invite someone specific, with a concrete question. */
function silence(s: Snapshot): Intervention | null {
  if (!s.topic || s.silenceMs < s.policy.silenceSeconds * S) return null;
  if (s.people.some((p) => p.holding)) return null;
  const pick = pickSpeaker(s);
  if (!pick) return null;
  const question = nextQuestion(s, s.topic);
  if (pick.everyoneHeard && s.people.length > 1) {
    const order = roundOrder(s);
    return {
      trigger: "silence",
      kind: "roundRobin",
      topicId: topicId(s),
      addresseeId: order[0]?.id,
      vars: { ...base(s), question, names: order.map((p) => p.name).join(", then ") },
      actions: ["speak"],
      priority: false,
      question,
    };
  }
  return {
    trigger: "silence",
    kind: "silence",
    topicId: topicId(s),
    addresseeId: pick.person.id,
    vars: {
      ...base(s, pick.person),
      question,
      reason: pick.reason,
      // Only set when true, so templates can pick the right phrasing.
      notHeardOn: pick.person.topicMs === 0 ? (s.topic.title ?? "") : "",
    },
    actions: ["speak"],
    priority: false,
    question,
  };
}

// --- helpers -------------------------------------------------------------------------------

function topicId(s: Snapshot): string | null {
  return s.topic?.id ?? null;
}

function person(s: Snapshot, id: string): PersonView | undefined {
  return s.people.find((p) => p.id === id);
}

function base(s: Snapshot, who?: PersonView): Record<string, string> {
  return {
    name: who?.name ?? "",
    topicTitle: s.topic?.title ?? "",
    topicGoal: s.topic?.goal ?? "",
    purpose: s.purpose,
  };
}

/** The first of the topic's questions not yet put to the room; then they cycle. */
export function nextQuestion(s: Snapshot, topic: Topic | null | undefined): string {
  if (!topic) return "";
  const qs = topic.questions;
  if (!qs.length) return render(s.fallbackQuestion, { topicTitle: topic.title, topicGoal: topic.goal });
  const asked = s.asked[topic.id] ?? [];
  return qs.find((q) => !asked.includes(q)) ?? qs[asked.length % qs.length]!;
}
