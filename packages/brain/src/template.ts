/**
 * `{{name}}` placeholders. Unknown or empty values render as nothing; spacing is tidied.
 *
 * A spoken line also has a budget: the rubric (docs/QUALITY.md) allows the chair
 * MAX_SPOKEN_WORDS, while the material it has to carry — an agenda's own question, the
 * summary of a tangent — is written by whoever wrote the agenda and can be any length. So
 * a spoken template marks the tail it can live without as `{{question?}}`, and a template
 * with such a tail is fitted to the budget: values are first shortened to their leading
 * clause, then the optional tails are dropped from the end until the line fits. What comes
 * before the first optional tail is never dropped — that is where the name and the
 * handover live. Prompt text carries no `?` and renders exactly as it always did.
 */

/** The rubric's hard limit on a line the chair says out loud. */
export const MAX_SPOKEN_WORDS = 20;

type Vars = Record<string, string | number | undefined | null>;

const PLACEHOLDER = /\{\{\s*(\w+)(\?)?\s*\}\}/g;
/** Where a sentence can be cut and still read as one: a list break or a subordinate clause. */
const CLAUSE = /\s*[;/]\s+|\s+[—–]\s+|\s+(?:that|which|because)\s+/i;
const DANGLING = /[\s,:;—–-]+$/;

export function render(template: string, vars: Vars): string {
  const optional = [...template.matchAll(PLACEHOLDER)].filter((m) => m[2]).map((m) => m[1]!);
  if (!optional.length) return tidy(fill(template, vars));

  const attempts = [fill(template, vars), fill(template, vars, { clip: true })];
  const dropped = new Set<string>();
  for (const key of [...optional].reverse()) {
    dropped.add(key);
    attempts.push(fill(template, vars, { clip: true, dropped: new Set(dropped) }));
  }
  const lines = attempts.map((line) => close(tidy(line)));
  return lines.find((line) => wordCount(line) <= MAX_SPOKEN_WORDS) ?? lines[lines.length - 1]!;
}

function fill(
  template: string,
  vars: Vars,
  opts: { clip?: boolean; dropped?: ReadonlySet<string> } = {},
): string {
  return template.replace(PLACEHOLDER, (_, key: string, optional: string | undefined) => {
    if (optional && opts.dropped?.has(key)) return "";
    const value = vars[key];
    if (value === undefined || value === null) return "";
    const text = String(value);
    return opts.clip ? clause(text) : text;
  });
}

function tidy(line: string): string {
  return line
    .replace(/[ \t]{2,}/g, " ")
    .replace(/\s+([.,:;?!])/g, "$1")
    .replace(/([.:?!]){2,}/g, "$1")
    .trim();
}

/** A dropped tail leaves the line hanging on its "…, and now:" — close it instead. */
function close(line: string): string {
  const trimmed = line.replace(DANGLING, "");
  return trimmed && !/[.?!]$/.test(trimmed) ? `${trimmed}.` : trimmed;
}

/** The leading clause, keeping the sentence's own end mark: "Why X, so that Y?" → "Why X?" */
function clause(text: string): string {
  const at = text.search(CLAUSE);
  if (at < 0) return text;
  const head = text.slice(0, at).replace(DANGLING, "");
  if (!head) return text;
  const end = text.trim().slice(-1);
  return /[.?!]/.test(end) ? `${head}${end}` : head;
}

function wordCount(line: string): number {
  return line.trim().split(/\s+/).filter(Boolean).length;
}
