// Confirm-table rows → docs/CONTRACT.md §1 agenda.

import { describe, expect, it } from "vitest";
import { EARS_DEFAULT_POLICY, ENFORCEMENT_LEVELS, buildAgenda, policyFor, fillTopicMinutes, isRegistrable, newSessionId, topicDrafts } from "../src/lib/agenda.js";
import type { ConfirmState, ContractAgenda, Person } from "../src/lib/types.js";

const host: Person = { name: "Vitaly", email: "host@example.com" };
const ana: Person = { name: "Ana Ruiz", email: "ana@example.com" };
const artem: Person = { name: "Artem Ivanov", email: "artem@example.com" };

const state: ConfirmState = {
  title: "Launch go / no-go",
  purpose: "Decide whether we ship Thursday",
  start: "2026-09-24T14:00:00+02:00",
  durationMinutes: 30,
  attendees: [host, ana, artem],
  enforcement: "medium",
  rows: [
    { title: "Pricing", minutes: "10", owner: "Ana", mustHear: "Ana, Artem", type: "discussion" },
    { title: "Rollout", minutes: "", owner: "artem@example.com", mustHear: "", type: "presentation" },
    { title: "  ", minutes: "", owner: "", mustHear: "", type: "discussion" }, // the spare row
    { title: "Blockers", minutes: "", owner: "", mustHear: "Nobody Known", type: "discussion" },
  ],
};

describe("fillTopicMinutes", () => {
  it("keeps named budgets and splits the rest evenly, remainder on the last", () => {
    expect(fillTopicMinutes([10, null, null], 30)).toEqual([10, 10, 10]);
    expect(fillTopicMinutes([10, null, null, null], 30)).toEqual([10, 6, 6, 8]);
    expect(fillTopicMinutes([null], 45)).toEqual([45]);
  });
  it("never goes negative when the named budgets exceed the meeting", () => {
    expect(fillTopicMinutes([40, null], 30)).toEqual([40, 0]);
  });
  it("returns the named budgets untouched when every row has one", () => {
    expect(fillTopicMinutes([5, 25], 30)).toEqual([5, 25]);
  });
});

describe("topicDrafts", () => {
  it("drops blank rows and gives every topic a whole-minute budget in seconds", () => {
    const drafts = topicDrafts(state.rows, 30);
    expect(drafts.map((d) => d.title)).toEqual(["Pricing", "Rollout", "Blockers"]);
    expect(drafts.map((d) => d.budgetSeconds)).toEqual([600, 600, 600]);
    expect(drafts[0]!.mustHearNames).toEqual(["Ana", "Artem"]);
    expect(drafts[1]!.ownerName).toBe("artem@example.com");
  });
});

describe("buildAgenda", () => {
  const agenda = buildAgenda({ state, host, sessionId: "abc123def456" });

  it("is contract-shaped: every §1 field present, durations in seconds", () => {
    expect(Object.keys(agenda).sort()).toEqual(["attendees", "policy", "purpose", "sessionId", "topics", "totalSeconds"]);
    expect(agenda.sessionId).toBe("abc123def456");
    expect(agenda.totalSeconds).toBe(1800);
    for (const t of agenda.topics) {
      expect(Object.keys(t).sort()).toEqual(["budgetSeconds", "goal", "id", "mustHear", "owner", "questions", "title", "type"]);
      expect(Number.isInteger(t.budgetSeconds)).toBe(true);
    }
  });

  it("marks the signed-in user as host and everyone else as attendee, ids are e-mails", () => {
    expect(agenda.attendees).toEqual([
      { discordId: "host@example.com", name: "Vitaly", role: "host" },
      { discordId: "ana@example.com", name: "Ana Ruiz", role: "attendee" },
      { discordId: "artem@example.com", name: "Artem Ivanov", role: "attendee" },
    ]);
  });

  it("adds the host when the editor did not list them", () => {
    const a = buildAgenda({ state: { ...state, attendees: [ana] }, host, sessionId: "x" });
    expect(a.attendees.map((p) => p.role)).toEqual(["host", "attendee"]);
  });

  it("resolves owners by first name, full name or e-mail; unassigned falls back to the host", () => {
    expect(agenda.topics.map((t) => t.owner)).toEqual(["ana@example.com", "artem@example.com", "host@example.com"]);
  });

  it("resolves mustHear to ids, drops unknown names, defaults to the owner", () => {
    expect(agenda.topics[0]!.mustHear).toEqual(["ana@example.com", "artem@example.com"]);
    expect(agenda.topics[1]!.mustHear).toEqual(["artem@example.com"]);
    // "Nobody Known" is on no chip → dropped → owner (host) stands in
    expect(agenda.topics[2]!.mustHear).toEqual(["host@example.com"]);
  });

  it("does not guess between two people sharing a first name", () => {
    const ana2: Person = { name: "Ana Petrova", email: "ana.p@example.com" };
    const a = buildAgenda({ state: { ...state, attendees: [host, ana, ana2] }, host, sessionId: "x" });
    expect(a.topics[0]!.owner).toBe("host@example.com");
  });

  it("numbers topics t1..tn and keeps the type", () => {
    expect(agenda.topics.map((t) => t.id)).toEqual(["t1", "t2", "t3"]);
    expect(agenda.topics.map((t) => t.type)).toEqual(["discussion", "presentation", "discussion"]);
  });

  it("falls back to the title as purpose, like agenda._purpose", () => {
    const a = buildAgenda({ state: { ...state, purpose: "  " }, host, sessionId: "x" });
    expect(a.purpose).toBe("Launch go / no-go");
  });

  it("attaches the ears default policy with the chosen enforcement level layered on", () => {
    expect(agenda.policy).toEqual(policyFor("medium"));
    expect(agenda.policy).toMatchObject(ENFORCEMENT_LEVELS.medium);
    for (const key of Object.keys(EARS_DEFAULT_POLICY)) expect(agenda.policy).toHaveProperty(key);
    const strict = buildAgenda({ state: { ...state, enforcement: "high" }, host, sessionId: "x" });
    expect(strict.policy).toMatchObject(ENFORCEMENT_LEVELS.high);
    expect(strict.policy).not.toEqual(agenda.policy);
  });

  it("serialises to JSON with no undefined holes", () => {
    const round = JSON.parse(JSON.stringify(agenda)) as ContractAgenda;
    expect(round).toEqual(agenda);
  });
});

describe("isRegistrable", () => {
  const good = buildAgenda({ state, host, sessionId: "x" });
  it("accepts a full agenda", () => {
    expect(isRegistrable(good)).toBe(true);
  });
  it("refuses an agenda with no topics — the gate, enforced one last time", () => {
    const rows = state.rows.filter((r) => !r.title.trim());
    expect(isRegistrable(buildAgenda({ state: { ...state, rows }, host, sessionId: "x" }))).toBe(false);
  });
  it("refuses a zero-length meeting", () => {
    expect(isRegistrable({ ...good, totalSeconds: 0 })).toBe(false);
  });
});

describe("newSessionId", () => {
  it("is twelve hex characters from a uuid, like uuid4().hex[:12]", () => {
    expect(newSessionId(() => "0f8fad5b-d9cb-469f-a165-70867728950e")).toBe("0f8fad5bd9cb");
    expect(newSessionId()).toMatch(/^[0-9a-f]{12}$/);
  });
});
