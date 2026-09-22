// What gets written into the real invite's description.
//
// The same text `packages/calendar/src/gavel_calendar/ics_writer.py:_description`
// puts in a compose-created `.ics`, because that is the shape
// `ics_parser.parse_ics` already reads: a purpose line, `Agenda:`, one
// `- title — Nm (owner: X, must hear: Y)` line per topic, and the join link.
// An invite written here therefore round-trips through the calendar service's
// feed poller with no new parser on the server.
//
// Rewriting is idempotent: the block is fenced with two marker lines so a second
// "Chair this meeting" on the same event replaces the previous agenda instead of
// stacking a new one under it, and whatever the host wrote *outside* the block
// (the brief, a dial-in, a doc link) is left alone.

import type { ContractAgenda } from "./types.js";

export const BLOCK_START = "— gavel agenda —";
export const BLOCK_END = "— end of agenda —";

function attendeeName(agenda: ContractAgenda, id: string | null): string {
  if (id === null) return "";
  return agenda.attendees.find((a) => a.discordId === id)?.name ?? id;
}

/** `ics_writer._topic_line` — minutes, owner, must-hear, in that format. */
export function topicLine(agenda: ContractAgenda, topic: ContractAgenda["topics"][number]): string {
  const minutes = Math.floor(topic.budgetSeconds / 60);
  const owner = attendeeName(agenda, topic.owner);
  const mustHear = topic.mustHear.map((id) => attendeeName(agenda, id));
  let line = `- ${topic.title} \u2014 ${minutes}m`;
  const parts: string[] = [];
  if (owner) parts.push(`owner: ${owner}`);
  if (mustHear.length) parts.push(`must hear: ${mustHear.join(", ")}`);
  if (parts.length) line += ` (${parts.join(", ")})`;
  return line;
}

/** `ics_writer._description`, fenced. */
export function agendaBlock(agenda: ContractAgenda, joinUrl: string): string {
  const lines: string[] = [BLOCK_START];
  const purpose = agenda.purpose.trim();
  if (purpose) {
    lines.push(purpose, "");
  }
  lines.push("Agenda:");
  for (const t of agenda.topics) lines.push(topicLine(agenda, t));
  lines.push("", `Join: ${joinUrl}`, BLOCK_END);
  return lines.join("\n");
}

/** Everything in `description` that is not a previous gavel block. */
export function stripAgendaBlock(description: string): string {
  const start = description.indexOf(BLOCK_START);
  if (start === -1) return description.trim();
  const end = description.indexOf(BLOCK_END, start);
  const before = description.slice(0, start).trim();
  const after = end === -1 ? "" : description.slice(end + BLOCK_END.length).trim();
  return [before, after].filter(Boolean).join("\n\n");
}

/** The new description: the host's own text first, then the agenda. */
export function writeAgenda(existingDescription: string, agenda: ContractAgenda, joinUrl: string): string {
  const own = stripAgendaBlock(existingDescription);
  const block = agendaBlock(agenda, joinUrl);
  return own ? `${own}\n\n${block}` : block;
}

/** The brief the model reads: the description minus any agenda we wrote before,
 *  so re-chairing an event does not feed our own output back in as the input. */
export function briefFrom(existingDescription: string): string {
  return stripAgendaBlock(existingDescription);
}
