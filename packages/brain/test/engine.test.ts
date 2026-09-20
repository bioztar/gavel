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
  const VIT = "100000000000000001";

  function lobby(present: Array<{ discordId: string; name: string }>, over: Record<string, unknown> = {}) {
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
    agenda.policy = { ...agenda.policy, ...over };
    engine.handle({ type: "ready", channelId: "c", participants: present, atMs: 0 });
    engine.handle({ type: "session.started", sessionId: "s", title: "Sync", agenda, atMs: 0 });
    const tick = async (at: number) => {
      now = at;
      const iv = engine.tick();
      await engine.idle();
      return iv;
    };
    const arrive = (people: Array<{ discordId: string; name: string }>, at: number) =>
      engine.handle({ type: "participants", participants: people, atMs: at });
    const say = (text: string, at: number, who = VIT) =>
      engine.handle({ type: "transcript", discordId: who, text, final: true, utteranceId: `u${at}`, atMs: at });
    return { engine, agenda, tick, arrive, say };
  }

  it("waits while anyone expected is missing, and opens itself once nobody is", async () => {
    const { engine, agenda, tick, arrive } = lobby([{ discordId: VIT, name: "Vitaly" }]);
    expect(await tick(60_000)).toBeNull(); // one of three: no opening, and no silence prompt
    expect(engine.view()).toMatchObject({ phase: "gathering", readyToStart: false });

    arrive(agenda.attendees.map(({ discordId, name }) => ({ discordId, name })), 60_000);
    expect(await tick(61_000)).toBeNull(); // the room only just filled: give it a moment
    expect((await tick(64_000))?.kind).toBe("startMeeting");
    expect(engine.view()).toMatchObject({ phase: "active", readyToStart: false });
  });

  it("asked to start, she starts — and says who never turned up", async () => {
    const { engine, tick, say } = lobby([{ discordId: VIT, name: "Vitaly" }]);
    say("Karen, let's start the meeting", 1_000);
    const iv = await tick(1_000);
    expect(iv?.kind).toBe("startMeeting");
    expect(iv?.vars.missingNote).toMatch(/Ana and Marc/);
    expect(engine.phase).toBe("active");
  });

  it("requireStart keeps her waiting however full the room is", async () => {
    const { engine, agenda, tick, arrive, say } = lobby([], { requireStart: true });
    arrive(agenda.attendees.map(({ discordId, name }) => ({ discordId, name })), 0);
    expect((await tick(10_000))?.kind).toBe("lobbyGreeting"); // hello, not the agenda
    expect(await tick(60_000)).toBeNull();
    expect(engine.phase).toBe("gathering");
    say("Karen, let's start the meeting", 60_000);
    expect((await tick(60_000))?.kind).toBe("startMeeting");
  });

  it("a meeting nobody was invited to waits to be asked, however many turn up", async () => {
    const { engine, tick, arrive } = lobby([]);
    engine.agenda!.attendees = []; // an ad-hoc session from the ears console: no roster
    arrive([{ discordId: "9", name: "Jo" }], 0);
    const iv = await tick(10_000);
    expect(iv?.kind).toBe("lobbyGreeting");
    expect(iv?.vars.missingNames).toBe(""); // nobody to wait for: tell them to say the word
    expect(await tick(60_000)).toBeNull();
    expect(engine.phase).toBe("gathering");
  });

  it("greets whoever walks into the lobby, and says who is still missing", async () => {
    const { engine, tick, arrive } = lobby([{ discordId: VIT, name: "Vitaly" }]);
    arrive([{ discordId: VIT, name: "Vitaly" }, { discordId: "100000000000000002", name: "Ana" }], 10_000);
    expect(await tick(10_500)).toBeNull(); // a moment for their audio to connect
    const iv = await tick(12_000);
    expect(iv?.kind).toBe("lobbyGreeting");
    expect(iv?.vars.names).toBe("Ana");
    expect(iv?.vars.missingNames).toBe("Marc");
    expect(engine.phase).toBe("gathering");
    // Discord re-lists the channel on any voice change; nobody is greeted twice.
    arrive([{ discordId: VIT, name: "Vitaly" }, { discordId: "100000000000000002", name: "Ana" }], 20_000);
    expect(await tick(30_000)).toBeNull();
  });

  it("the last arrival is not greeted: the opening welcomes them, seconds later", async () => {
    const { engine, agenda, tick, arrive } = lobby([{ discordId: VIT, name: "Vitaly" }]);
    arrive(agenda.attendees.map(({ discordId, name }) => ({ discordId, name })), 10_000);
    expect(await tick(12_000)).toBeNull();
    expect((await tick(15_500))?.kind).toBe("startMeeting");
  });

  it("binds an expected attendee to the speaker whose name is theirs", async () => {
    const { engine, tick, arrive } = lobby([]);
    // What a calendar invite carries when no operator mapped the emails to snowflakes.
    engine.agenda!.attendees = [
      { discordId: "vitaly@x.dev", name: "Vitaly", role: "host" },
      { discordId: "artem@x.dev", name: "Artem", role: "attendee" },
    ];
    engine.agenda!.topics[0]!.owner = "artem@x.dev";
    engine.agenda!.topics[0]!.mustHear = ["artem@x.dev"];
    arrive([{ discordId: "777", name: "Vitaly" }, { discordId: "888", name: "artemshambalev" }], 1_000);
    expect(engine.agenda!.attendees.map((a) => a.discordId)).toEqual(["777", "888"]);
    expect(engine.agenda!.attendees[1]!.name).toBe("artemshambalev");
    // The topic's owner follows them, or the chair would chase someone not in the call.
    expect(engine.agenda!.topics[0]!.owner).toBe("888");
    expect(engine.agenda!.topics[0]!.mustHear).toEqual(["888"]);
    expect(engine.view().missingAttendees).toEqual([]);
    // Nobody is missing any more, so the meeting opens by itself.
    expect(await tick(2_000)).toBeNull();
    expect((await tick(6_000))?.kind).toBe("startMeeting");
  });

  it("leaves a stranger a stranger: an unmatched name is never bound", async () => {
    const { engine, arrive } = lobby([]);
    engine.agenda!.attendees = [{ discordId: "vitaly@x.dev", name: "Vitaly", role: "host" }];
    arrive([{ discordId: "777", name: "Priya" }], 1_000);
    expect(engine.agenda!.attendees[0]!.discordId).toBe("vitaly@x.dev");
    expect(engine.view().missingAttendees).toEqual(["Vitaly"]);
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
    // These are the lobby's *answers*, not its opening: everyone expected is in the call,
    // so with the default policy Karen would open the meeting three seconds in.
    agenda.policy = { ...agenda.policy, requireStart: true };
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

describe("requireStart: false (the cats-and-dogs demo)", () => {
  function lobbyOf(agendaFile: string) {
    const config = loadConfig();
    let now = 0;
    const engine = new Engine({
      config: () => config,
      clock: () => now,
      wire: { connected: true, send: () => true },
      store: new MemoryStore(),
      llm: new StubLlm(),
      tts: new SilentTts(),
      fallbackAgenda: null,
    });
    const agenda = loadAgendaFile(resolve(FIXTURES, agendaFile));
    const people = [{ discordId: "1", name: "Ana" }, { discordId: "2", name: "Marc" }];
    engine.handle({ type: "ready", channelId: "c", participants: people, atMs: 0 });
    engine.handle({ type: "session.started", sessionId: "s", title: "Demo", agenda: { ...agenda, attendees: people.map((p) => ({ ...p, role: "attendee" })) }, atMs: 0 });
    const tick = async (at: number) => {
      now = at;
      const iv = engine.tick();
      await engine.idle();
      return iv;
    };
    return { engine, tick };
  }

  it("Karen opens the meeting herself once everyone has been in the call a moment", async () => {
    const { engine, tick } = lobbyOf("agenda.cats-dogs.json");
    expect(engine.view().requireStart).toBe(false);
    expect(await tick(1_000)).toBeNull(); // everyone is here: the delay starts
    expect(await tick(3_500)).toBeNull();
    expect((await tick(4_000))?.kind).toBe("startMeeting");
    expect(engine.phase).toBe("active");
  });

  it("opens once, even while her opening line is still being written", async () => {
    const config = loadConfig();
    let now = 0;
    let release: () => void = () => {};
    const composed: string[] = [];
    const spokenIds: string[] = [];
    const engine = new Engine({
      config: () => config,
      clock: () => now,
      wire: { connected: true, send: (f) => (f.type === "speak" && spokenIds.push(f.utteranceId), true) },
      store: new MemoryStore(),
      // A slow model: the opening is still composing across the next ticks.
      llm: {
        composes: true,
        classify: async () => null,
        compose: (req: { user: string }) =>
          new Promise<string>((done) => (release = () => done(`Welcome ${composed.push(req.user)}.`))),
      },
      tts: new SilentTts(),
      fallbackAgenda: null,
    });
    const agenda = loadAgendaFile(resolve(FIXTURES, "agenda.cats-dogs.json"));
    const people = [{ discordId: "1", name: "Ana" }, { discordId: "2", name: "Marc" }];
    engine.handle({ type: "ready", channelId: "c", participants: people, atMs: 0 });
    engine.handle({ type: "session.started", sessionId: "s", title: "Demo", agenda: { ...agenda, attendees: people.map((p) => ({ ...p, role: "attendee" })) }, atMs: 0 });
    for (now = 1_000; now <= 6_000; now += 250) engine.tick();
    release();
    await engine.idle();
    for (now = 6_250; now <= 20_000; now += 250) {
      // ears: each line has finished playing by the next tick.
      for (const id of spokenIds.splice(0)) engine.handle({ type: "spoken", utteranceId: id, atMs: now });
      engine.tick();
      release();
      await engine.idle();
    }
    expect(engine.history.filter((h) => h.kind === "startMeeting")).toHaveLength(1);
  });

  it("is the default now: an agenda that says nothing about it still opens itself", async () => {
    const { engine, tick } = lobbyOf("agenda.demo.json");
    expect(engine.view().requireStart).toBe(false);
    expect(await tick(1_000)).toBeNull();
    expect((await tick(4_500))?.kind).toBe("startMeeting");
    expect(engine.phase).toBe("active");
  });
});

describe("timed: false — topics in any order, no time limits", () => {
  const VIT = "100000000000000001";
  const ANA = "100000000000000002";
  const BLOCKERS = "so who actually owns the database migration blocker and the flaky payments tests right now";
  const STATUS = "going back to where we actually are, the staging build is green and QA started this morning";

  function meeting(timed: boolean) {
    const config = loadConfig();
    let now = 0;
    let n = 0;
    const llm = {
      composes: true,
      classify: async (req: { window: string }) =>
        /blocker/.test(req.window) ? { verdict: "otherTopic" as const, topicId: "t3", summary: "blocker owners" }
        : /staging/.test(req.window) ? { verdict: "otherTopic" as const, topicId: "t1", summary: "where we are" }
        : { verdict: "current" as const },
      compose: async () => `Line ${n++}, noted.`,
    };
    const engine = new Engine({
      config: () => config,
      clock: () => now,
      wire: { connected: true, send: () => true },
      store: new MemoryStore(),
      llm,
      tts: new SilentTts(),
      fallbackAgenda: null,
    });
    const agenda = loadAgendaFile(resolve(FIXTURES, "agenda.demo.json"));
    agenda.policy = { ...agenda.policy, timed, silenceSeconds: 10_000, offAgendaGraceSeconds: 5 };
    engine.handle({ type: "ready", channelId: "c", participants: agenda.attendees.map(({ discordId, name }) => ({ discordId, name })), atMs: 0 });
    engine.handle({ type: "session.started", sessionId: "s", title: "Sync", agenda, atMs: 0 });
    const tick = async (at: number) => {
      now = at;
      const iv = engine.tick();
      await engine.idle();
      return iv;
    };
    const talk = async (id: string, text: string, from: number, to: number) => {
      engine.handle({ type: "speaking.start", discordId: id, atMs: from });
      now = to;
      engine.handle({ type: "transcript", discordId: id, text, final: true, utteranceId: `u${n++}`, atMs: to });
      await engine.idle();
    };
    const start = async () => {
      await talk(VIT, "Karen, let's start the meeting.", 1_000, 1_000);
      expect((await tick(1_000))?.kind).toBe("startMeeting");
      engine.handle({ type: "speaking.end", discordId: VIT, atMs: 1_500 });
    };
    return { engine, tick, talk, start };
  }

  it("never calls time on a topic", async () => {
    const timed = meeting(true);
    await timed.start();
    expect((await timed.tick(200_000))?.kind).toBe("topicOverrun");

    const untimed = meeting(false);
    await untimed.start();
    expect(await untimed.tick(200_000)).toBeNull();
    expect(untimed.engine.view()).toMatchObject({ timed: false, phase: "active", topic: { id: "t1" } });
  });

  it("follows the room to any agenda item, later or earlier, instead of redirecting", async () => {
    const { engine, tick, talk, start } = meeting(false);
    await start();
    await talk(ANA, BLOCKERS, 10_000, 14_000);
    expect(engine.view().topic?.id).toBe("t3");
    expect(engine.snapshot().episodes).toEqual([]);
    expect(await tick(30_000)).toBeNull(); // no "we'll get there" redirect

    await talk(VIT, STATUS, 40_000, 44_000);
    expect(engine.view().topic?.id).toBe("t1");
    expect(engine.view().topics.map((t) => [t.id, t.done, t.discussed])).toEqual([
      ["t1", false, true],
      ["t2", false, false],
      ["t3", false, true],
    ]);
  });
});

describe("keeping up with the room, as in the 2026-09-19 cats-vs-dogs session", () => {
  const VIT = "100000000000000001";
  const ANA = "100000000000000002";
  const MARC = "100000000000000003";
  const WEATHER = "honestly the weather here is so humid and hot, and I saw helicopters over the beach today";

  function room(compose: (user: string) => string | null = () => null, policy: Record<string, unknown> = {}) {
    const config = loadConfig();
    config.policy.defaults.offAgendaGraceSeconds = 5;
    let now = 0;
    let n = 0;
    const sent: BrainFrame[] = [];
    const prompts: string[] = [];
    const classified: string[] = [];
    const llm = {
      composes: true,
      classify: async (req: { window: string }) => {
        classified.push(req.window);
        return /weather|helicopters|beach/.test(req.window)
          ? { verdict: "offAgenda" as const, summary: "the weather" }
          : { verdict: "current" as const };
      },
      compose: async (req: { user: string }) => (prompts.push(req.user), compose(req.user) ?? `Line ${n++}, noted.`),
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
    agenda.policy = { ...agenda.policy, minSecondsBetweenInterventions: 12, ...policy };
    engine.handle({ type: "ready", channelId: "c", participants: agenda.attendees.map(({ discordId, name }) => ({ discordId, name })), atMs: 0 });
    engine.handle({ type: "session.started", sessionId: "s", title: "Sync", agenda, atMs: 0 });
    const tick = async (at: number) => {
      now = at;
      const iv = engine.tick();
      await engine.idle();
      return iv;
    };
    const say = async (id: string, text: string, at: number) => {
      now = at;
      engine.handle({ type: "transcript", discordId: id, text, final: true, utteranceId: `u${n++}`, atMs: at });
      await engine.idle();
    };
    const talking = (id: string, at: number) => engine.handle({ type: "speaking.start", discordId: id, atMs: at });
    const quiet = (id: string, at: number) => engine.handle({ type: "speaking.end", discordId: id, atMs: at });
    /** ears: Karen's line finished playing. */
    const spoken = (at: number) => {
      now = at;
      const line = sent.findLast((f) => f.type === "speak");
      if (line?.type === "speak") engine.handle({ type: "spoken", utteranceId: line.utteranceId, atMs: at });
    };
    const lines = () => sent.flatMap((f) => (f.type === "speak" ? [f.text] : []));
    const start = async () => {
      await say(VIT, "Karen, let's start the meeting.", 1_000);
      expect((await tick(1_000))?.kind).toBe("startMeeting");
    };
    return { engine, sent, prompts, classified, tick, say, talking, quiet, spoken, lines, start };
  }

  it("a tangent started while Karen is talking is caught then, not once she has finished", async () => {
    const { engine, classified, tick, say, talking, spoken, start } = room();
    await start(); // Karen is speaking the opening line
    talking(ANA, 2_000);
    await say(ANA, WEATHER, 6_000);
    expect(classified).toHaveLength(1);
    expect(engine.snapshot().episodes[0]?.episode.offSince).toBe(6_000);
    spoken(8_000);
    // Grace (5 s) ran from 6 s; the gap between interventions (12 s from 1 s) is what holds it.
    expect(await tick(12_750)).toBeNull();
    expect(await tick(13_000)).toMatchObject({ kind: "offAgenda", targetId: ANA });
  });

  it("the grace period counts from the first words of the drift, not from the verdict", async () => {
    const { engine, tick, say, talking, spoken, start } = room();
    await start();
    spoken(2_000);
    talking(ANA, 3_000);
    await say(ANA, "so about where we are, I think", 7_000); // too few words to judge
    await say(ANA, WEATHER, 12_000);
    expect(engine.snapshot().episodes[0]?.episode.offSince).toBe(7_000);
    expect(await tick(13_000)).toMatchObject({ kind: "offAgenda", targetId: ANA });
  });

  it("holds the redirect once someone else has taken the room on", async () => {
    const { engine, tick, say, talking, quiet, spoken, start } = room();
    await start();
    spoken(2_000);
    talking(ANA, 3_000);
    await say(ANA, WEATHER, 7_000);
    talking(MARC, 8_000);
    await say(MARC, "Back to status: payments slipped a week, push is on track.", 10_000);
    quiet(MARC, 10_500);
    // Ana still makes noise, but "Ana, …" would now land on Marc's point.
    expect(await tick(14_000)).toBeNull();
    expect(engine.snapshot().episodes).toHaveLength(1);
    // She carries on with the tangent: now the redirect is hers.
    await say(ANA, "and the helicopters were so loud all day", 15_000);
    expect(await tick(15_000)).toMatchObject({ kind: "offAgenda", targetId: ANA });
  });

  it("what someone says under Karen's redirect is not a fresh tangent", async () => {
    const { engine, tick, say, talking, spoken, start } = room();
    await start();
    spoken(2_000);
    talking(ANA, 3_000);
    await say(ANA, WEATHER, 7_000);
    expect(await tick(15_000)).toMatchObject({ kind: "offAgenda" });
    await say(ANA, "and the beach was packed, the weather is just too hot for me", 16_000);
    expect(engine.snapshot().episodes).toHaveLength(1);
    spoken(20_000);
    expect(engine.snapshot().episodes).toHaveLength(0);
  });

  it("talking to Karen is not drifting, and her answer is ready the moment she finishes", async () => {
    const { engine, prompts, classified, tick, say, talking, spoken, start } = room((user) =>
      user.includes("recognize") ? "Yes, Marc, I hear you." : null,
    );
    await start();
    spoken(2_000);
    talking(ANA, 3_000);
    await say(ANA, WEATHER, 7_000);
    expect(await tick(15_000)).toMatchObject({ kind: "offAgenda" }); // Karen is speaking to Ana
    talking(MARC, 15_500);
    await say(MARC, "This is not Ana, Karen. Can you recognize a different person?", 19_000);
    expect(classified).toHaveLength(1); // only Ana's tangent
    expect(await tick(19_000)).toBeNull(); // still speaking
    expect(prompts.at(-1)).toContain("recognize"); // ...but the answer is already written
    const composed = prompts.length;
    spoken(21_000);
    const answer = await tick(21_000);
    expect(answer).toMatchObject({ kind: "addressed", targetId: MARC });
    expect(prompts).toHaveLength(composed);
    expect(engine.history.at(-1)).toMatchObject({ line: "Yes, Marc, I hear you.", source: "cache" });
  });

  it("'Karen?' then 'Are you still here, Karen?' is one question, answered once", async () => {
    const { engine, tick, say } = room();
    await say(VIT, "Karen?", 1_000);
    expect(await tick(1_000)).toBeNull();
    await say(VIT, "Are you still here, Karen?", 3_000);
    expect((await tick(3_000))?.vars.request).toBe("Are you still here?");
    for (let t = 3_250; t <= 12_000; t += 250) expect(await tick(t)).toBeNull();
    expect(engine.history.filter((h) => h.kind === "addressed")).toHaveLength(1);
  });

  it("once a tangent is parked, later lines are told to leave it alone", async () => {
    const { prompts, tick, say, talking, spoken, start } = room();
    await start();
    spoken(2_000);
    talking(ANA, 3_000);
    await say(ANA, WEATHER, 7_000);
    expect(await tick(15_000)).toMatchObject({ kind: "offAgenda" });
    // The redirect itself is about the tangent: no "leave it alone" there.
    expect(prompts.find((p) => p.includes("has drifted off the agenda"))).not.toContain("Already parked");
    spoken(17_000);
    await say(VIT, "Karen, where are we?", 30_000);
    await tick(30_000);
    expect(prompts.at(-1)).toMatch(/Already parked for later: \w+ on the weather\. That is dealt with/);
  });

  it("someone who comes in mid-meeting is welcomed at the next pause, and only once", async () => {
    const { engine, tick, say, talking, quiet, spoken, start } = room();
    const everyone = (extra: Array<{ discordId: string; name: string }> = []) => [
      { discordId: VIT, name: "Vitaly" },
      { discordId: ANA, name: "Ana" },
      { discordId: MARC, name: "Marc" },
      ...extra,
    ];
    const LEO = { discordId: "100000000000000009", name: "Leo" };
    await start();
    spoken(2_000);
    // A mute toggle re-sends the same list: nobody arrived.
    engine.handle({ type: "participants", participants: everyone(), atMs: 3_000 });
    expect(engine.snapshot().arrivals).toEqual([]);
    engine.handle({ type: "participants", participants: everyone([LEO]), atMs: 10_000 });
    talking(ANA, 10_500);
    await say(ANA, "Status is fine, payments slipped a week.", 11_000);
    quiet(ANA, 11_000);
    expect(await tick(14_000)).toBeNull(); // Ana only just stopped
    const welcome = await tick(15_500);
    expect(welcome).toMatchObject({ kind: "newcomer", addresseeId: LEO.discordId, vars: { names: "Leo" } });
    spoken(18_000);
    engine.handle({ type: "participants", participants: everyone(), atMs: 20_000 });
    engine.handle({ type: "participants", participants: everyone([LEO]), atMs: 25_000 });
    for (let t = 25_250; t <= 40_000; t += 250) expect((await tick(t))?.kind).not.toBe("newcomer");
  });

  it("a newcomer's own hello does not break the quiet: 3 s before they join and 1 s after is enough", async () => {
    // 2026-09-19: Vitaly joined, said "Hey, can you hear me?" on an open mic that never left a
    // 4 s gap, and was never greeted.
    const { engine, tick, say, talking, spoken, start } = room();
    const LEO = { discordId: "100000000000000009", name: "Leo" };
    const everyone = [VIT, ANA, MARC].map((id, i) => ({ discordId: id, name: ["Vitaly", "Ana", "Marc"][i]! }));
    await start();
    spoken(2_000);
    engine.handle({ type: "participants", participants: [...everyone, LEO], atMs: 5_000 });
    talking(LEO.discordId, 5_200);
    await say(LEO.discordId, "Hey. Hey. How's it going? Can you hear me?", 5_800);
    expect(await tick(5_750)).toBeNull(); // the room has been quiet 3.75 s
    expect(await tick(6_000)).toMatchObject({ kind: "newcomer", addresseeId: LEO.discordId });
  });

  it("no welcome for someone who has joined the discussion by themselves, or who came before the start", async () => {
    const { engine, tick, say, spoken, start } = room();
    const LEO = { discordId: "100000000000000009", name: "Leo" };
    const everyone = [VIT, ANA, MARC].map((id, i) => ({ discordId: id, name: ["Vitaly", "Ana", "Marc"][i]! }));
    engine.handle({ type: "participants", participants: [...everyone, LEO], atMs: 500 }); // lobby
    await start();
    spoken(2_000);
    expect(engine.snapshot().arrivals).toEqual([]);
    const MIA = { discordId: "100000000000000010", name: "Mia" };
    engine.handle({ type: "participants", participants: [...everyone, LEO, MIA], atMs: 2_500 });
    await say(MIA.discordId, "Hi all, sorry I'm late. On status: payments slipped a week because the vendor missed the sandbox, and push is still on track.", 3_000);
    expect(engine.snapshot().arrivals).toEqual([]);
    for (let t = 3_250; t <= 30_000; t += 250) expect((await tick(t))?.kind).not.toBe("newcomer");
  });

  it("after a floor handover the talker's earlier minutes do not hand the floor over again", async () => {
    // 2026-09-19: floorHog asked Artem five times in two minutes while Vitaly's first stretch
    // still filled the window.
    const { tick, talking, spoken, start } = room();
    await start();
    spoken(2_000);
    talking(VIT, 3_000);
    let first: number | null = null;
    for (let t = 3_250; t <= 60_000 && first === null; t += 250) if ((await tick(t))?.kind === "floorHog") first = t;
    expect(first).not.toBeNull();
    spoken(first! + 2_000);
    const again: number[] = [];
    for (let t = first! + 2_250; t <= first! + 120_000; t += 250) {
      const iv = await tick(t);
      if (iv) spoken(t + 2_000);
      if (iv?.kind === "floorHog") again.push(t);
    }
    // Only once they have held most of the floor for softHandoverSeconds more.
    expect(again[0]! - first!).toBeGreaterThanOrEqual(45_000);
  });

  it.each([
    ["soft", { priority: false, quietMs: 700, maxWaitMs: 15_000 }, { softHandoverSeconds: 45, hardHandoverSeconds: 90 }],
    // Hard at the same threshold as soft: the first handover already cuts in.
    ["hard", { priority: true, quietMs: 700, maxWaitMs: 0 }, { softHandoverSeconds: 45, hardHandoverSeconds: 45 }],
  ])("a %s floor handover waits for a pause, or cuts in", async (_name, gate, policy) => {
    const { tick, talking, spoken, start, sent } = room(undefined, policy);
    await start();
    spoken(2_000);
    talking(VIT, 3_000);
    let hog = false;
    for (let t = 3_250; t <= 60_000 && !hog; t += 250) hog = (await tick(t))?.kind === "floorHog";
    expect(hog).toBe(true);
    expect(sent.findLast((f) => f.type === "speak")).toMatchObject(gate);
  });

  it("\"Karen, next topic\" moves on at once, and past the last topic wraps up", async () => {
    const { engine, tick, say, spoken, start } = room();
    await start();
    spoken(2_000);
    // Asking about the next topic is not asking to go there.
    await say(ANA, "Karen, what's the next topic?", 5_000);
    expect(await tick(5_000)).toMatchObject({ kind: "addressed" });
    spoken(7_000);
    expect(engine.view().topic?.index).toBe(0);

    await say(ANA, "Karen, I'm done, let's move on to the next topic.", 10_000);
    expect(await tick(10_000)).toMatchObject({ kind: "nextTopic", targetId: ANA, vars: { nextTopicTitle: "The date" } });
    expect(engine.view().topic).toMatchObject({ index: 1, title: "The date" });
    spoken(12_000);

    await say(VIT, "Karen, next topic please.", 20_000);
    expect(await tick(20_000)).toMatchObject({ kind: "nextTopic" });
    spoken(22_000);
    await say(VIT, "Karen, can we move on?", 30_000);
    expect(await tick(30_000)).toMatchObject({ kind: "wrapUp" });
    expect(engine.view()).toMatchObject({ phase: "finished", agendaFinished: true });
  });

  it("untimed, \"next topic\" goes to the next one not yet discussed", async () => {
    const { engine, tick, say, spoken, start } = room(undefined, { timed: false });
    await start();
    spoken(2_000);
    await say(ANA, "Karen, next topic.", 5_000);
    expect(await tick(5_000)).toMatchObject({ kind: "nextTopic", vars: { nextTopicTitle: "The date" } });
    spoken(7_000);
    await say(ANA, "Karen, next topic.", 10_000);
    expect(await tick(10_000)).toMatchObject({ kind: "nextTopic", vars: { nextTopicTitle: "Blocker owners" } });
    spoken(12_000);
    // Everything has been discussed: "next" ends the meeting.
    await say(ANA, "Karen, next topic.", 20_000);
    expect(await tick(20_000)).toMatchObject({ kind: "wrapUp" });
  });

  it("a line past compose.maxWords is asked for once more, shorter", async () => {
    const long = "Thanks for the weather report, Artem, saved that for the small talk folder. Now, back to the real debate: what does a dog do that no cat could?";
    const { prompts, say, tick, lines } = room((user) => (user.includes("Too long") ? "Artem, weather parked. What can a dog do that no cat could?" : long));
    await say(VIT, "Karen, tell us something.", 1_000);
    await tick(1_000);
    expect(prompts[1]).toMatch(/is 28 words\. Say the same thing in at most\s+22 words/);
    expect(lines()).toEqual(["Artem, weather parked. What can a dog do that no cat could?"]);
  });
});
