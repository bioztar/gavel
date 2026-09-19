/**
 * The chair's loop, minus any I/O choices: frames in, a tick on a clock, interventions out.
 *
 * main.ts runs it against ears and Nebius; replay.ts runs it against a recorded meeting, a
 * fake clock and stubs. Everything it needs from the outside world is a constructor argument.
 */
import { randomUUID } from "node:crypto";
import type { Config, InterventionKind } from "./config";
import { type Agenda, type Attendee, mergePolicy } from "./contract/agenda";
import type { EarsFrame, Participant } from "./contract/frames";
import { ContextBlock } from "./chair/context";
import type { Llm, Usage } from "./chair/llm";
import { STREAM_RATE, type Tts } from "./chair/tts";
import type { Memory, Store } from "./ears/store";
import type { Wire } from "./ears/wire";
import { log } from "./log";
import type { Intervention, PersonView, Redirect, Snapshot } from "./policy/snapshot";
import { evaluate, redirectFor } from "./policy/triggers";
import { type Classification, RelevanceTracker } from "./state/relevance";
import { TalkLedger } from "./state/talk";
import { render } from "./template";

// chair-video is a separate package with no other consumer wired in yet
// (mission scope is this one hook, nothing else in packages/brain) — reading
// the env var directly here, rather than through ./config, keeps main.ts and
// replay.ts untouched. Unset means no stage: the idle-loop/lip-sync path in
// chair-video keeps working either way, this is additive.
const CHAIR_VIDEO_URL = process.env.CHAIR_VIDEO_URL?.trim() || null;

// Fire-and-forget: the projector stage is cosmetic next to actually being
// heard in the Discord call, so a slow or down chair-video must never delay
// or break the wire.send() below it. 2s is generous for a same-network
// hackathon box; anything slower isn't worth waiting on.
function pushToStage(audio: Buffer, format: string, personaId: string): void {
  if (!CHAIR_VIDEO_URL) return;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 2000);
  fetch(`${CHAIR_VIDEO_URL}/director/speak`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ audioBase64: audio.toString("base64"), format, persona: personaId }),
    signal: controller.signal,
  })
    .catch((err: unknown) => log.warn("stage.push_failed", { error: String(err) }))
    .finally(() => clearTimeout(timeoutId));
}

export type MeetingPhase = "idle" | "gathering" | "active" | "finished";

export interface EngineDeps {
  config: () => Config;
  clock: () => number;
  wire: Wire;
  store: Store;
  llm: Llm;
  tts: Tts;
  /** Used when ears' session.started carries no agenda. */
  fallbackAgenda: Agenda | null;
  /** How an intervention is carried out. Default: directly; main.ts routes it through the Mastra workflow. */
  runner?: (engine: Engine, iv: Intervention) => Promise<unknown>;
  /** Called for every model call (tokens, latency), after cost is computed. */
  onUsage?: (u: Usage & { costUsd: number }) => void;
}

export interface Composed {
  line: string;
  source: "llm" | "template" | "cache";
  composeMs: number;
}

interface Precomposed {
  at: number;
  promise: Promise<string | null>;
}

export class Engine {
  sessionId: string | null = null;
  agenda: Agenda | null = null;
  phase: MeetingPhase = "idle";
  private title: string | null = null;
  private meetingContext: string | null = null;
  private people = new Map<string, Participant>();
  private topicIndex = 0;
  private agendaCompleted = false;
  private topicStartedAt = 0;
  private sessionStartedAt = 0;
  private ledger: TalkLedger;
  private relevance: RelevanceTracker;
  private context = new ContextBlock();

  private pending: { utteranceId: string; at: number } | null = null;
  private composing = false;
  private chairLastSpokeAt = 0;
  private lastInterventionAt: number | null = null;
  private redirect: Redirect | null = null;
  private escalatedAt: Record<string, number> = {};
  private lastPromptedId: string | null = null;
  private asked: Record<string, string[]> = {};
  private parked: Array<{ name: string; summary: string }> = [];
  private carried: Memory[] = [];
  private muted = new Map<string, number>();
  private precomposed = new Map<string, Precomposed>();
  private directQueue: Intervention[] = [];
  private handledUtterances = new Set<string>();
  /** People who said just "Karen," — their next words are the request. */
  private awaitingRequest = new Map<string, number>();
  /** Each person's recent final transcripts, for context when they address Karen. */
  private recentWords = new Map<string, Array<{ at: number; text: string }>>();
  private facts: string[] = [];
  private decisions: string[] = [];
  private openItems: string[] = [];
  private inFlight = new Set<Promise<unknown>>();
  readonly history: Array<Intervention & { at: number; line?: string; source?: string }> = [];
  readonly usage = { calls: 0, inputTokens: 0, outputTokens: 0, costUsd: 0 };

  constructor(private deps: EngineDeps) {
    this.ledger = new TalkLedger(() => this.topic()?.id ?? null);
    this.relevance = new RelevanceTracker(() => this.cfg.policy.relevance);
  }

  private get cfg(): Config {
    return this.deps.config();
  }

