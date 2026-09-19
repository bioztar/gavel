/** The two model calls the chair makes, behind one interface so replay can stub them. */
import type { Topic } from "../contract/agenda";
import type { Notes } from "../state/notes";
import type { Classification } from "../state/relevance";

export interface ClassifyRequest {
  system: string;
  user: string;
  /** Structured copies of what is in the prompt, for the stub. */
  window: string;
  topicId: string | null;
  topics: Topic[];
}

export interface ComposeRequest {
  system: string;
  user: string;
  /** Overrides the normal profile's timeout (someone asked Karen directly and is waiting). */
  timeoutMs?: number;
  /** The intervention kind, for tracing. */
  kind?: string;
}

export interface DigestRequest {
  system: string;
  user: string;
}

export interface Usage {
  agent: "relevance" | "chair" | "digest";
  model: string;
  inputTokens: number;
  outputTokens: number;
  cachedTokens: number;
  latencyMs: number;
  cacheHit: boolean;
}

export interface Llm {
  /** False for a stub that never composes: the engine then always speaks the YAML templates. */
  readonly composes: boolean;
  classify(req: ClassifyRequest): Promise<Classification | null>;
  compose(req: ComposeRequest): Promise<string | null>;
  /** Merges the running notes for the status board. Absent: the board shows them as kept. */
  digest?(req: DigestRequest): Promise<Notes | null>;
}

/**
 * No model at all: a keyword classifier and no composition (the YAML templates speak).
 * For offline replay and tests — deterministic and free.
 */
export class StubLlm implements Llm {
  readonly composes = false;

  async classify(req: ClassifyRequest): Promise<Classification | null> {
    const words = new Set(tokens(req.window));
    if (words.size < 4) return { verdict: "unclear" };
    const score = (t: Topic) => tokens([t.title, t.goal, ...t.questions].join(" ")).filter((w) => words.has(w)).length;
    const current = req.topics.find((t) => t.id === req.topicId);
    if (current && score(current) > 0) return { verdict: "current", summary: current.title };
    const other = req.topics.filter((t) => t.id !== req.topicId).sort((a, b) => score(b) - score(a))[0];
    if (other && score(other) > 0) return { verdict: "otherTopic", topicId: other.id, summary: other.title };
    return { verdict: "offAgenda", summary: [...words].slice(0, 6).join(" ") };
  }

  async compose(): Promise<string | null> {
    return null;
  }
}

const STOP = new Set(
  "the a an and or but to of in on for with is are was be it that this we you i they what who how do does can our your my at as by from not have has so if just per one all any also very really will would should about".split(" "),
);

function tokens(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/[^\p{L}\p{N} ]/gu, " ")
    .split(/\s+/)
    .filter((w) => w.length > 2 && !STOP.has(w))
    .map((w) => w.replace(/s$/, ""));
}
