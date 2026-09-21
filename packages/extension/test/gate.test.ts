// The refusal gate, unchanged from compose.py. These tests pin the behaviour
// the in-call triggers depend on: no topics → no invite, one question asked.

import { describe, expect, it } from "vitest";
import { GATE_QUESTION, briefWithAgenda, gate, rowsFromDraft, rowsFromLines } from "../src/lib/gate.js";
import type { Draft, Person } from "../src/lib/types.js";

const host: Person = { name: "Vitaly", email: "host@example.com" };
const ana: Person = { name: "Ana Ruiz", email: "ana@example.com" };

const emptyDraft: Draft = {
  title: "Weekly sync",
  purpose: "",
  start: "2026-09-24T14:00:00+02:00",
  durationMinutes: 30,
  topics: [],
};

const fullDraft: Draft = {
  ...emptyDraft,
  title: "Launch go / no-go",
  purpose: "Decide whether we ship Thursday",
  topics: [
    { title: "Pricing", minutes: 10, owner: "Ana", mustHear: ["Ana"], type: "discussion" },
    { title: "Rollout", minutes: null, owner: null, mustHear: [], type: "presentation" },
  ],
};

describe("gate", () => {
  it("refuses when the model returns no topics and asks the one question", () => {
    const out = gate(emptyDraft, "", [host, ana]);
    expect(out).toEqual({ kind: "refuse", question: GATE_QUESTION, typed: "" });
  });

  it("asks the exact question compose.py asks", () => {
    expect(GATE_QUESTION).toBe("What does this call have to decide?");
  });

  it("treats a failed model call (parsed: null) exactly like no topics", () => {
    expect(gate(null, "", [host])).toEqual(gate(emptyDraft, "", [host]));
  });

  it("does not refuse when a typed answer parses to at least one row", () => {
    const out = gate(emptyDraft, "Pricing\n- Launch date", [host, ana]);
    expect(out.kind).toBe("confirm");
    if (out.kind !== "confirm") return;
    // two typed rows plus one spare, all owned by the host as a last resort
    expect(out.rows.map((r) => r.title)).toEqual(["Pricing", "Launch date", ""]);
    expect(out.rows[0]).toMatchObject({ owner: "Vitaly", mustHear: "Vitaly", type: "discussion" });
  });

  it("refuses again, keeping the text, when the typed answer has nothing usable", () => {
    const out = gate(null, "  - ; \n", [host]);
    expect(out).toEqual({ kind: "refuse", question: GATE_QUESTION, typed: "  - ; \n" });
  });

  it("confirms on a draft with topics", () => {
    const out = gate(fullDraft, "", [host, ana]);
    expect(out.kind).toBe("confirm");
    if (out.kind !== "confirm") return;
    expect(out.draft).toBe(fullDraft);
    expect(out.rows).toHaveLength(3);
  });
});

describe("briefWithAgenda", () => {
  it("folds the typed answer in under an Agenda: heading, as render_confirm_form does", () => {
    expect(briefWithAgenda("Sync on launch", " Pricing\nRollout ")).toBe("Sync on launch\n\nAgenda:\nPricing\nRollout");
  });
  it("leaves the brief alone when nothing was typed", () => {
    expect(briefWithAgenda("Sync on launch", "  ")).toBe("Sync on launch");
  });
});

describe("rowsFromLines", () => {
  it("splits on newlines and semicolons and strips bullets", () => {
    expect(rowsFromLines("• Pricing; Rollout\n* Hiring -", "Vitaly").map((r) => r.title)).toEqual(["Pricing", "Rollout", "Hiring"]);
  });
  it("yields nothing for whitespace and punctuation", () => {
    expect(rowsFromLines(" ; \n - \n", "Vitaly")).toEqual([]);
  });
});

describe("rowsFromDraft", () => {
  it("gives an unassigned topic the host as owner and only must-hear", () => {
    const rows = rowsFromDraft(fullDraft.topics, "Vitaly");
    expect(rows[0]).toEqual({ title: "Pricing", minutes: "10", owner: "Ana", mustHear: "Ana", type: "discussion" });
    expect(rows[1]).toEqual({ title: "Rollout", minutes: "", owner: "Vitaly", mustHear: "Vitaly", type: "presentation" });
    expect(rows[2]).toEqual({ title: "", minutes: "", owner: "", mustHear: "", type: "discussion" });
  });
});
