import { loadConfig } from "../src/config";
import type { Topic } from "../src/contract/agenda";
import type { PersonView, Snapshot } from "../src/policy/snapshot";

export const config = loadConfig();

export const TOPICS: Topic[] = [
  { id: "t1", title: "Status", goal: "One status each", budgetSeconds: 90, owner: "ana", mustHear: ["marc"], questions: ["What slipped?"] },
  { id: "t2", title: "The date", goal: "A date", budgetSeconds: 120, owner: "vit", mustHear: [], questions: ["What date can you defend?"] },
];

export function person(id: string, over: Partial<PersonView> = {}): PersonView {
  const names: Record<string, string> = { vit: "Vitaly", ana: "Ana", marc: "Marc" };
  return {
    id,
    name: names[id] ?? id,
    role: id === "vit" ? "host" : "attendee",
    totalMs: 0,
    topicMs: 0,
    windowMs: 0,
    holding: false,
    holdingSince: null,
    ...over,
  };
}

export function snap(over: Partial<Snapshot> = {}): Snapshot {
  return {
    now: 1_000_000,
    purpose: "Ship it",
    policy: { ...config.policy.defaults },
    engine: config.policy.engine,
    pick: config.policy.pickSpeaker,
    topics: TOPICS,
    topicIndex: 0,
    topic: TOPICS[0]!,
    topicStartedAt: 1_000_000 - 30_000,
    people: [person("vit"), person("ana"), person("marc")],
    chairBusy: false,
    lastInterventionAt: null,
    silenceMs: 0,
    episodes: [],
    redirect: null,
    escalatedAt: {},
    lastSpeakerId: null,
    lastPromptedId: null,
    asked: {},
    recaps: {},
    parked: [],
    carried: [],
    fallbackQuestion: config.chair.fallbackQuestion,
    ...over,
  };
}
