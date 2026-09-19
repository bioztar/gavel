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
      "startMeeting",
      "silence",
      "topicOverrun",
      "offAgenda",
      "escalateFirm",
      "topicOverrun",
      "silence",
      "wrapUp",
    ]);
    const speaks = sent.filter((f) => f.type === "speak");
    expect(speaks.every((f) => f.text && f.text.length > 0)).toBe(true);
    expect(speaks.map((f) => f.type === "speak" && f.priority)).toEqual([false, false, false, true, true, false, false, false]);
    expect(store.memories).toHaveLength(1);
    expect(store.memories[0]).toMatchObject({ discordId: "100000000000000001", kind: "parked", sessionId: "replay-offagenda" });
    expect(store.interventions).toHaveLength(8);
    expect(engine.history[7]?.line).toContain("Parked for later: Vitaly on");
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

describe("a meeting with a purpose but no topics", () => {
  it("runs as one implicit topic: invites the quiet, catches drift, never overruns", async () => {
    const config = loadConfig();
    let now = 0;
    const sent: BrainFrame[] = [];
    const engine = new Engine({
      config: () => config,
      clock: () => now,
      wire: { connected: false, send: (f) => (sent.push(f), false) },
      store: new MemoryStore(),
      llm: new StubLlm(),
      tts: new SilentTts(),
      fallbackAgenda: null,
    });
    engine.handle({ type: "ready", channelId: "c", participants: [{ discordId: "a", name: "Artem" }], atMs: 0 });
    engine.handle({
      type: "session.started",
      sessionId: "s",
      title: "An AI meeting moderator demo",
      context: "Talk about the moderator and how it works",
      agenda: { purpose: "Present the AI moderator", topics: [], attendees: [], policy: {}, totalSeconds: 0 },
      atMs: 0,
    });
    expect(engine.view()).toMatchObject({ phase: "gathering", readyToStart: true });
    engine.handle({
      type: "transcript",
      discordId: "a",
      text: "Karen, let's start the meeting",
      final: true,
      utteranceId: "start",
      atMs: 0,
    });
    expect(engine.topic()).toMatchObject({ id: "main", title: "An AI meeting moderator demo", budgetSeconds: 0 });
    for (now = 0; now <= 20_000; now += 250) {
      engine.tick();
      await engine.idle();
    }
    expect(engine.history.map((h) => h.kind)).toEqual(["startMeeting"]);
    expect(engine.history[0]?.line).toContain("Artem");
  });
});

describe("Karen and the meeting lobby", () => {
  it("waits for expected people, then starts only on an explicit instruction", async () => {
    const config = loadConfig();
    let now = 0;
    const engine = new Engine({
      config: () => config,
      clock: () => now,
      wire: { connected: false, send: () => false },
      store: new MemoryStore(),
      llm: new StubLlm(),
      tts: new SilentTts(),
      fallbackAgenda: null,
    });
    const agenda = loadAgendaFile(resolve(FIXTURES, "agenda.demo.json"));
    engine.handle({ type: "ready", channelId: "c", participants: [{ discordId: "100000000000000001", name: "Vitaly" }], atMs: 0 });
    engine.handle({ type: "session.started", sessionId: "s", title: "Sync", agenda, atMs: 0 });
    now = 60_000;
    expect(engine.tick()).toBeNull(); // no timer-based opening or silence prompt in the lobby
    engine.handle({ type: "transcript", discordId: "100000000000000001", text: "Karen, let's start the meeting", final: true, utteranceId: "early", atMs: now });
    expect(engine.tick()?.kind).toBe("waitingForPeople");
    await engine.idle();
    expect(engine.phase).toBe("gathering");

    engine.handle({ type: "participants", participants: agenda.attendees.map(({ discordId, name }) => ({ discordId, name })), atMs: now });
    engine.handle({ type: "transcript", discordId: "100000000000000001", text: "Karen, please begin the meeting", final: true, utteranceId: "ready", atMs: now });
    expect(engine.tick()?.kind).toBe("startMeeting");
    await engine.idle();
    expect(engine.view()).toMatchObject({ chairName: "Karen", phase: "active", readyToStart: false });
  });
});

