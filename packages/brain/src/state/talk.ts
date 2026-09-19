/**
 * Who has talked, how much, on which topic — from speaking.start/end plus a clock.
 * Pure bookkeeping, no timers: every question takes `now`.
 */

interface Segment {
  id: string;
  start: number;
  end: number;
}

export interface PersonTalk {
  totalMs: number;
  topicMs: number;
  windowMs: number;
  speaking: boolean;
  lastSpokeAt: number | null;
}

export class TalkLedger {
  private open = new Map<string, number>();
  private segments: Segment[] = [];
  private totals = new Map<string, number>();
  private byTopic = new Map<string, Map<string, number>>();
  private lastEnd = new Map<string, number>();
  private lastAnyEnd = 0;
  private lastStarter: string | null = null;

  constructor(private topicOf: () => string | null) {}

  start(id: string, at: number): void {
    if (this.open.has(id)) return;
    this.open.set(id, at);
    this.lastStarter = id;
  }

  end(id: string, at: number): void {
    const start = this.open.get(id);
    if (start === undefined) return;
    this.open.delete(id);
    this.record(id, start, at);
    this.lastEnd.set(id, at);
    this.lastAnyEnd = Math.max(this.lastAnyEnd, at);
  }

  /** Close open speech at a topic boundary so time lands on the right topic. */
  splitAt(at: number): void {
    for (const [id, start] of this.open) {
      this.record(id, start, at);
      this.open.set(id, at);
    }
  }

  reset(): void {
    this.open.clear();
    this.segments = [];
    this.totals.clear();
    this.byTopic.clear();
    this.lastEnd.clear();
    this.lastAnyEnd = 0;
    this.lastStarter = null;
  }

  private record(id: string, start: number, end: number): void {
    const ms = Math.max(0, end - start);
    if (!ms) return;
    this.segments.push({ id, start, end });
    this.totals.set(id, (this.totals.get(id) ?? 0) + ms);
    const topic = this.topicOf();
    if (topic) {
      const t = this.byTopic.get(topic) ?? new Map<string, number>();
      t.set(id, (t.get(id) ?? 0) + ms);
      this.byTopic.set(topic, t);
    }
  }

  // --- questions ---------------------------------------------------------------------

  isSpeaking(id: string): boolean {
    return this.open.has(id);
  }

  anyoneSpeaking(): boolean {
    return this.open.size > 0;
  }

  /** Speaking now, or paused for less than `gapMs` — still holding the floor. */
  holding(id: string, now: number, gapMs: number): boolean {
    if (this.open.has(id)) return true;
    const end = this.lastEnd.get(id);
    return end !== undefined && now - end < gapMs;
  }

  /** When this person's current hold of the floor began (pauses < gapMs bridged). */
  holdingSince(id: string, now: number, gapMs: number): number | null {
    if (!this.holding(id, now, gapMs)) return null;
    let since = this.open.get(id) ?? this.lastEnd.get(id) ?? now;
    const mine = this.segments.filter((s) => s.id === id).sort((a, b) => b.start - a.start);
    for (const s of mine) {
      if (since - s.end < gapMs) since = Math.min(since, s.start);
      else break;
    }
    return since;
  }

  lastSpeaker(): string | null {
    return this.lastStarter;
  }

  /** ms since anyone — but those in `except` — last spoke (0 while someone is speaking). */
  silenceMs(now: number, since: number, except: ReadonlySet<string> = new Set()): number {
    if ([...this.open.keys()].some((id) => !except.has(id))) return 0;
    let last = except.size ? 0 : this.lastAnyEnd;
    if (except.size) for (const [id, end] of this.lastEnd) if (!except.has(id)) last = Math.max(last, end);
    return now - Math.max(last, since);
  }

  person(id: string, now: number, topicId: string | null, windowMs: number): PersonTalk {
    const openStart = this.open.get(id);
    const live = openStart !== undefined ? now - openStart : 0;
    return {
      totalMs: (this.totals.get(id) ?? 0) + live,
      topicMs: (topicId ? (this.byTopic.get(topicId)?.get(id) ?? 0) : 0) + live,
      windowMs: this.inWindow(id, now, windowMs),
      speaking: openStart !== undefined,
      lastSpokeAt: openStart !== undefined ? now : (this.lastEnd.get(id) ?? null),
    };
  }

  private inWindow(id: string, now: number, windowMs: number): number {
    const from = now - windowMs;
    let ms = 0;
    for (const s of this.segments) {
      if (s.id !== id || s.end <= from) continue;
      ms += s.end - Math.max(s.start, from);
    }
    const openStart = this.open.get(id);
    if (openStart !== undefined) ms += now - Math.max(openStart, from);
    return ms;
  }

  /** Total speaking by everyone in the window. */
  windowTotal(now: number, windowMs: number, ids: Iterable<string>): number {
    let ms = 0;
    for (const id of ids) ms += this.inWindow(id, now, windowMs);
    return ms;
  }

  /** Drop segments nobody will ask about again (older than the longest window). */
  prune(now: number, keepMs: number): void {
    const from = now - keepMs;
    if (this.segments.length > 2000) this.segments = this.segments.filter((s) => s.end > from);
  }
}