  private now(): number {
    return this.deps.clock();
  }

  // --- frames in -------------------------------------------------------------------------

  handle(frame: EarsFrame): void {
    const at = frame.atMs ?? this.now();
    switch (frame.type) {
      case "ready":
      case "participants":
        this.people = new Map(frame.participants.map((p) => [p.discordId, p]));
        if (frame.type === "ready" && !this.agenda) this.startSession(null, null, this.deps.fallbackAgenda, at);
        break;
      case "session.started":
        this.meetingContext = frame.context ?? null;
        this.startSession(frame.sessionId, frame.title ?? null, frame.agenda ?? this.deps.fallbackAgenda, at);
        break;
      case "session.ended":
        if (frame.sessionId === this.sessionId) {
          log.info("session.ended", { sessionId: frame.sessionId });
          this.agenda = null;
          this.phase = this.agendaCompleted ? "finished" : "idle";
        }
        break;
      case "speaking.start":
        this.ledger.start(frame.discordId, at);
        // Someone else taking the floor means the redirect worked.
        if (this.redirect && this.redirect.targetId !== frame.discordId) this.redirect = null;
        break;
      case "speaking.end":
        this.ledger.end(frame.discordId, at);
        break;
      case "transcript":
        this.maybeAddressKaren(frame.discordId, frame.text, at, frame.utteranceId, frame.final);
        this.relevance.addTranscript(frame.discordId, frame.text);
        this.maybeClassify(frame.discordId);
        break;
      case "spoken":
        if (this.pending?.utteranceId === frame.utteranceId) this.chairDone(at);
        break;
      case "moderation":
        if (frame.action === "muted") this.muted.set(frame.discordId, frame.until ?? at);
        if (frame.action === "unmuted") this.muted.delete(frame.discordId);
        log.info("moderation", { action: frame.action, who: this.nameOf(frame.discordId), error: frame.error });
        break;
      default:
        break;
    }
  }

  private startSession(sessionId: string | null, title: string | null, agenda: Agenda | null, at: number): void {
    this.sessionId = sessionId;
    this.title = title;
    this.agenda = this.withImplicitTopic(agenda, title);
    this.phase = this.agenda ? "gathering" : "idle";
    this.topicIndex = 0;
    this.agendaCompleted = false;
    this.topicStartedAt = at;
    this.sessionStartedAt = at;
    this.chairLastSpokeAt = 0;
    this.lastInterventionAt = null;
    this.redirect = null;
    this.escalatedAt = {};
    this.lastPromptedId = null;
    this.asked = {};
    this.parked = [];
    this.carried = [];
    this.precomposed.clear();
    this.directQueue = [];
    this.handledUtterances.clear();
    this.awaitingRequest.clear();
    this.recentWords.clear();
    this.facts = [];
    this.decisions = [];
    this.openItems = [];
    this.ledger.reset();
    this.relevance.resetAll();
    log.info("session.started", {
      sessionId,
      title,
      topics: agenda?.topics.map((t) => t.title) ?? [],
      policy: this.policy(),
      phase: this.phase,
    });
    this.track(this.loadCarried());
  }

  /**
   * A meeting with a purpose but no topics runs as one topic made from that purpose
   * (config/prompts/chair.yaml → implicitTopic), so the chair still has something to hold
   * the room to. No budget: it never runs over.
   */
  private withImplicitTopic(agenda: Agenda | null, title: string | null): Agenda | null {
    if (!agenda || agenda.topics.length) return agenda;
    const purpose = agenda.purpose || this.meetingContext || title || "";
    if (!purpose && !title) {
      log.warn("agenda.empty", { reason: "no topics, no purpose, no title — the chair has nothing to steer by" });
      return agenda;
    }
    const tpl = this.cfg.chair.implicitTopic;
    const vars = { title: title || purpose, purpose, context: this.meetingContext ?? "" };
    const topic = {
      id: "main",
      title: render(tpl.title, vars),
      goal: render(tpl.goal, vars),
      budgetSeconds: 0,
      owner: null,
      mustHear: [],
      questions: tpl.questions.map((q) => render(q, vars)),
    };
    log.warn("agenda.no_topics", { using: topic.title, goal: topic.goal });
    return { ...agenda, topics: [topic] };
  }

  /** Open memories for everyone expected or present — brought up at the wrap-up. */
  private async loadCarried(): Promise<void> {
    const ids = [...new Set([...this.people.keys(), ...(this.agenda?.attendees ?? []).map((a) => a.discordId)])];
    if (!ids.length) return;
    const open = await this.deps.store.listMemories({ discordIds: ids, status: "open" });
    this.carried = open.filter((m) => m.sessionId !== this.sessionId);
    if (this.carried.length) log.info("memory.carried", { items: this.carried.map((m) => `${m.name}: ${m.summary}`) });
  }

  // --- the clock ---------------------------------------------------------------------------

