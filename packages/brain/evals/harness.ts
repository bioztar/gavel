/**
 * One case, through the chair's own code. Nothing here re-implements a decision:
 * `evaluate()` from src/policy/triggers picks the intervention off the frozen snapshot, and
 * the line comes out of `Engine.compose()` — the same prompt assembly (config/prompts/chair.yaml,
 * the session context block, the facts list) that main.ts and replay.ts use in a live call.
 *
 * The engine is given the case's agenda and room the normal way, by ears frames; only the
 * clock, the wire, the store and the TTS are stubs, exactly as in offline replay.
 */
import type { Config } from "../src/config";
import type { Llm } from "../src/chair/llm";
import { SilentTts } from "../src/chair/tts";
import { mergePolicy } from "../src/contract/agenda";
import type { BrainFrame } from "../src/contract/frames";
import { MemoryStore } from "../src/ears/store";
import type { Wire } from "../src/ears/wire";
import { Engine, type Composed } from "../src/engine";
import type { Intervention, Snapshot } from "../src/policy/snapshot";
import { evaluate } from "../src/policy/triggers";
import type { EvalCase } from "./types";

/** ears is not in the room: the eval never speaks, it only reads the line. */
class NullWire implements Wire {
  readonly connected = false;
  readonly sent: BrainFrame[] = [];

  send(frame: BrainFrame): boolean {
    this.sent.push(frame);
    return false;
  }
}

/** The frozen state, in the shape the policy reads. */
export function snapshotFor(c: EvalCase, config: Config): Snapshot {
  const s = c.state;
  const topics = c.agenda.topics;
  return {
    now: s.nowMs,
    purpose: c.agenda.purpose,
    policy: mergePolicy(config.policy.defaults, c.agenda),
    engine: config.policy.engine,
    pick: config.policy.pickSpeaker,
    newcomer: config.policy.newcomer,
    topics,
    topicIndex: s.topicIndex,
    topic: topics[s.topicIndex] ?? null,
    topicStartedAt: s.topicStartedAtMs,
    people: s.people,
    arrivals: [],
    chairBusy: false,
    lastInterventionAt: s.lastInterventionAtMs,
    silenceMs: s.silenceMs,
    roomSilenceMs: s.silenceMs,
    episodes: s.episodes,
    redirect: s.redirect,
    escalatedAt: s.escalatedAt,
    lastSpeakerId: s.lastSpeakerId,
    lastPromptedId: s.lastPromptedId,
    asked: s.asked,
    recaps: s.recaps,
    parked: s.parked,
    carried: s.carried,
    fallbackQuestion: config.chair.fallbackQuestion,
  };
}

/** The trigger the frozen state fires, straight from the policy. */
export function interventionFor(c: EvalCase, config: Config): Intervention | null {
  return evaluate(snapshotFor(c, config));
}

export interface Generated {
  intervention: Intervention;
  composed: Composed;
}

/**
 * The line the chair would say. `llm` is the only seam: a `StubLlm` composes nothing and the
 * YAML template speaks (offline, no network), `MastraLlm` goes to the configured model.
 */
export async function generateLine(c: EvalCase, config: Config, llm: Llm): Promise<Generated> {
  const engine = new Engine({
    config: () => config,
    clock: () => c.state.nowMs,
    wire: new NullWire(),
    store: new MemoryStore(),
    llm,
    tts: new SilentTts(),
    fallbackAgenda: null,
  });
  // How a real session begins: the agenda and then the room, over the ears wire.
  engine.handle({
    type: "session.started",
    sessionId: c.id,
    title: c.sessionTitle,
    agenda: c.agenda,
    atMs: c.state.nowMs,
  });
  engine.handle({
    type: "participants",
    participants: c.state.people.map((p) => ({ discordId: p.id, name: p.name })),
    atMs: c.state.nowMs,
  });

  const intervention = interventionFor(c, config);
  if (!intervention) throw new Error(`${c.id}: no trigger fired on the frozen state`);
  // The engine records an intervention the moment it launches one and composes after, and
  // the template rotation counts that entry. Live, `launch()` does this; here the frozen
  // state is the launch.
  engine.history.push({ ...intervention, at: c.state.nowMs });
  return { intervention, composed: await engine.compose(intervention) };
}
