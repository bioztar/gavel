/**
 * The session context block: purpose, agenda, who is here. It sits right after the system
 * prompt in every model call and only changes when the agenda or the room does, so the
 * prompt prefix stays byte-identical across calls — what any provider-side prefix cache
 * (and vLLM's own prefix reuse on Nebius) keys on. Everything that changes per call goes
 * in the short user tail instead.
 */
import type { Agenda } from "../contract/agenda";

export class ContextBlock {
  private key = "";
  private text = "";

  get(agenda: Agenda | null, people: Array<{ name: string; role: string }>): string {
    const names = people.map((p) => (p.role && p.role !== "attendee" ? `${p.name} (${p.role})` : p.name)).sort();
    const key = JSON.stringify([agenda?.purpose, agenda?.topics.map((t) => [t.id, t.title, t.goal]), names]);
    if (key !== this.key) {
      this.key = key;
      this.text = build(agenda, names);
    }
    return this.text;
  }
}

function build(agenda: Agenda | null, names: string[]): string {
  const lines = [`MEETING: ${agenda?.purpose || "(no stated purpose)"}`, "AGENDA:"];
  for (const t of agenda?.topics ?? []) lines.push(`- ${t.id} | ${t.title}${t.goal ? ` | ${t.goal}` : ""}`);
  lines.push(`ATTENDEES: ${names.join(", ") || "(unknown)"}`);
  return lines.join("\n");
}
