/** The running notes: near-duplicates dropped on the way in, the model's digest on the board. */
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import type { DigestRequest } from "../src/chair/llm";
import { SilentTts } from "../src/chair/tts";
import { loadConfig } from "../src/config";
import { loadAgendaFile } from "../src/contract/agenda";
import { MemoryStore } from "../src/ears/store";
import { Engine } from "../src/engine";
import { type Notes, addNotes, boardNotes, noteKeys } from "../src/state/notes";

const FIXTURES = resolve(__dirname, "../../contract/fixtures");

describe("addNotes", () => {
  it("drops restatements and keeps the more specific one", () => {
    const facts: string[] = [];
    addNotes(facts, ["QA needs two weeks.", "QA needs two weeks", "qa NEEDS two weeks!"]);
    expect(facts).toEqual(["QA needs two weeks."]);
    addNotes(facts, ["QA needs two more weeks."]);
    expect(facts).toEqual(["QA needs two more weeks."]);
    expect(addNotes(facts, ["The launch moves to 3 October."])).toBe(true);
    expect(addNotes(facts, ["The launch moves to 3 October"])).toBe(false);
    expect(facts).toHaveLength(2);
  });
});

describe("boardNotes", () => {
  const notes: Notes = {
    facts: ["QA needs two weeks."],
    decisions: [],
    openItems: ["Who owns the pricing page?", "Office move timing"],
    parked: [{ name: "Vitaly", summary: "office move timing" }],
  };

  it("without a digest: the notes, minus open items that are parked", () => {
    expect(boardNotes(notes, null, new Set())).toMatchObject({
      source: "raw",
      openItems: ["Who owns the pricing page?"],
      parked: [{ name: "Vitaly", summary: "office move timing" }],
    });
  });

  it("with a digest: the digest plus anything newer than it", () => {
    const seen = noteKeys(notes);
    const digest: Notes = { facts: ["QA needs two weeks."], decisions: [], openItems: ["Who owns pricing?"], parked: notes.parked };
    const later = { ...notes, decisions: ["Ship on 3 October."], facts: [...notes.facts, "QA needs two weeks"] };
    expect(boardNotes(later, digest, seen)).toEqual({
      source: "llm",
      facts: ["QA needs two weeks."],
      decisions: ["Ship on 3 October."],
      openItems: ["Who owns pricing?"],
      parked: notes.parked,
    });
  });
});

describe("the engine's digest", () => {
  it("runs when the notes change, at most every minIntervalSeconds, and never twice for the same notes", async () => {
    const config = loadConfig();
    let now = 0;
    const calls: DigestRequest[] = [];
    const engine = new Engine({
      config: () => config,
      clock: () => now,
      wire: { connected: true, send: () => true },
      store: new MemoryStore(),
      llm: {
        composes: false,
        classify: async () => null,
        compose: async () => null,
        digest: async (req) => {
          calls.push(req);
          return { facts: [], decisions: [], openItems: [], parked: [{ name: "Ana", summary: "hiring plan" }] };
        },
      },
      tts: new SilentTts(),
      fallbackAgenda: null,
    });
    const agenda = loadAgendaFile(resolve(FIXTURES, "agenda.demo.json"));
    engine.handle({ type: "session.started", sessionId: "s", title: "Sync", agenda, atMs: 0 });
    const park = (summary: string) => engine.park({ discordId: "1", name: "Ana", summary });
    const tick = async (at: number) => {
      now = at;
      engine.tick();
      await engine.idle();
    };

    await park("hiring plan");
    await park("the hiring plan for Q4");
    await tick(30_000);
    expect(calls).toHaveLength(0); // below minItems
    await park("office snacks");
    await tick(31_000);
    expect(calls).toHaveLength(1);
    expect(calls[0]!.user).toContain("- Ana: the hiring plan for Q4");
    expect(engine.view().digest).toMatchObject({ source: "llm", parked: [{ summary: "hiring plan" }] });

    await park("parking at the office");
    // Shown before the next digest runs.
    expect(engine.view().digest.parked.map((p) => p.summary)).toEqual(["hiring plan", "parking at the office"]);
    await tick(40_000);
    expect(calls).toHaveLength(1); // too soon
    await tick(52_000);
    expect(calls).toHaveLength(2);
    await tick(80_000);
    expect(calls).toHaveLength(2); // nothing new
  });
});