  /** One step of the loop. Returns the intervention it launched, if any. */
  tick(): Intervention | null {
    const now = this.now();
    const engine = this.cfg.policy.engine;
    if (this.pending && now - this.pending.at > engine.spokenTimeoutSeconds * 1000) {
      log.warn("chair.spoken_timeout", { utteranceId: this.pending.utteranceId });
      this.chairDone(now);
    }
    if (this.redirect && this.redirect.spokenAt !== null && now - this.redirect.spokenAt > engine.redirectExpirySeconds * 1000) {
      this.redirect = null;
    }
    // An episode ends when its speaker has been quiet for the whole grace period.
    const graceMs = this.policy().offAgendaGraceSeconds * 1000;
    for (const [id] of this.relevance.episodes()) {
      if (!this.ledger.holding(id, now, graceMs)) this.relevance.clear(id);
    }
    for (const id of this.people.keys()) this.maybeClassify(id);
    // "Karen," and then nothing: answer from what they said before it.
    const followUpMs = this.cfg.policy.addressed.followUpSeconds * 1000;
    for (const [id, since] of this.awaitingRequest) {
      if (now - since < followUpMs) continue;
      this.awaitingRequest.delete(id);
      this.onRequest(id, "", since);
    }
    this.ledger.prune(now, this.policy().floorWindowSeconds * 2000);

    if (this.directQueue.length && !this.pending && !this.composing) {
      const direct = this.directQueue.shift()!;
      this.launch(direct);
      return direct;
    }
    if (!this.agenda || this.phase !== "active") return null;
    const iv = evaluate(this.snapshot());
    if (iv) this.launch(iv);
    return iv;
  }

  /** Resolves when every in-flight model call and intervention has settled. */
  async idle(): Promise<void> {
    while (this.inFlight.size) await Promise.allSettled([...this.inFlight]);
  }

  private track<T>(p: Promise<T>): Promise<T> {
    this.inFlight.add(p);
    void p.finally(() => this.inFlight.delete(p)).catch(() => {});
    return p;
  }

  // --- the snapshot the policy sees ------------------------------------------------------------

  policy() {
    return mergePolicy(this.cfg.policy.defaults, this.agenda);
  }

  topic() {
    return this.agenda?.topics[this.topicIndex] ?? null;
  }

  private attendee(id: string): Attendee | undefined {
    return this.agenda?.attendees.find((a) => a.discordId === id);
  }

  private nameOf(id: string): string {
    return this.people.get(id)?.name ?? this.attendee(id)?.name ?? id;
  }

  snapshot(): Snapshot {
    const now = this.now();
    const cfg = this.cfg.policy;
    const policy = this.policy();
    const topic = this.topic();
    const gap = cfg.engine.floorGapMs;
    const windowMs = policy.floorWindowSeconds * 1000;
    const people: PersonView[] = [...this.people.values()].map((p) => {
      const talk = this.ledger.person(p.discordId, now, topic?.id ?? null, windowMs);
      return {
        id: p.discordId,
        name: p.name,
        role: this.attendee(p.discordId)?.role ?? "attendee",
        totalMs: talk.totalMs,
        topicMs: talk.topicMs,
        windowMs: talk.windowMs,
        holding: this.ledger.holding(p.discordId, now, gap) && !this.muted.has(p.discordId),
        holdingSince: this.ledger.holdingSince(p.discordId, now, gap),
      };
    });
    const recaps: Record<string, string> = {};
    for (const p of people) {
      const r = this.relevance.lastSummary(p.id);
      if (r) recaps[p.id] = r;
    }
    return {
      now,
      purpose: this.agenda?.purpose ?? "",
      policy,
      engine: cfg.engine,
      pick: cfg.pickSpeaker,
      topics: this.agenda?.topics ?? [],
      topicIndex: this.topicIndex,
      topic,
      topicStartedAt: this.topicStartedAt,
      people,
      chairBusy: this.pending !== null || this.composing,
      lastInterventionAt: this.lastInterventionAt,
      silenceMs: this.ledger.silenceMs(now, Math.max(this.topicStartedAt, this.chairLastSpokeAt, this.sessionStartedAt)),
      episodes: this.relevance.episodes().map(([id, episode]) => ({ id, episode })),
      redirect: this.redirect,
      escalatedAt: this.escalatedAt,
      lastSpeakerId: this.ledger.lastSpeaker(),
      lastPromptedId: this.lastPromptedId,
      asked: this.asked,
      recaps,
      parked: this.parked,
      carried: this.carried.map((m) => ({ name: m.name ?? this.nameOf(m.discordId), summary: m.summary })),
      fallbackQuestion: this.cfg.chair.fallbackQuestion,
    };
  }

  // --- off-agenda classification ------------------------------------------------------------