describe("talking to Karen, as in the 2026-09-19 demo transcript", () => {
  function lobby(compose: (user: string) => string | null = () => null) {
    const config = loadConfig();
    let now = 0;
    const prompts: string[] = [];
    const sent: BrainFrame[] = [];
    const llm = {
      composes: true,
      classify: async () => null,
      compose: async (req: { user: string }) => (prompts.push(req.user), compose(req.user)),
    };
    const engine = new Engine({
      config: () => config,
      clock: () => now,
      wire: { connected: true, send: (f) => (sent.push(f), true) },
      store: new MemoryStore(),
      llm,
      tts: new SilentTts(),
      fallbackAgenda: null,
    });
    const agenda = loadAgendaFile(resolve(FIXTURES, "agenda.demo.json"));
    engine.handle({ type: "ready", channelId: "c", participants: agenda.attendees.map(({ discordId, name }) => ({ discordId, name })), atMs: 0 });
    engine.handle({ type: "session.started", sessionId: "s", title: "Sync", agenda, atMs: 0 });
    const artem = agenda.attendees[0]!.discordId;
    let n = 0;
    const step = async (at: number) => {
      now = at;
      const iv = engine.tick();
      await engine.idle();
      // Karen finished speaking.
      const speak = sent.findLast((f) => f.type === "speak");
      if (speak?.type === "speak") engine.handle({ type: "spoken", utteranceId: speak.utteranceId, atMs: at });
      return iv;
    };
    const say = async (text: string, at: number) => {
      engine.handle({ type: "transcript", discordId: artem, text, final: true, utteranceId: `u${n++}`, atMs: at });
      return step(at);
    };
    const speaking = (on: boolean, at: number) =>
      engine.handle({ type: on ? "speaking.start" : "speaking.end", discordId: artem, atMs: at });
    return { engine, prompts, sent, say, speaking, tick: step };
  }

  it("hears the name at the end of a sentence and starts the meeting", async () => {
    const { engine, say } = lobby();
    expect((await say("Yeah. Working. Let's start the meeting, please, Karen.", 1_000))?.kind).toBe("startMeeting");
    expect(engine.phase).toBe("active");
  });

  it("answers the question, not a bare '.', and tells the model where the meeting is", async () => {
    const { prompts, say, tick } = lobby((user) => (user.includes("meeting about") ? "Status, the date, owners." : "Hi!"));
    // A bare greeting waits for the rest of the question; nothing comes, so it is answered.
    expect(await say("Hello, Karen.", 1_000)).toBeNull();
    const iv = await tick(3_000);
    expect(iv?.vars.request).toBe("Hello.");
    expect(iv?.vars.meetingState).toMatch(/^Not started yet/);
    expect(iv?.vars.question).toBeUndefined();
    const iv2 = await say("What is this meeting about, Karen?", 4_000);
    expect(iv2?.vars.request).toBe("What is this meeting about?");
    expect(iv2?.vars.agendaList).toMatch(/, and /);
    // Never served from the cache of an earlier answer.
    expect(prompts).toHaveLength(2);
    // The room's conversation, Karen's own lines included, in the order it was said.
    expect(prompts[1]).toContain("Vitaly: Hello, Karen.\nKaren: Hi!\nVitaly: What is this meeting about, Karen?");
  });

  it("'Karen,' then the request in the next chunk, with what came before as context", async () => {
    const { say, tick } = lobby(() => "ok");
    await say("What is our agenda today?", 1_000);
    expect(await say("Karen,", 2_000)).toBeNull();
    const iv = await say("please answer.", 4_000);
    expect(iv?.kind).toBe("addressed");
    expect(iv?.vars.request).toBe("please answer.");
    expect(iv?.vars.earlierWords).toBe("What is our agenda today?");
    // Name alone and nothing after: answered from the earlier words once they go quiet.
    await say("Karen?", 20_000);
    expect(await tick(21_000)).toBeNull();
    expect((await tick(22_500))?.vars.request).toBe("(only your name)");
  });

  it("'Hey, Karen.' then the question a few seconds later is one request", async () => {
    const { say, speaking, tick } = lobby(() => "ok");
    speaking(true, 500);
    expect(await say("Hey, Karen.", 1_000)).toBeNull();
    expect(await tick(3_500)).toBeNull(); // still talking: the question is on its way
    const iv = await say("How are we doing?", 4_000);
    expect(iv?.vars.request).toBe("Hey. How are we doing?");
  });

  it("a talker who never pauses is answered once the follow-up wait runs out", async () => {
    const { say, speaking, tick } = lobby(() => "ok");
    speaking(true, 500);
    await say("Karen,", 1_000);
    expect(await tick(6_500)).toBeNull();
    expect((await tick(7_000))?.kind).toBe("addressed");
  });

  it("never says the same line twice: asks once more, then stays quiet", async () => {
    const { engine, prompts, sent, say } = lobby(() => "Why don't meetings get lost? They follow the agenda!");
    await say("Karen, tell me a joke.", 1_000);
    await say("Karen, another joke, please.", 20_000);
    const spoken = sent.filter((f) => f.type === "speak" || f.type === "speak.start");
    expect(spoken).toHaveLength(1);
    expect(prompts).toHaveLength(3);
    expect(prompts[2]).toContain("You already said these lines in this meeting: Why don't meetings");
    expect(engine.history.at(-1)?.line).toBe("");
  });

  it("a second try with new words is spoken", async () => {
    const lines = ["Thanks Ana, Marc, what's the one thing a dog does no cat could?", "Thanks Ana, Marc, what's the one thing a dog does that no cat ever could?", "Marc, your turn: dogs or cats?"];
    const { sent, say } = lobby(() => lines.shift() ?? null);
    await say("Karen, what now?", 1_000);
    await say("Karen, and now?", 20_000);
    const spoken = sent.flatMap((f) => (f.type === "speak" ? [f.text] : []));
    expect(spoken).toEqual(["Thanks Ana, Marc, what's the one thing a dog does no cat could?", "Marc, your turn: dogs or cats?"]);
  });

  it("'Let's start the meeting, please.' then just 'Karen.' starts it", async () => {
    const { engine, say, tick } = lobby();
    await say("Let's start the meeting, please.", 1_000);
    expect(await say("Karen.", 2_000)).toBeNull();
    expect((await tick(4_500))?.kind).toBe("startMeeting");
    expect(engine.phase).toBe("active");
  });

  it("with template fallback off, a model that gives nothing means Karen stays quiet", async () => {
    const { engine, sent, say } = lobby(() => null);
    await say("Karen, can you tell me a joke?", 1_000);
    expect(engine.history.at(-1)?.kind).toBe("addressed");
    expect(sent.filter((f) => f.type === "speak")).toHaveLength(0);
  });
});

