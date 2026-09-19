/**
 * ears is the one database. Memories, interventions and model usage go through its REST
 * API into the same Postgres as the transcripts. A store that is down costs rows, never the
 * meeting: every call here is bounded and swallows its failure.
 */
import { log } from "../log";

export interface Memory {
  id: string;
  discordId: string;
  name: string | null;
  kind: "parked" | "note";
  summary: string;
  quote: string | null;
  topicId: string | null;
  sessionId: string | null;
  status: "open" | "resolved";
  createdAt: string;
}

export interface NewMemory {
  discordId: string;
  name?: string;
  kind: "parked" | "note";
  summary: string;
  quote?: string;
  topicId?: string | null;
  sessionId?: string | null;
}

export interface InterventionRecord {
  sessionId: string | null;
  kind: string;
  targetId?: string;
  addresseeId?: string;
  topicId?: string | null;
  line: string;
  source: "llm" | "template" | "cache";
  actions: string[];
  composeMs?: number;
  ttsMs?: number;
}

export interface LlmCallRecord {
  sessionId: string | null;
  agent: string;
  model: string;
  inputTokens: number;
  outputTokens: number;
  cachedTokens: number;
  latencyMs: number;
  costUsd: number;
  cacheHit: boolean;
}

export interface Store {
  addMemory(m: NewMemory): Promise<Memory | null>;
  listMemories(q: { discordIds?: string[]; status?: "open" | "resolved"; sessionId?: string }): Promise<Memory[]>;
  setMemoryStatus(id: string, status: "open" | "resolved"): Promise<Memory | null>;
  intervention(r: InterventionRecord): void;
  llmCall(r: LlmCallRecord): void;
}

export class EarsStore implements Store {
  constructor(private baseUrl: string) {}

  private async call<T>(method: string, path: string, body?: unknown): Promise<T | null> {
    try {
      const res = await fetch(`${this.baseUrl.replace(/\/$/, "")}${path}`, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        signal: AbortSignal.timeout(3000),
      });
      if (!res.ok) {
        log.warn("store.failed", { method, path, status: res.status, body: (await res.text()).slice(0, 200) });
        return null;
      }
      return (await res.json()) as T;
    } catch (err) {
      log.warn("store.unreachable", { method, path, error: String(err) });
      return null;
    }
  }

  addMemory(m: NewMemory) {
    return this.call<Memory>("POST", "/api/memories", m);
  }

  async listMemories(q: { discordIds?: string[]; status?: "open" | "resolved"; sessionId?: string }) {
    const params = new URLSearchParams();
    for (const id of q.discordIds ?? []) params.append("discordId", id);
    if (q.status) params.set("status", q.status);
    if (q.sessionId) params.set("sessionId", q.sessionId);
    return (await this.call<Memory[]>("GET", `/api/memories?${params}`)) ?? [];
  }

  setMemoryStatus(id: string, status: "open" | "resolved") {
    return this.call<Memory>("PATCH", `/api/memories/${id}`, { status });
  }

  intervention(r: InterventionRecord): void {
    void this.call("POST", "/api/interventions", r);
  }

  llmCall(r: LlmCallRecord): void {
    void this.call("POST", "/api/llm-calls", r);
  }
}

/** Replay without ears: the same behaviour, kept in memory. */
export class MemoryStore implements Store {
  memories: Memory[] = [];
  interventions: InterventionRecord[] = [];
  llmCalls: LlmCallRecord[] = [];

  async addMemory(m: NewMemory): Promise<Memory> {
    const row: Memory = {
      id: `m${this.memories.length + 1}`,
      discordId: m.discordId,
      name: m.name ?? null,
      kind: m.kind,
      summary: m.summary,
      quote: m.quote ?? null,
      topicId: m.topicId ?? null,
      sessionId: m.sessionId ?? null,
      status: "open",
      createdAt: new Date().toISOString(),
    };
    this.memories.push(row);
    return row;
  }

  async listMemories(q: { discordIds?: string[]; status?: "open" | "resolved"; sessionId?: string }) {
    return this.memories.filter(
      (m) =>
        (!q.discordIds?.length || q.discordIds.includes(m.discordId)) &&
        (!q.status || m.status === q.status) &&
        (!q.sessionId || m.sessionId === q.sessionId),
    );
  }

  async setMemoryStatus(id: string, status: "open" | "resolved") {
    const m = this.memories.find((x) => x.id === id);
    if (m) m.status = status;
    return m ?? null;
  }

  intervention(r: InterventionRecord): void {
    this.interventions.push(r);
  }

  llmCall(r: LlmCallRecord): void {
    this.llmCalls.push(r);
  }
}