  private maybeClassify(id: string): void {
    const now = this.now();
    if (!this.agenda || !this.topic() || this.phase !== "active") return;
    // Nothing could act on a verdict while the chair is mid-sentence.
    if (this.pending) return;
    const since = this.ledger.holdingSince(id, now, this.cfg.policy.engine.floorGapMs);
    if (since === null || !this.relevance.due(id, now, now - since)) return;
    const topic = this.topic();
    const { key, cached } = this.relevance.begin(id, now, topic?.id ?? null);
    if (cached) {
      this.afterVerdict(id, key, cached, true);
      return;
    }
    const agenda = this.agenda;
    const window = this.relevance.window(id);
    const req = {
      system: `${this.cfg.relevance.system}\n${this.contextText()}`,
      user: render(this.cfg.relevance.user, { topicId: topic?.id, name: this.nameOf(id), window }),
      window,
      topicId: topic?.id ?? null,
      topics: agenda.topics,
    };
    this.track(
      this.deps.llm
        .classify(req)
        .catch((err) => {
          log.warn("relevance.failed", { error: String(err) });
          return null;
        })
        .then((result) => this.afterVerdict(id, key, result, false)),
    );
  }

  private afterVerdict(id: string, key: string, raw: Classification | null, cached: boolean): void {
    const result = raw && this.checkVerdict(raw);
    if (result) this.absorbInsights(result);
    const change = this.relevance.finish(id, this.now(), key, result);
    if (result) log.debug("relevance", { who: this.nameOf(id), ...result, cached });
    if (change === "opened") {
      const episode = this.relevance.episode(id)!;
      log.info("offagenda.opened", { who: this.nameOf(id), verdict: episode.verdict, summary: episode.summary });
      if (this.cfg.policy.compose.precompose) {
        const person = this.snapshot().people.find((p) => p.id === id);
        if (person) this.precompose(redirectFor(this.snapshot(), person, episode));
      }
    } else if (change === "closed") {
      log.info("offagenda.closed", { who: this.nameOf(id) });
    }
  }

  /**
   * "Another agenda item" only counts if it is still ahead of us. Jumping back to a finished
   * topic, or to an id the agenda does not have, is drifting off the agenda.
   */
  private checkVerdict(c: Classification): Classification {
    if (c.verdict !== "otherTopic") return c;
    const at = this.agenda?.topics.findIndex((t) => t.id === c.topicId) ?? -1;
    return at > this.topicIndex ? c : { ...c, verdict: "offAgenda", topicId: null };
  }

  // --- interventions ----------------------------------------------------------------------------

  private launch(iv: Intervention): void {
    const now = this.now();
    this.composing = true;
    this.lastInterventionAt = now;
    if (iv.question && iv.topicId) (this.asked[iv.topicId] ??= []).push(iv.question);
    if (iv.addresseeId) this.lastPromptedId = iv.addresseeId;
    if (iv.trigger === "escalate" && iv.targetId) {
      this.escalatedAt[iv.targetId] = now;
      this.redirect = null;
    } else if (iv.redirects && iv.targetId) {
      this.redirect = { targetId: iv.targetId, topicId: iv.topicId, spokenAt: null };
    }
    if (iv.trigger === "offAgenda") {
      if (iv.targetId) this.relevance.clear(iv.targetId);
      for (const p of iv.parks ?? []) this.relevance.clear(p.discordId);
    }
    const entry = { ...iv, at: now };
    this.history.push(entry);
    log.info("chair.intervene", {
      kind: iv.kind,
      target: iv.targetId && this.nameOf(iv.targetId),
      addressee: iv.addresseeId && this.nameOf(iv.addresseeId),
      topic: iv.topicId,
      actions: iv.actions,
    });
    const run = this.deps.runner ? this.deps.runner(this, iv) : this.carryOut(iv);
    this.track(
      run
        .catch((err) => log.error("chair.intervention_failed", { kind: iv.kind, error: String(err) }))
        .finally(() => {
          this.composing = false;
        }),
    );
  }

  /** The whole intervention, in order. The Mastra workflow runs the same steps one by one. */
  async carryOut(iv: Intervention): Promise<Composed> {
    const composed = await this.compose(iv);
    const done = await this.act(iv, composed.line);
    this.record(iv, composed, done.ttsMs);
    return composed;
  }

  private lineKey(iv: Pick<Intervention, "kind" | "targetId" | "addresseeId" | "topicId" | "vars">): string {
    // Direct questions from the same person must not reuse the answer to their previous
    // question. Policy interventions intentionally keep the shorter reusable key.
    const direct = iv.kind === "addressed" ? `:${iv.vars.request ?? ""}` : "";
    return `${iv.kind}:${iv.targetId ?? iv.addresseeId ?? "-"}:${iv.topicId ?? "-"}${direct}`;
  }

  private precompose(iv: Intervention): void {
    const key = this.lineKey(iv);
    if (this.precomposed.has(key)) return;
    const promise = this.generate(iv);
    this.precomposed.set(key, { at: this.now(), promise });
    this.track(promise);
    log.debug("chair.precompose", { key });
  }

