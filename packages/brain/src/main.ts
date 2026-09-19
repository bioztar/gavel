/**
 * The live chair: ears over the wire, Nebius through Mastra, SLNG for the voice, ears'
 * Postgres for memory. GET /state on STAGE_PORT is the stage's (and your) view.
 */
import { createServer } from "node:http";
import { env } from "./env";
import { loadConfig, watchConfig } from "./config";
import { loadAgendaFile } from "./contract/agenda";
import { MastraLlm } from "./chair/mastraLlm";
import { StubLlm } from "./chair/llm";
import { SilentTts, SlngTts } from "./chair/tts";
import { EarsStore } from "./ears/store";
import { EarsWire } from "./ears/wire";
import { Engine } from "./engine";
import { log } from "./log";
import { mastra } from "./mastra";
import { setConfig, setEngine } from "./runtime";

let config = loadConfig();
setConfig(config);

const agenda = (() => {
  try {
    return loadAgendaFile(env.agendaFile);
  } catch (err) {
    log.warn("agenda.file_unreadable", { path: env.agendaFile, error: String(err) });
    return null;
  }
})();

if (!env.nebiusApiKey) log.warn("nebius.off", { reason: "NEBIUS_API_KEY unset — keyword classifier + templates only" });
if (!env.slngApiKey) log.warn("tts.off", { reason: "SLNG_API_KEY unset — the chair cannot speak" });

const wire = new EarsWire(env.earsWireUrl);
let engine: Engine;
const llm = env.nebiusApiKey ? new MastraLlm(() => config.models, (u) => engine.recordUsage(u)) : new StubLlm();

engine = new Engine({
  config: () => config,
  clock: Date.now,
  wire,
  store: new EarsStore(env.earsHttpUrl),
  llm,
  tts: env.slngApiKey ? new SlngTts(() => config.models.tts, env.slngApiKey) : new SilentTts(),
  fallbackAgenda: agenda,
  // Every intervention runs as a traced Mastra workflow.
  runner: async (_engine, iv) => {
    const run = await mastra.getWorkflow("interveneWorkflow").createRun();
    const result = await run.start({ inputData: { intervention: iv } });
    if (result.status !== "success") throw new Error(`intervene workflow ${result.status}`);
    return result.result;
  },
});
setEngine(engine);

wire.on("frame", (frame) => engine.handle(frame));
wire.start();

let timer = setInterval(() => engine.tick(), config.policy.engine.tickMs);
// Edit any YAML mid-call: prompts, thresholds and models apply from the next tick.
watchConfig(config, (next) => {
  config = next;
  setConfig(next);
  clearInterval(timer);
  timer = setInterval(() => engine.tick(), next.policy.engine.tickMs);
});

createServer((req, res) => {
  if (req.url === "/state" || req.url === "/") {
    res.writeHead(200, { "content-type": "application/json", "access-control-allow-origin": "*" });
    res.end(JSON.stringify(engine.view(), null, 2));
    return;
  }
  res.writeHead(404).end();
}).listen(env.stagePort, env.stageHost, () =>
  log.info("brain.ready", {
    state: `http://${env.stageHost}:${env.stagePort}/state`,
    ears: env.earsWireUrl,
  }),
);

for (const sig of ["SIGINT", "SIGTERM"] as const) {
  process.on(sig, () => {
    wire.close();
    process.exit(0);
  });
}
