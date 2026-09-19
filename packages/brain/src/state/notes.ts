/**
 * The meeting's running notes — facts, decisions, open items, parked points — and their tidy
 * form for the status board.
 *
 * Two layers of deduplication. Cheap and always on: a note whose words mostly match one
 * already kept is dropped (or replaces it, if it says more). Then, off the live path, the model
 * merges what only reads alike (prompts/digest.yaml). The board shows the model's last digest
 * plus any note that arrived after it, so nothing waits on the model to appear.
 */

export interface Parked {
  name: string;
  summary: string;
}

export interface Notes {
  facts: string[];
  decisions: string[];
  openItems: string[];
  parked: Parked[];
}

export interface Digest extends Notes {
  /** "llm": merged by the model (plus anything newer). "raw": the notes as kept. */
  source: "llm" | "raw";
}

const MAX_NOTES = 50;
/** Word-set overlap at which two notes count as the same point. */
const SAME = 0.75;

/** Adds each value unless a kept note already says it. A longer restatement replaces the shorter. */
export function addNotes(target: string[], values: string[] | undefined): boolean {
  let changed = false;
  for (const raw of values ?? []) {
    const value = raw.trim();
    if (!value) continue;
    const words = wordSet(value);
    const i = target.findIndex((x) => similar(wordSet(x), words));
    if (i >= 0) {
      if (words.size <= wordSet(target[i]!).size) continue;
      target[i] = value;
    } else {
      target.push(value);
      if (target.length > MAX_NOTES) target.shift();
    }
    changed = true;
  }
  return changed;
}

export function totalNotes(n: Notes): number {
  return n.facts.length + n.decisions.length + n.openItems.length + n.parked.length;
}

/** Every note, as the text the digest request carried — to tell which notes came after it. */
export function noteKeys(n: Notes): Set<string> {
  return new Set([...n.facts, ...n.decisions, ...n.openItems, ...n.parked.map(parkedLine)]);
}

export function parkedLine(p: Parked): string {
  return `${p.name}: ${p.summary}`;
}

/**
 * What the board shows: the model's digest (made from the notes in `seen`) plus every note
 * newer than it — or, with no digest yet, the notes themselves.
 */
export function boardNotes(notes: Notes, digest: Notes | null, seen: Set<string>): Digest {
  const board: Digest = digest
    ? {
        source: "llm",
        facts: merge(digest.facts, fresh(notes.facts, seen)),
        decisions: merge(digest.decisions, fresh(notes.decisions, seen)),
        openItems: merge(digest.openItems, fresh(notes.openItems, seen)),
        parked: [...digest.parked, ...notes.parked.filter((p) => !seen.has(parkedLine(p)))],
      }
    : {
        source: "raw",
        facts: [...notes.facts],
        decisions: [...notes.decisions],
        openItems: [...notes.openItems],
        parked: [...notes.parked],
      };
  // A parked point is listed once, under parked — the model does not always manage that.
  const parked = board.parked.map((p) => wordSet(p.summary));
  board.openItems = board.openItems.filter((o) => !parked.some((p) => similar(p, wordSet(o))));
  return board;
}

function fresh(list: string[], seen: Set<string>): string[] {
  return list.filter((x) => !seen.has(x));
}

function merge(base: string[], extra: string[]): string[] {
  const out = [...base];
  addNotes(out, extra);
  return out;
}

const FILLER = new Set(
  "the a an and or but to of in on for with is are was be it that this we they will would should has have its".split(" "),
);

function wordSet(text: string): Set<string> {
  return new Set(
    text
      .toLowerCase()
      .replace(/[^\p{L}\p{N} ]/gu, " ")
      .split(/\s+/)
      .filter((w) => w && !FILLER.has(w))
      .map((w) => w.replace(/s$/, "")),
  );
}

function similar(a: Set<string>, b: Set<string>): boolean {
  if (!a.size || !b.size) return false;
  let shared = 0;
  for (const w of a) if (b.has(w)) shared += 1;
  return shared / (a.size + b.size - shared) >= SAME;
}