  /**
   * The line: a pre-composed or recent one if we have it, else the model, else — only when
   * policy.yaml's compose.templateFallback is on, or there is no model — the template. An
   * empty line means the chair says nothing this time.
   */
  async compose(iv: Intervention): Promise<Composed> {
    const started = performance.now();
    const profile = this.cfg.models.profiles.normal;
    // Someone asked Karen directly and is waiting: a real answer a little later beats a
    // canned one now.
    const direct = iv.trigger === "addressed" || iv.trigger === "meetingStart";
    const timeoutMs = direct ? (profile.directTimeoutMs ?? profile.timeoutMs) : profile.timeoutMs;
    const key = this.lineKey(iv);
    const ready = direct ? undefined : this.precomposed.get(key);
    const fresh = ready && this.now() - ready.at < this.cfg.policy.compose.lineCacheSeconds * 1000;
    let line: string | null = null;
    let source: Composed["source"] = "llm";
    if (fresh) {
      line = await withTimeout(ready.promise, timeoutMs);
      source = "cache";
    }
    if (!line) {
      source = "llm";
      const promise = this.generate(iv, timeoutMs);
      if (!direct) this.precomposed.set(key, { at: this.now(), promise });
      line = await withTimeout(promise, timeoutMs);
    }
    if (!line && (this.cfg.policy.compose.templateFallback || !this.deps.llm.composes)) {
      line = this.template(iv);
      source = "template";
    }
    if (!line) log.warn("chair.no_line", { kind: iv.kind, reason: "model gave nothing in time; template fallback is off" });
    return { line: line ?? "", source, composeMs: Math.round(performance.now() - started) };
  }

  private async generate(iv: Intervention, timeoutMs?: number): Promise<string | null> {
    const kind = this.cfg.chair.kinds[iv.kind];
    // Only an explicit question to Karen needs the live notes. Supplying them to routine
    // redirects and wrap-ups tempts smaller models to improvise extra commitments.
    const enrichedVars = iv.kind === "addressed"
      ? {
          ...iv.vars,
          knownFacts: this.facts.join("; "),
          knownDecisions: this.decisions.join("; "),
          knownOpenItems: this.openItems.join("; "),
          yourRecentLines: this.recentChairLines(3),
        }
      : iv.vars;
    const user = render(this.cfg.chair.user, {
      instruction: render(kind.instruction, enrichedVars),
      examples: kind.examples.map((e) => `- ${e}`).join("\n"),
      // Every fact is listed, empty ones as "(none)": a missing fact invites the model to invent it.
      facts: Object.entries(enrichedVars)
        .filter(([k]) => k !== "quote")
        .map(([k, v]) => `${k}: ${v?.trim() || "(none)"}`)
        .join("\n"),
    });
    try {
      const text = await this.deps.llm.compose({ system: `${this.cfg.chair.system}\n${this.contextText()}`, user, timeoutMs });
      return text ? clean(text) : null;
    } catch (err) {
      log.warn("chair.compose_failed", { kind: iv.kind, error: String(err) });
      return null;
    }
  }

  /**
   * The templates whose placeholders all have values, rotating by how many times this kind
   * has already fired this session — so a persona's four-plus variants don't repeat inside
   * one meeting. Deterministic: same history, same pick. Falls back to the last template
   * (persona-agnostic) when none qualify.
   */
  template(iv: Intervention): string {
    const templates = this.cfg.chair.kinds[iv.kind as InterventionKind].templates;
    const filled = templates.filter((t) =>
      [...t.matchAll(/\{\{\s*(\w+)\s*\}\}/g)].every((m) => (iv.vars[m[1]!] ?? "").trim() !== ""),
    );
    const pool = filled.length ? filled : [templates[templates.length - 1]!];
    const seenBefore = this.history.filter((h) => h.kind === iv.kind).length - 1;
    // Spoken aloud, people are addressed by first name ("Artem", not "Artem Shambalev").
    const vars = { ...iv.vars, name: firstName(iv.vars.name), addresseeName: firstName(iv.vars.addresseeName) };
    return render(pool[seenBefore % pool.length]!, vars);
  }

  /** Park, speak, mute, advance — whichever the intervention calls for, in that order. */
  async act(iv: Intervention, line: string): Promise<{ ttsMs?: number; utteranceId?: string }> {
    if (iv.actions.includes("park") && iv.park) await this.park(iv.park);
    if (iv.actions.includes("park")) for (const p of iv.parks ?? []) await this.park(p);
    let out: { ttsMs?: number; utteranceId?: string } = {};
    if (iv.actions.includes("speak") && line) out = await this.speak(line, iv.priority);
    if (iv.actions.includes("mute") && iv.targetId && iv.muteSeconds) {
      this.mute(iv.targetId, iv.muteSeconds, `gavel: ${iv.kind}`);
    }
    if (iv.actions.includes("advance")) this.advanceTopic();
    if (iv.actions.includes("start")) this.activateMeeting();
    const entry = this.history[this.history.length - 1];
    if (entry) entry.line = line;
    return out;
  }

  record(iv: Intervention, composed: Composed, ttsMs?: number): void {
    const entry = this.history[this.history.length - 1];
    if (entry) entry.source = composed.source;
    log.info("chair.said", { kind: iv.kind, source: composed.source, composeMs: composed.composeMs, ttsMs, line: composed.line });
    this.deps.store.intervention({
      sessionId: this.sessionId,
      kind: iv.kind,
      targetId: iv.targetId,
      addresseeId: iv.addresseeId,
      topicId: iv.topicId,
      line: composed.line,
      source: composed.source,
      actions: iv.actions,
      composeMs: composed.composeMs,
      ttsMs,
    });
  }

