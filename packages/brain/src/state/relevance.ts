/**
 * Is each speaker on the agenda? Keeps a rolling window of their words, decides when a
 * (rationed) classifier call is worth making, and tracks off-agenda episodes: when one
 * opened, what it is about, and when it ends.
 */
import type { PolicyConfig } from "../config";

export type Verdict = "current" | "otherTopic" | "offAgenda" | "unclear";

export interface Classification {
  verdict: Verdict;
  topicId?: string | null;
  summary?: string | null;
  /** Small, displayable pieces of meeting understanding extracted with the same call. */
  facts?: string[];
  decisions?: string[];
  openItems?: string[];
}

export interface Episode {
  offSince: number;
  verdict: "otherTopic" | "offAgenda";
  topicId: string | null;
  summary: string;
  quote: string;
}

interface Speaker {
  words: string[];
  newWords: number;
  lastClassifiedAt: number;
  inFlight: boolean;
  episode: Episode | null;
  lastSummary: string | null;
}

type RelevanceCfg = PolicyConfig["relevance"];

export class RelevanceTracker {
  private speakers = new Map<string, Speaker>();
  private cache = new Map<string, Classification>();

  constructor(private cfg: () => RelevanceCfg) {}

  private get(id: string): Speaker {
    let s = this.speakers.get(id);
    if (!s) {
      s = { words: [], newWords: 0, lastClassifiedAt: 0, inFlight: false, episode: null, lastSummary: null };
      this.speakers.set(id, s);
    }
    return s;
  }

  addTranscript(id: string, text: string): void {
    const s = this.get(id);
    const words = text.split(/\s+/).filter(Boolean);
    s.words.push(...words);
    const keep = this.cfg().windowWords * 2;
    if (s.words.length > keep) s.words.splice(0, s.words.length - keep);
    s.newWords += words.length;
  }

  window(id: string): string {
    return this.get(id).words.slice(-this.cfg().windowWords).join(" ");
  }

  /**
   * Worth a model call now? Enough new words, from someone holding the floor long enough,
   * nothing already in flight, and — once an episode is open — not re-checked too often.
   */
  due(id: string, now: number, heldMs: number): boolean {
    const s = this.get(id);
    const cfg = this.cfg();
    if (s.inFlight || s.newWords < cfg.minNewWords || heldMs < cfg.minFloorSeconds * 1000) return false;
    if (s.episode && now - s.lastClassifiedAt < cfg.recheckSeconds * 1000) return false;
    return true;
  }

  /** Mark a call as started; returns the cache key and a cached verdict if there is one. */
  begin(id: string, now: number, topicId: string | null): { key: string; cached: Classification | null } {
    const s = this.get(id);
    s.inFlight = true;
    s.newWords = 0;
    s.lastClassifiedAt = now;
    const key = `${topicId ?? "-"}|${normalize(this.window(id))}`;
    return { key, cached: this.cache.get(key) ?? null };
  }

  /**
   * Apply a verdict. Returns "opened" when an off-agenda episode starts (the moment to
   * pre-compose the redirect), "closed" when it ends, otherwise null.
   */
  finish(id: string, now: number, key: string, result: Classification | null): "opened" | "closed" | null {
    const s = this.get(id);
    s.inFlight = false;
    if (!result) return null;
    this.remember(key, result);
    if (result.summary) s.lastSummary = result.summary;
    if (result.verdict === "current") {
      const had = s.episode !== null;
      s.episode = null;
      return had ? "closed" : null;
    }
    if (result.verdict === "unclear") return null;
    if (s.episode) {
      s.episode.verdict = result.verdict;
      s.episode.topicId = result.topicId ?? s.episode.topicId;
      return null;
    }
    s.episode = {
      offSince: now,
      verdict: result.verdict,
      topicId: result.topicId ?? null,
      summary: result.summary?.trim() || "that",
      quote: this.window(id),
    };
    return "opened";
  }

  episode(id: string): Episode | null {
    return this.speakers.get(id)?.episode ?? null;
  }

  lastSummary(id: string): string | null {
    return this.speakers.get(id)?.lastSummary ?? null;
  }

  episodes(): Array<[string, Episode]> {
    return [...this.speakers].flatMap(([id, s]) => (s.episode ? [[id, s.episode] as [string, Episode]] : []));
  }

  /** The chair dealt with it, or they went quiet: the episode is over and the words are spent. */
  clear(id: string): void {
    const s = this.speakers.get(id);
    if (!s) return;
    s.episode = null;
    s.words = [];
    s.newWords = 0;
  }

  /** A new topic changes what "on the agenda" means: start everyone fresh. */
  resetAll(): void {
    for (const s of this.speakers.values()) {
      s.episode = null;
      s.words = [];
      s.newWords = 0;
    }
  }

  private remember(key: string, result: Classification): void {
    const size = this.cfg().cacheSize;
    if (!size) return;
    this.cache.delete(key);
    this.cache.set(key, result);
    while (this.cache.size > size) this.cache.delete(this.cache.keys().next().value as string);
  }
}

function normalize(text: string): string {
  return text.toLowerCase().replace(/[^\p{L}\p{N} ]/gu, "").replace(/\s+/g, " ").trim();
}
