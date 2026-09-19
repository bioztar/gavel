/** The frozen eval cases and their loader. Offline: the stub model, no network. */
import { mkdtempSync, readdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { StubLlm } from "../src/chair/llm";
import { CASES_DIR, loadCase, loadCases } from "../evals/cases";
import { generateLine, interventionFor } from "../evals/harness";
import { config } from "./helpers";

const TEN = [
  "01-floor-hog-62",
  "02-floor-hog-81",
  "03-topic-over-budget",
  "04-topic-at-risk-two-left",
  "05-musthear-silent-70pct",
  "06-silence-15s",
  "07-fire-drill",
  "08-crosstalk",
  "09-host-monologue",
  "10-empty-agenda",
];

function tmpDir(files: Record<string, unknown>): string {
  const dir = mkdtempSync(join(tmpdir(), "gavel-evals-"));
  for (const [name, body] of Object.entries(files)) writeFileSync(join(dir, name), JSON.stringify(body));
  return dir;
}

describe("the case loader", () => {
  it("loads the ten cases off disk, in id order", () => {
    const cases = loadCases();
    expect(cases.map((c) => c.id)).toEqual(TEN);
    expect(readdirSync(CASES_DIR).filter((f) => f.endsWith(".json"))).toHaveLength(10);
  });

  it("ignores anything that is not a .json case", () => {
    const dir = tmpDir({ "01-a.json": { ...loadCase(resolve(CASES_DIR, "01-floor-hog-62.json")), id: "01-a" } });
    writeFileSync(join(dir, "README.md"), "not a case");
    expect(loadCases(dir).map((c) => c.id)).toEqual(["01-a"]);
  });

  it("rejects a case that is not the real shape, naming the field", () => {
    const broken = { ...loadCase(resolve(CASES_DIR, "06-silence-15s.json")) } as Record<string, unknown>;
    broken.state = { ...(broken.state as object), silenceMs: "fifteen" };
    const dir = tmpDir({ "01-broken.json": broken });
    expect(() => loadCases(dir)).toThrow(/silenceMs/);
  });

  it("rejects two cases claiming the same id", () => {
    const one = loadCase(resolve(CASES_DIR, "01-floor-hog-62.json"));
    expect(() => loadCases(tmpDir({ "a.json": one, "b.json": one }))).toThrow(/duplicate case id: 01-floor-hog-62/);
  });

  it("fills the optional state fields so every case is a complete snapshot", () => {
    const c = loadCase(resolve(CASES_DIR, "01-floor-hog-62.json"));
    expect(c.state.episodes).toEqual([]);
    expect(c.state.redirect).toBeNull();
    expect(c.state.escalatedAt).toEqual({});
    expect(c.expect.maxWords).toBe(20);
  });
});

describe("the frozen cases", () => {
  const cases = loadCases();

  it.each(cases.map((c) => [c.id, c] as const))("%s fires the trigger it says it does", (_id, c) => {
    const iv = interventionFor(c, config);
    expect(iv).not.toBeNull();
    expect({ trigger: iv?.trigger, kind: iv?.kind }).toEqual({ trigger: c.expect.trigger, kind: c.expect.kind });
  });

  it("hands the floor to the person each case expects", async () => {
    const byId = Object.fromEntries(
      cases.flatMap((c) => c.agenda.attendees.map((a) => [a.discordId, a.name] as const)),
    );
    for (const c of cases) {
      if (c.expect.floorTo.kind !== "person") continue;
      const iv = interventionFor(c, config);
      expect(byId[iv?.addresseeId ?? ""], c.id).toBe(c.expect.floorTo.name);
    }
  });

  it("the host's monologue is still interrupted", () => {
    const host = cases.find((c) => c.id === "09-host-monologue")!;
    const iv = interventionFor(host, config);
    const vitaly = host.agenda.attendees.find((a) => a.role === "host")!;
    expect(iv?.targetId).toBe(vitaly.discordId);
    // Never muted, though: the host keeps their mic (policy.neverMuteRoles).
    expect(iv?.actions).not.toContain("mute");
  });

  it("crosstalk is redirected as a group, nobody singled out", () => {
    const iv = interventionFor(cases.find((c) => c.id === "08-crosstalk")!, config);
    expect(iv?.kind).toBe("groupOffAgenda");
    expect(iv?.targetId).toBeUndefined();
    expect(iv?.parks).toHaveLength(2);
  });

  it("an empty agenda leaves the chair with no topic and no question to borrow", async () => {
    const empty = loadCase(resolve(CASES_DIR, "10-empty-agenda.json"));
    expect(empty.agenda.topics).toEqual([]);
    const iv = interventionFor(empty, config)!;
    expect(iv.vars.topicTitle ?? "").toBe("");
    expect(iv.vars.question ?? "").toBe("");
    const { composed } = await generateLine(empty, config, new StubLlm());
    expect(composed.source).toBe("template");
    expect(composed.line).not.toBe("");
  });

  it("produces a line for every case without a model", async () => {
    for (const c of cases) {
      const { intervention, composed } = await generateLine(c, config, new StubLlm());
      expect(intervention.kind, c.id).toBe(c.expect.kind);
      expect(composed.source, c.id).toBe("template");
      expect(composed.line.trim(), c.id).not.toBe("");
    }
  });
});