  // --- the chair's hands (also exposed as Mastra tools) -------------------------------------------

  async park(p: { discordId: string; name: string; summary: string; quote?: string; topicId?: string | null }): Promise<Memory | null> {
    this.parked.push({ name: p.name, summary: p.summary });
    const memory = await this.deps.store.addMemory({
      discordId: p.discordId,
      name: p.name,
      kind: "parked",
      summary: p.summary,
      quote: p.quote,
      topicId: p.topicId,
      sessionId: this.sessionId,
    });
    log.info("memory.parked", { who: p.name, summary: p.summary, id: memory?.id });
    return memory;
  }

  async speak(text: string, priority: boolean): Promise<{ ttsMs?: number; utteranceId?: string }> {
    const utteranceId = randomUUID();
    this.pending = { utteranceId, at: this.now() };
    if (this.cfg.models.tts.transport === "stream" && this.deps.tts.stream) return this.speakStreamed(utteranceId, text, priority);
    try {
      const speech = await this.deps.tts.synthesize(text);
      pushToStage(speech.audio, speech.format, this.cfg.persona.id);
      const sent = this.deps.wire.send({
        type: "speak",
        utteranceId,
        audio: speech.audio.toString("base64"),
        text,
        format: speech.format,
        priority,
      });
      if (!sent) {
        log.warn("chair.not_connected", { text });
        this.chairDone(this.now());
        return { ttsMs: speech.latencyMs };
      }
      // Anchor the pending wait at send time, not at the TTS request.
      this.pending = { utteranceId, at: this.now() };
      return { ttsMs: speech.latencyMs, utteranceId };
    } catch (err) {
      log.warn("chair.tts_failed", { error: String(err) });
      this.chairDone(this.now());
      return {};
    }
  }

  /**
   * ears starts playing (and queues, or cuts in for a priority line) on `speak.start`, then
   * plays each chunk as it lands — so the room hears the first words ~0.2 s after the text
   * reaches TTS instead of after the whole clip is synthesized.
   */
  private async speakStreamed(utteranceId: string, text: string, priority: boolean): Promise<{ ttsMs?: number; utteranceId?: string }> {
    const wire = this.deps.wire;
    const started = wire.send({ type: "speak.start", utteranceId, text, format: "pcm_s16le", sampleRate: STREAM_RATE, channels: 1, priority });
    if (!started) {
      log.warn("chair.not_connected", { text });
      this.chairDone(this.now());
      return {};
    }
    this.pending = { utteranceId, at: this.now() };
    try {
      const done = await this.deps.tts.stream!(text, (pcm) => {
        wire.send({ type: "speak.chunk", utteranceId, audio: pcm.toString("base64") });
      });
      wire.send({ type: "speak.end", utteranceId });
      return { ttsMs: done.firstAudioMs, utteranceId };
    } catch (err) {
      log.warn("chair.tts_failed", { error: String(err) });
      // ears finishes whatever arrived and reports `spoken` as usual.
      wire.send({ type: "speak.end", utteranceId, error: String(err).slice(0, 200) });
      return { utteranceId };
    }
  }

  mute(discordId: string, seconds: number, reason?: string): boolean {
    return this.deps.wire.send({ type: "mute", discordId, seconds, reason });
  }

  unmute(discordId: string): boolean {
    return this.deps.wire.send({ type: "unmute", discordId });
  }

  stop(): boolean {
    return this.deps.wire.send({ type: "stop" });
  }

  advanceTopic(): void {
    const now = this.now();
    this.ledger.splitAt(now);
    this.topicIndex += 1;
    this.topicStartedAt = now;
    this.relevance.resetAll();
    this.redirect = null;
    this.lastPromptedId = null;
    const topic = this.topic();
    if (!topic) {
      this.agendaCompleted = true;
      this.phase = "finished";
    }
    log.info("topic.advanced", { to: topic?.title ?? "(agenda done)" });
  }

  async recall(discordIds?: string[]): Promise<Memory[]> {
    return this.deps.store.listMemories({ discordIds, status: "open" });
  }

  async resolveMemory(id: string): Promise<Memory | null> {
    return this.deps.store.setMemoryStatus(id, "resolved");
  }

  private chairDone(at: number): void {
    this.pending = null;
    this.chairLastSpokeAt = at;
    if (this.redirect && this.redirect.spokenAt === null) this.redirect.spokenAt = at;
  }

  private activateMeeting(): void {
    const now = this.now();
    this.phase = "active";
    this.topicStartedAt = now;
    this.sessionStartedAt = now;
    // Lobby chatter must not count toward meeting talk time or relevance.
    this.ledger.reset();
    this.relevance.resetAll();
    log.info("meeting.started", { sessionId: this.sessionId, topic: this.topic()?.title });
  }

