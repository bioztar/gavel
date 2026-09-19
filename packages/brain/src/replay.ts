/**
 * Replay a recorded ears stream through the whole chair on a fake clock — no Discord, no
 * voice channel, no second person. The fastest loop for tuning YAML.
 *
 *   pnpm replay <file.jsonl> [--stub-llm] [--speed N] [--config DIR] [--agenda FILE]
 *                            [--policy key=value ...] [--store ears] [--speak] [--quiet]
 *
 * Defaults: as fast as possible, Nebius if NEBIUS_API_KEY is set, an in-memory store, and
 * the chair's lines printed instead of spoken. `--store ears` writes memories, interventions
 * and usage into ears' Postgres; `--speak` also sends them to ears to play in the call.
 * Model latency does not advance the fake clock.
 */
import { readFileSync } from "node:fs";
import { parseArgs } from "node:util";

process.env.GAVEL_MASTRA_STORAGE ??= "off";

const { env } = await import("./env");
const { loadConfig } = await import("./config");
const { loadAgendaFile } = await import("./contract/agenda");
const { parseEarsFrame } = await import("./contract/frames");
const { StubLlm } = await import("./chair/llm");
const { MastraLlm } = await import("./chair/mastraLlm");
const { SilentTts, SlngTts } = await import("./chair/tts");
const { EarsStore, MemoryStore } = await import("./ears/store");
const { EarsWire } = await import("./ears/wire");
const { Engine } = await import("./engine");
const { log } = await import("./log");
const { mastra } = await import("./mastra");
const { setConfig, setEngine } = await import("./runtime");
type EarsFrame = import("./contract/frames").EarsFrame;
type BrainFrame = import("./contract/frames").BrainFrame;

const { values, positionals } = parseArgs({
  allowPositionals: true,
  options: {
    "stub-llm": { type: "boolean", default: false },
    speed: { type: "string", default: "0" },
    config: { type: "string" },
    agenda: { type: "string" },
    policy: { type: "string", multiple: true, default: [] },
    store: { type: "string", default: "memory" },
    speak: { type: "boolean", default: false },
    quiet: { type: "boolean", default: false },
    tail: { type: "string", default: "30" },
  },
});

const file = positionals[0];
if (!file) {
  console.error("usage: pnpm replay <file.jsonl> [--stub-llm] [--speed N] [--policy allowMute=true] ...");
  process.exit(2);
}

const config = loadConfig(values.config);
// --policy overrides the YAML defaults (the agenda's own block still wins over both).
for (const kv of values.policy) {
  const [key, raw] = kv.split("=");
  if (!key || raw === undefined || !(key in config.policy.defaults)) throw new Error(`--policy ${kv}: unknown key`);
  (config.policy.defaults as Record<string, unknown>)[key] = raw === "true" ? true : raw === "false" ? false : Number(raw);
}
setConfig(config);

const frames: EarsFrame[] = readFileSync(file, "utf8")
  .split("\n")
  .filter((l) => l.trim())
  .map((l) => parseEarsFrame(JSON.parse(l)))
  .filter((f): f is EarsFrame => f !== null)
  .sort((a, b) => a.atMs - b.atMs);

let now = frames[0]?.atMs ?? 0;
const clock = () => now;
log.useClock(clock);
log.setQuiet(values.quiet);

/** Stands in for ears: `spoken` after the time the line would take to say, `moderation` at once. */
class FakeWire {
  connected = true;
  queue: EarsFrame[] = [];
  real = values.speak ? new EarsWire(env.earsWireUrl) : null;

  send(frame: BrainFrame): boolean {
    this.real?.send(frame);
    if (frame.type === "speak") {
      const ms = 600 + (lastLine.split(/\s+/).length / 2.6) * 1000;
      this.queue.push({ type: "spoken", utteranceId: frame.utteranceId, atMs: now + ms });
    } else if (frame.type === "mute") {
      this.queue.push({ type: "moderation", action: "muted", discordId: frame.discordId, until: now + frame.seconds * 1000, atMs: now });
      this.queue.push({ type: "moderation", action: "unmuted", discordId: frame.discordId, atMs: now + frame.seconds * 1000 });
    }
    return true;
  }
}

let lastLine = "";
const wire = new FakeWire();
if (wire.real) wire.real.start();
const store = values.store === "ears" ? new EarsStore(env.earsHttpUrl) : new MemoryStore();
const useModel = !values["stub-llm"] && !!env.nebiusApiKey;
let engine: InstanceType<typeof Engine>;

engine = new Engine({
  config: () => config,
  clock,
  wire,
  store,
  llm: useModel ? new MastraLlm(() => config.models, (u) => engine.recordUsage(u)) : new StubLlm(),
  tts: values.speak && env.slngApiKey ? new SlngTts(() => config.models.tts, env.slngApiKey) : new SilentTts(),
  fallbackAgenda: loadAgendaFile(values.agenda ?? env.agendaFile),
  runner: async (e, iv) => {
    const run = await mastra.getWorkflow("interveneWorkflow").createRun();
    const result = await run.start({ inputData: { intervention: iv } });
    if (result.status !== "success") throw new Error(`intervene workflow ${result.status}`);
    return result.result;
  },
});
setEngine(engine);

// Capture each line as it is composed, for the spoken-duration estimate and the transcript.
const said: Array<{ at: number; kind: string; line: string; source: string }> = [];
const compose = engine.compose.bind(engine);
engine.compose = async (iv) => {
  const out = await compose(iv);
  lastLine = out.line;
  said.push({ at: now, kind: iv.kind, line: out.line, source: out.source });
  return out;
};

const speed = Number(values.speed);
const tickMs = config.policy.engine.tickMs;
const end = (frames[frames.length - 1]?.atMs ?? 0) + Number(values.tail) * 1000;
const pending = [...frames];

console.log(`replay ${file} · ${frames.length} frames · ${useModel ? `nebius ${config.models.profiles.fast.model} / ${config.models.profiles.normal.model}` : "stub llm"}`);
while (now <= end) {
  const due = [...pending, ...wire.queue].filter((f) => f.atMs <= now).sort((a, b) => a.atMs - b.atMs);
  for (const f of due) {
    pending.includes(f) ? pending.splice(pending.indexOf(f), 1) : wire.queue.splice(wire.queue.indexOf(f), 1);
    engine.handle(f);
    await engine.idle();
  }
  engine.tick();
  await engine.idle();
  if (speed > 0) await new Promise((r) => setTimeout(r, tickMs / speed));
  now += tickMs;
}
wire.real?.close();

const mmss = (ms: number) => `${String(Math.floor(ms / 60000)).padStart(2, "0")}:${String(Math.floor((ms % 60000) / 1000)).padStart(2, "0")}`;
const t0 = frames[0]?.atMs ?? 0;
console.log("\n— what the chair said —");
for (const s of said) console.log(`${mmss(s.at - t0)}  ${s.kind.padEnd(13)} [${s.source}] ${s.line}`);
const view = engine.view();
console.log("\n— talk time (s) —");
for (const p of view.people) console.log(`${p.name.padEnd(10)} total ${String(p.totalSeconds).padStart(4)}`);
console.log("\n— parked —");
for (const p of view.parked) console.log(`${p.name}: ${p.summary}`);
const u = engine.usage;
console.log(`\n— model usage — ${u.calls} calls · ${u.inputTokens} in / ${u.outputTokens} out tokens · $${u.costUsd.toFixed(5)}`);
process.exit(0);
