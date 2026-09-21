import { describe, expect, it } from "vitest";
import { BLOCK_END, BLOCK_START, agendaBlock, briefFrom, stripAgendaBlock, topicLine, writeAgenda } from "../src/lib/description.js";
import type { ContractAgenda } from "../src/lib/types.js";

const agenda: ContractAgenda = {
  sessionId: "abc123def456",
  purpose: "Decide whether we ship Thursday",
  totalSeconds: 1800,
  attendees: [
    { discordId: "host@example.com", name: "Vitaly", role: "host" },
    { discordId: "ana@example.com", name: "Ana Ruiz", role: "attendee" },
  ],
  topics: [
    { id: "t1", title: "Pricing", goal: "", budgetSeconds: 600, owner: "ana@example.com", mustHear: ["ana@example.com", "host@example.com"], questions: [], type: "discussion" },
    { id: "t2", title: "Rollout", goal: "", budgetSeconds: 1200, owner: null, mustHear: [], questions: [], type: "presentation" },
  ],
};
const join = "https://gavel.example.com/join/abc123def456";

describe("topicLine", () => {
  it("matches ics_writer._topic_line so ics_parser can read it back", () => {
    expect(topicLine(agenda, agenda.topics[0]!)).toBe("- Pricing \u2014 10m (owner: Ana Ruiz, must hear: Ana Ruiz, Vitaly)");
    expect(topicLine(agenda, agenda.topics[1]!)).toBe("- Rollout \u2014 20m");
  });
  it("prints an id it cannot name rather than dropping the owner", () => {
    expect(topicLine(agenda, { ...agenda.topics[1]!, owner: "ghost@example.com" })).toBe("- Rollout \u2014 20m (owner: ghost@example.com)");
  });
});

describe("agendaBlock", () => {
  it("is purpose, Agenda:, topic lines, join link, fenced", () => {
    expect(agendaBlock(agenda, join).split("\n")).toEqual([
      BLOCK_START,
      "Decide whether we ship Thursday",
      "",
      "Agenda:",
      "- Pricing \u2014 10m (owner: Ana Ruiz, must hear: Ana Ruiz, Vitaly)",
      "- Rollout \u2014 20m",
      "",
      `Join: ${join}`,
      BLOCK_END,
    ]);
  });
});

describe("writeAgenda", () => {
  it("appends to what the host wrote", () => {
    const out = writeAgenda("Dial-in: 555-0100", agenda, join);
    expect(out.startsWith("Dial-in: 555-0100\n\n" + BLOCK_START)).toBe(true);
  });
  it("is idempotent: chairing twice replaces the block, keeps the host's text", () => {
    const once = writeAgenda("Dial-in: 555-0100\n\nSee the doc.", agenda, join);
    const twice = writeAgenda(once, { ...agenda, purpose: "Changed my mind" }, join);
    expect(twice.split(BLOCK_START)).toHaveLength(2);
    expect(twice).toContain("Dial-in: 555-0100\n\nSee the doc.");
    expect(twice).toContain("Changed my mind");
    expect(twice).not.toContain("ship Thursday");
  });
  it("keeps text the host added after a previous block", () => {
    const out = writeAgenda(`${agendaBlock(agenda, join)}\n\nPS bring coffee`, agenda, join);
    expect(stripAgendaBlock(out)).toBe("PS bring coffee");
  });
  it("is just the block for an empty description", () => {
    expect(writeAgenda("  \n", agenda, join)).toBe(agendaBlock(agenda, join));
  });
});

describe("briefFrom", () => {
  it("feeds the model the host's own text, never our previous output", () => {
    const desc = writeAgenda("Thursday sync before the launch.", agenda, join);
    expect(briefFrom(desc)).toBe("Thursday sync before the launch.");
  });
  it("tolerates a torn block with no end marker", () => {
    expect(briefFrom(`brief\n${BLOCK_START}\nAgenda:\n- x`)).toBe("brief");
  });
});