  private maybeAddressKaren(id: string, text: string, at: number, utteranceId?: string, final?: boolean): void {
    if (final === false) return;
    const key = utteranceId ?? `${id}:${text.toLowerCase().replace(/\s+/g, " ").trim()}`;
    if (this.handledUtterances.has(key)) return;
    this.handledUtterances.add(key);

    if (KAREN.test(text)) {
      // Her name can come anywhere: "Karen, what's the agenda?", "Let's start, Karen."
      const request = withoutName(text);
      if (/[\p{L}\p{N}]/u.test(request)) this.onRequest(id, request, at);
      else this.awaitingRequest.set(id, at);
    } else if (this.awaitingRequest.has(id)) {
      this.awaitingRequest.delete(id);
      this.onRequest(id, text.trim(), at);
    }
    this.remember(id, text, at);
  }

  private remember(id: string, text: string, at: number): void {
    const keepMs = this.cfg.policy.addressed.contextSeconds * 1000;
    const list = (this.recentWords.get(id) ?? []).filter((w) => at - w.at <= keepMs);
    list.push({ at, text: text.trim() });
    this.recentWords.set(id, list.slice(-4));
  }

  private earlierWords(id: string, at: number): string {
    const keepMs = this.cfg.policy.addressed.contextSeconds * 1000;
    return (this.recentWords.get(id) ?? [])
      .filter((w) => at - w.at <= keepMs && !KAREN.test(w.text))
      .map((w) => w.text)
      .join(" ");
  }

  private onRequest(id: string, request: string, at: number): void {
    const who = this.nameOf(id);
    const wantsStart = START.test(request);

    if (wantsStart && this.phase === "gathering") {
      const missing = this.missingAttendees();
      if (missing.length) {
        this.directQueue.push({
          trigger: "meetingStart",
          kind: "waitingForPeople",
          topicId: this.topic()?.id ?? null,
          targetId: id,
          vars: { name: who, missingNames: joinNames(missing), topicTitle: this.topic()?.title ?? "" },
          actions: ["speak"],
          priority: false,
        });
        return;
      }

      const starter = this.startingPerson(id);
      const topic = this.topic();
      const question = topic?.questions[0] ?? render(this.cfg.chair.fallbackQuestion, {
        topicTitle: topic?.title ?? "the first topic",
        topicGoal: topic?.goal ?? "",
      });
      this.directQueue.push({
        trigger: "meetingStart",
        kind: "startMeeting",
        topicId: topic?.id ?? null,
        addresseeId: starter.id,
        vars: {
          name: who,
          agendaList: this.agendaList(),
          topicTitle: topic?.title ?? "",
          topicGoal: topic?.goal ?? "",
          addresseeName: starter.name,
          question,
          purpose: this.agenda?.purpose ?? "",
        },
        actions: ["speak", "start"],
        priority: false,
        question,
      });
      return;
    }

    this.directQueue.push({
      trigger: "addressed",
      kind: "addressed",
      topicId: this.topic()?.id ?? null,
      targetId: id,
      vars: {
        name: who,
        request: request || "(only your name)",
        earlierWords: this.earlierWords(id, at),
        meetingState: this.meetingState(),
        meetingTitle: this.title ?? "",
        purpose: this.agenda?.purpose ?? "",
        agendaList: this.agendaList(),
        topicTitle: this.phase === "active" ? (this.topic()?.title ?? "") : "",
      },
      actions: ["speak"],
      priority: false,
    });
  }

  /** "where we actually are, the date, and blocker owners" — the way it is said aloud. */
  private agendaList(): string {
    const titles = (this.agenda?.topics ?? []).map((t) => t.title);
    return titles.length ? joinNames(titles) : "";
  }

  /** Where the meeting is, in words the chair model cannot mistake for a topic. */
  private meetingState(): string {
    const topics = this.agenda?.topics ?? [];
    switch (this.phase) {
      case "gathering": {
        const missing = this.missingAttendees();
        const waiting = missing.length ? ` Still waiting for ${joinNames(missing)}.` : "";
        return `Not started yet; people are joining.${waiting}`;
      }
      case "active":
        return `In progress, on topic ${this.topicIndex + 1} of ${topics.length}: ${this.topic()?.title ?? ""}.`;
      case "finished":
        return "The agenda is finished.";
      default:
        return "No meeting is set up yet.";
    }
  }

  private recentChairLines(n: number): string {
    return this.history
      .filter((h) => h.line)
      .slice(-n)
      .map((h) => h.line)
      .join(" | ");
  }

  private missingAttendees(): string[] {
    const present = new Set(this.people.keys());
    return (this.agenda?.attendees ?? [])
      .filter((a) => a.discordId && !present.has(a.discordId))
      .map((a) => a.name);
  }

  private startingPerson(fallbackId: string): { id: string; name: string } {
    const topic = this.topic();
    const candidates = [topic?.owner, ...(topic?.mustHear ?? []), ...this.people.keys()].filter(Boolean) as string[];
    const id = candidates.find((candidate) => this.people.has(candidate)) ?? fallbackId;
    return { id, name: this.nameOf(id) };
  }

