// The refusal gate, moved from `/compose` to the point of creation.
//
// This is `packages/calendar/src/gavel_calendar/compose.py:render_confirm_form`
// with the HTML taken out: the model's reading of the brief comes back with no
// topics (or no reading at all) and the meeting is not booked. The one question
// that clears it is asked inline, and the typed answer is appended to the brief
// and re-parsed through the *same* path — there is no second-class agenda.
//
// This file runs in a content script, which is public code anyone can edit,
// so on its own it is advisory: it decides what the host sees and when, not
// what the server accepts. The server MUST reject `POST /ext/v1/agendas` with
// 422 when `agenda.topics` is empty (spec in packages/extension/README.md);
// until that endpoint exists there is no enforced gate, only this one.

import type { Draft, DraftTopic, Person, TopicRow } from "./types.js";

export const GATE_QUESTION = "What does this call have to decide?";
export const GATE_HEADLINE = "There\u2019s no agenda in that brief.";
export const GATE_BODY =
  "Karen won\u2019t put a meeting in three people\u2019s calendars without one.";
export const GATE_HINT =
  "\u201cPricing \u2014 Artem, 10 min. Launch date \u2014 me, 5 min. Then open discussion on the blockers.\u201d";

export type GateOutcome =
  | { kind: "refuse"; question: string; typed: string }
  | { kind: "confirm"; draft: Draft | null; rows: TopicRow[] };

/** The brief the model is asked to read, with a typed agenda folded in the way
 *  `render_confirm_form` does it (`f"{brief}\n\nAgenda:\n{typed}"`). */
export function briefWithAgenda(brief: string, typed: string): string {
  const t = typed.trim();
  return t ? `${brief}\n\nAgenda:\n${t}` : brief;
}

/** Decide what the panel shows after a draft comes back.
 *
 *  `typed` is the answer to the gate question from a previous round, empty on
 *  the first pass. Same three branches as the Python:
 *    1. no topics and nothing typed         → refuse
 *    2. no topics, something typed, lines   → confirm on the typed lines
 *       parse to at least one row              (a parse failure is not a
 *                                               reason to refuse twice)
 *    3. no topics, typed, nothing usable    → refuse again, keeping the text
 *    4. topics                              → confirm
 */
export function gate(draft: Draft | null, typed: string, attendees: Person[]): GateOutcome {
  const hostName = attendees[0]?.name ?? "";
  if (draft === null || draft.topics.length === 0) {
    if (!typed.trim()) return { kind: "refuse", question: GATE_QUESTION, typed: "" };
    const fallback = rowsFromLines(typed, hostName);
    if (fallback.length > 0) return { kind: "confirm", draft, rows: withSpareRow(fallback) };
    return { kind: "refuse", question: GATE_QUESTION, typed };
  }
  return { kind: "confirm", draft, rows: rowsFromDraft(draft.topics, hostName) };
}

/** `compose.py:_rows_from_lines` — one topic per line (or `;`-separated
 *  chunk), bullets stripped, the host as owner. Last resort only.
 *
 *  Deliberate divergence: the Python leaves `must_hear` blank on these rows
 *  while `_rows_from_parsed` gives an unassigned topic the host as owner *and*
 *  must-hear. That is read as an inconsistency in the original, not intent —
 *  its own docstring says a blank gives the chair nothing to chase — so the
 *  fallback row follows the same owner-and-must-hear rule as the parsed row. */
export function rowsFromLines(typed: string, hostName: string): TopicRow[] {
  const rows: TopicRow[] = [];
  for (const line of typed.split("\n")) {
    for (const chunk of line.split(";")) {
      const title = chunk.replace(/^[\s\-*\u2022]+|[\s\-*\u2022]+$/g, "");
      if (title) rows.push({ title, minutes: "", owner: hostName, mustHear: hostName, type: "discussion" });
    }
  }
  return rows;
}

/** `compose.py:_rows_from_parsed` — an unassigned topic gets the host as its
 *  owner and only must-hear rather than a blank: a guess in an editable field
 *  is one keystroke to fix, a blank gives the chair nothing to chase. */
export function rowsFromDraft(topics: DraftTopic[], hostName: string): TopicRow[] {
  const rows = topics.map<TopicRow>((t) => {
    // `t.owner or host_name`: an owner of `""` is absent too.
    const owner = t.owner || hostName;
    return {
      title: t.title,
      minutes: t.minutes === null ? "" : String(t.minutes),
      owner,
      mustHear: t.mustHear.join(", ") || owner,
      type: t.type === "presentation" ? "presentation" : "discussion",
    };
  });
  return withSpareRow(rows);
}

const EMPTY_ROW: TopicRow = { title: "", minutes: "", owner: "", mustHear: "", type: "discussion" };

/** One spare row: enough to add a topic that was missed, not so many that a
 *  parsed agenda reads as a half-empty form. */
export function withSpareRow(rows: TopicRow[]): TopicRow[] {
  return [...rows, { ...EMPTY_ROW }];
}
