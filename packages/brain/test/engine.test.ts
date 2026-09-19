/** The whole loop on the recorded off-agenda meeting, stub model, fake clock. */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { loadConfig } from "../src/config";
import { loadAgendaFile } from "../src/contract/agenda";
import { type BrainFrame, type EarsFrame, parseEarsFrame } from "../src/contract/frames";
import { StubLlm } from "../src/chair/llm";
import { SilentTts } from "../src/chair/tts";
import { MemoryStore } from "../src/ears/store";
import { Engine } from "../src/engine";

const FIXTURES = resolve(__dirname, "../../contract/fixtures");

async function replay(policy: Record<string, unknown> = {}) {
  const config = loadConfig();
  Object.assign(config.policy.defaults, policy);
  const frames = readFileSync(resolve(FIXTURES, "replay.offagenda.jsonl"), "utf8")
    .trim()
    .split("\n")
    .map((l) => parseEarsFrame(JSON.parse(l)) as EarsFrame);
  let now = 0;
  const sent: BrainFrame[] = [];
  const echoes: EarsFrame[] = [];
  const store = new MemoryStore();
  const engine = new Engine({
    config: () => config,
    clock: () => now,
    wire: {
      connected: true,
      send(f) {
        sent.push(f);
        if (f.type === "speak") echoes.push({ type: "spoken", utteranceId: f.utteranceId, atMs: now + 5_000 });
        return true;
      },
    },
    store,
    llm: new StubLlm(),
    tts: new SilentTts(),
    fallbackAgenda: loadAgendaFile(resolve(FIXTURES, "agenda.demo.json")),
  });
  const queue = [...frames];
  for (now = 0; now <= 390_000; now += 250) {
    for (const f of [...queue, ...echoes].filter((x) => x.atMs <= now)) {
      queue.includes(f) ? queue.splice(queue.indexOf(f), 1) : echoes.splice(echoes.indexOf(f), 1);
      engine.handle(f);
    }
    engine.tick();
    await engine.idle();
  }
  return { engine, sent, store };
}

describe("engine on replay.offagenda.jsonl", () => {
  it("prompts the quiet, moves the agenda, parks the tangent, escalates, wraps up", async () => {
    const { engine, sent, store } = await replay();
    expect(engine.history.map((h) => h.kind)).toEqual([
      "silence",
      "topicOverrun",
      "offAgenda",
      "escalateFirm",
      "topicOverrun",
      "silence",
      "wrapUp",
    ]);
    const speaks = sent.filter((f) => f.type === "speak");
    expect(speaks.map((f) => f.type === "speak" && f.priority)).toEqual([false, false, true, true, false, false, false]);
    expect(store.memories).toHaveLength(1);
    expect(store.memories[0]).toMatchObject({ discordId: "100000000000000001", kind: "parked", sessionId: "replay-offagenda" });
    expect(store.interventions).toHaveLength(7);
    expect(engine.history[6]?.line).toContain("Parked for later: Vitaly on");
    // Minimum gap between interventions (escalation excepted) held throughout.
    const gaps = engine.history.slice(1).map((h, i) => [h.kind, h.at - engine.history[i]!.at] as const);
    for (const [kind, gap] of gaps) if (!kind.startsWith("escalate")) expect(gap).toBeGreaterThanOrEqual(45_000);
  });

  it("with allowMute the host is still never muted", async () => {
    const { sent } = await replay({ allowMute: true });
    expect(sent.some((f) => f.type === "mute")).toBe(false);
  });
});

describe("config", () => {
  it("every YAML file validates and every intervention kind has a template", () => {
    const c = loadConfig();
    for (const kind of Object.values(c.chair.kinds)) expect(kind.templates.length).toBeGreaterThan(0);
    expect(c.models.prices[c.models.profiles.fast.model]).toBeDefined();
    expect(c.models.prices[c.models.profiles.normal.model]).toBeDefined();
  });
});
