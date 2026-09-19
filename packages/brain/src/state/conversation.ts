/**
 * What was said in the channel: everyone's final transcripts and Karen's own lines, by name.
 * The model sees the tail of it, so it answers the room rather than a one-line summary.
 *
 * Transcripts arrive out of order (each speaker's STT finishes at its own pace), so lines
 * are kept sorted by when they were said.
 */
const KEEP = 60;

export interface Line {
  at: number;
  id: string;
  name: string;
  text: string;
}

export class Conversation {
  private lines: Line[] = [];

  add(line: Line): void {
    const text = line.text.replace(/\s+/g, " ").trim();
    if (!text) return;
    let i = this.lines.length;
    while (i > 0 && this.lines[i - 1]!.at > line.at) i--;
    this.lines.splice(i, 0, { ...line, text });
    if (this.lines.length > KEEP) this.lines.splice(0, this.lines.length - KEEP);
  }

  reset(): void {
    this.lines = [];
  }

  /**
   * The newest lines within `seconds` of `now` that fit in `maxWords`, oldest first, one
   * "Name: words" per line. `except` leaves out one person (their words go in separately).
   */
  tail(now: number, opts: { seconds: number; maxWords: number; except?: string }): string {
    if (opts.maxWords <= 0) return "";
    const out: string[] = [];
    let words = 0;
    for (let i = this.lines.length - 1; i >= 0; i--) {
      const l = this.lines[i]!;
      if (now - l.at > opts.seconds * 1000) break;
      if (l.id === opts.except) continue;
      const n = l.text.split(" ").length;
      if (words + n > opts.maxWords) break;
      words += n;
      out.push(`${l.name}: ${l.text}`);
    }
    return out.reverse().join("\n");
  }
}