  private absorbInsights(result: Classification): void {
    addUnique(this.facts, result.facts);
    addUnique(this.decisions, result.decisions);
    addUnique(this.openItems, result.openItems);
  }

  // --- model usage ------------------------------------------------------------------------------

  /** Called by the LLM implementation after every model call. */
  recordUsage(u: Usage): void {
    const price = this.cfg.models.prices[u.model];
    const costUsd = price ? (u.inputTokens * price.input + u.outputTokens * price.output) / 1e6 : 0;
    this.usage.calls += 1;
    this.usage.inputTokens += u.inputTokens;
    this.usage.outputTokens += u.outputTokens;
    this.usage.costUsd += costUsd;
    this.deps.store.llmCall({ sessionId: this.sessionId, ...u, costUsd });
    this.deps.onUsage?.({ ...u, costUsd });
    log.debug("llm.call", { ...u, costUsd: Number(costUsd.toFixed(6)) });
  }

  private contextText(): string {
    const people = [...this.people.values()].map((p) => ({
      name: p.name,
      role: this.attendee(p.discordId)?.role ?? "attendee",
    }));
    return this.context.get(this.agenda, people, this.meetingContext);
  }

  // --- the stage's view ---------------------------------------------------------------------------

  view() {
    const s = this.snapshot();
    return {
      sessionId: this.sessionId,
      title: this.title,
      purpose: s.purpose,
      chairName: "Karen",
      phase: this.phase,
      readyToStart: this.phase === "gathering" && this.missingAttendees().length === 0,
      missingAttendees: this.missingAttendees(),
      agendaFinished: this.agendaCompleted,
      topic: s.topic && {
        index: s.topicIndex,
        id: s.topic.id,
        title: s.topic.title,
        budgetSeconds: s.topic.budgetSeconds,
        elapsedSeconds: Math.round((s.now - s.topicStartedAt) / 1000),
      },
      topics: s.topics.map((t, i) => ({ id: t.id, title: t.title, budgetSeconds: t.budgetSeconds, done: i < s.topicIndex })),
      people: s.people.map((p) => ({
        id: p.id,
        name: p.name,
        role: p.role,
        totalSeconds: Math.round(p.totalMs / 1000),
        topicSeconds: Math.round(p.topicMs / 1000),
        windowSeconds: Math.round(p.windowMs / 1000),
        speaking: p.holding,
        muted: this.muted.has(p.id),
        offAgenda: this.relevance.episode(p.id)?.summary ?? null,
      })),
      persona: { id: this.cfg.persona.id, displayName: this.cfg.persona.displayName },
      chairBusy: s.chairBusy,
      silenceSeconds: Math.round(s.silenceMs / 1000),
      parked: this.parked,
      carried: s.carried,
      understanding: {
        facts: [...this.facts],
        decisions: [...this.decisions],
        openItems: [...this.openItems],
        later: [...this.openItems, ...this.parked.map((p) => p.summary)],
        offTopics: [...this.parked],
      },
      interventions: this.history.slice(-20).map((h) => ({ at: h.at, kind: h.kind, line: h.line, source: h.source })),
      usage: { ...this.usage, costUsd: Number(this.usage.costUsd.toFixed(6)) },
      policy: s.policy,
    };
  }
}

function addUnique(target: string[], values: string[] | undefined): void {
  for (const raw of values ?? []) {
    const value = raw.trim();
    if (!value || target.some((x) => x.toLowerCase() === value.toLowerCase())) continue;
    target.push(value);
    if (target.length > 50) target.shift();
  }
}

const KAREN = /\bkaren\b/i;
const START = /\b(?:(?:start|begin|kick\s*off|open)\b.*\b(?:meeting|agenda|session|call)|let'?s\s+(?:start|begin|get\s+started|kick\s*off))\b/i;

/** "Let's start the meeting, please, Karen." → "Let's start the meeting, please." */
function withoutName(text: string): string {
  return text
    .replace(/,?\s*\bkaren\b\s*,?/gi, " ")
    .replace(/\s+([.,!?;:])/g, "$1")
    .replace(/^[\s.,!?;:-]+/, "")
    .replace(/\s+/g, " ")
    .trim();
}

function firstName(name: string | undefined): string | undefined {
  return name?.trim().split(/\s+/)[0];
}

function joinNames(names: string[]): string {
  if (names.length < 2) return names[0] ?? "everyone";
  if (names.length === 2) return `${names[0]} and ${names[1]}`;
  return `${names.slice(0, -1).join(", ")}, and ${names.at(-1)}`;
}

function clean(text: string): string {
  let line = text.replace(/\s+/g, " ").trim();
  if (/^["'“].*["'”]$/.test(line)) line = line.slice(1, -1).trim();
  return line.length > 320 ? `${line.slice(0, 317).replace(/\s\S*$/, "")}…` : line;
}

function withTimeout<T>(p: Promise<T | null>, ms: number): Promise<T | null> {
  return Promise.race([p, new Promise<null>((resolve) => setTimeout(() => resolve(null), ms))]);
}