describe("streamed speech", () => {
  it("sends speak.start at once, each chunk as it lands, then speak.end", async () => {
    const config = loadConfig();
    config.models.tts.transport = "stream";
    const sent: BrainFrame[] = [];
    const tts = {
      synthesize: async () => ({ audio: Buffer.alloc(0), format: "wav", latencyMs: 0, cached: false }),
      stream: async (_text: string, onChunk: (pcm: Buffer) => void) => {
        expect(sent.map((f) => f.type)).toEqual(["speak.start"]); // ears is already playing
        onChunk(Buffer.from([1, 2]));
        onChunk(Buffer.from([3, 4]));
        return { firstAudioMs: 210, cached: false };
      },
    };
    const engine = new Engine({
      config: () => config,
      clock: () => 0,
      wire: { connected: true, send: (f) => (sent.push(f), true) },
      store: new MemoryStore(),
      llm: new StubLlm(),
      tts,
      fallbackAgenda: null,
    });
    const out = await engine.speak("Hello there.", true);
    expect(sent.map((f) => f.type)).toEqual(["speak.start", "speak.chunk", "speak.chunk", "speak.end"]);
    expect(sent[0]).toMatchObject({ text: "Hello there.", sampleRate: 48000, channels: 1, priority: true });
    // ears holds it for a pause; a priority line waits less before cutting in.
    expect(sent[0]).toMatchObject({ quietMs: config.policy.speak.quietMs, maxWaitMs: config.policy.speak.priorityMaxWaitMs });
    expect(sent[1]).toMatchObject({ audio: Buffer.from([1, 2]).toString("base64") });
    expect(new Set(sent.map((f) => ("utteranceId" in f ? f.utteranceId : null))).size).toBe(1);
    expect(out.ttsMs).toBe(210);
  });

  it("a TTS failure still closes the line so ears reports spoken", async () => {
    const config = loadConfig();
    config.models.tts.transport = "stream";
    const sent: BrainFrame[] = [];
    const engine = new Engine({
      config: () => config,
      clock: () => 0,
      wire: { connected: true, send: (f) => (sent.push(f), true) },
      store: new MemoryStore(),
      llm: new StubLlm(),
      tts: { synthesize: async () => { throw new Error("unused"); }, stream: async () => { throw new Error("socket closed"); } },
      fallbackAgenda: null,
    });
    await engine.speak("Hi.", false);
    expect(sent.at(-1)).toMatchObject({ type: "speak.end", error: "Error: socket closed" });
  });
});
