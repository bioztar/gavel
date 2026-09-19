/** The rubric scorer. The judged dimensions go to a fake judge — no model, no network. */
import { resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";
import type { Intervention } from "../src/policy/snapshot";
import { CASES_DIR, loadCase } from "../evals/cases";
import type { Judge, JudgeRequest } from "../evals/judge";
import { factsOf, mentions, scoreFloor, scoreLength, scoreLine, scoreNames, words } from "../evals/score";

const hog = loadCase(resolve(CASES_DIR, "01-floor-hog-62.json"));
const group = loadCase(resolve(CASES_DIR, "08-crosstalk.json"));
const EVERYONE = ["Vitaly", "Ana", "Marc"];

const intervention = (vars: Record<string, string>): Intervention => ({
  trigger: "floorHog",
  kind: "floorHog",
  topicId: "t1",
  vars,
  actions: ["speak"],
  priority: true,
});

const fakeJudge = (pass: boolean, reason = "because"): Judge & { seen: JudgeRequest[] } => {
  const seen: JudgeRequest[] = [];
  return {
    seen,
    judge: vi.fn(async (req: JudgeRequest) => {
      seen.push(req);
      return { pass, reason };
    }),
  };
};

describe("counting words", () => {
  it("counts spoken words, not whitespace", () => {
    expect(words("  Thanks Vitaly.   Marc, your turn?  ")).toHaveLength(5);
    expect(words("   ")).toHaveLength(0);
  });

  it("passes at the limit and fails one word over", () => {
    const twenty = Array.from({ length: 20 }, () => "word").join(" ");
    expect(scoreLength(twenty, 20)).toMatchObject({ pass: true, detail: "20 words" });
    expect(scoreLength(`${twenty} more`, 20)).toMatchObject({ pass: false, detail: "21 words" });
  });

  it("an empty line is not a short line", () => {
    expect(scoreLength("", 20).pass).toBe(false);
  });
});

describe("finding a name in a line", () => {
  it("matches a whole first name, in any case, next to punctuation", () => {
    expect(mentions("Ana, go ahead.", "Ana")).toBe(true);
    expect(mentions("over to ana?", "Ana")).toBe(true);
    expect(mentions("Ana, over to you", "Ana Petrova")).toBe(true);
  });

  it("does not match a name buried in another word", () => {
    expect(mentions("we should analyse the churn", "Ana")).toBe(false);
    expect(mentions("the marcom deck", "Marc")).toBe(false);
  });
});

describe("names the right person", () => {
  it("passes when the line names them", () => {
    expect(scoreNames("Thanks Vitaly — Marc, your turn.", { kind: "person", name: "Vitaly" }, EVERYONE).pass).toBe(true);
  });

  it("fails when it redirects someone else entirely", () => {
    const score = scoreNames("Ana, wrap it up.", { kind: "person", name: "Vitaly" }, EVERYONE);
    expect(score).toMatchObject({ pass: false, detail: "does not name Vitaly" });
  });

  it("notes the other people it dragged in", () => {
    const score = scoreNames("Vitaly, Ana said enough.", { kind: "person", name: "Vitaly" }, EVERYONE);
    expect(score).toMatchObject({ pass: true, detail: "names Vitaly, also Ana" });
  });

  it("a group redirect must name nobody", () => {
    expect(scoreNames("Let's get back to the date, everyone.", { kind: "nobody" }, EVERYONE).pass).toBe(true);
    expect(scoreNames("Marc, back to the date.", { kind: "nobody" }, EVERYONE)).toMatchObject({
      pass: false,
      detail: "singles out Marc",
    });
  });
});

describe("hands the floor somewhere specific", () => {
  it("to a person, by name", () => {
    expect(scoreFloor("Marc, what did you see?", { kind: "person", name: "Marc" }).pass).toBe(true);
    expect(scoreFloor("let's hear from someone else", { kind: "person", name: "Marc" })).toMatchObject({
      pass: false,
      detail: "no handover to Marc",
    });
  });

  it("or to a named agenda item", () => {
    expect(scoreFloor("Back to The Date.", { kind: "topic", title: "The date" }).pass).toBe(true);
    expect(scoreFloor("Back to the agenda.", { kind: "topic", title: "The date" }).pass).toBe(false);
  });
});

describe("the facts the line is held to", () => {
  it("lists every var the chair was given, empty ones as (none), and drops the raw quote", () => {
    const facts = factsOf(intervention({ name: "Vitaly", topicTitle: "", question: "What slipped?", quote: "blah blah" }));
    expect(facts).toBe("name: Vitaly\ntopicTitle: (none)\nquestion: What slipped?");
  });
});

describe("scoring a whole line", () => {
  const iv = intervention({ name: "Vitaly", addresseeName: "Marc", topicTitle: "Where we actually are" });
  const good = "Thanks Vitaly — Marc, what is not done that you expected?";

  it("counts the deterministic dimensions in code and asks the judge for the other two", async () => {
    const judge = fakeJudge(true, "warm and grounded");
    const scores = await scoreLine(hog, iv, good, judge);
    expect(scores.namesRightPerson.pass).toBe(true);
    expect(scores.underWordLimit.pass).toBe(true);
    expect(scores.handsFloorSomewhere.pass).toBe(true);
    expect(scores.polite).toEqual({ pass: true, detail: "warm and grounded" });
    expect(scores.inventsNothing).toEqual({ pass: true, detail: "warm and grounded" });
    expect(judge.seen.map((r) => r.dimension).sort()).toEqual(["grounded", "polite"]);
    // The judge only ever sees the line and the facts the chair itself was given.
    expect(judge.seen[0]?.facts).toBe(factsOf(iv));
  });

  it("reports the judge's failures as failures", async () => {
    const scores = await scoreLine(hog, iv, good, fakeJudge(false, "scolding"));
    expect(scores.polite).toEqual({ pass: false, detail: "scolding" });
    expect(scores.inventsNothing.pass).toBe(false);
  });

  it("leaves the judged dimensions unrun rather than passing them, with no judge", async () => {
    const scores = await scoreLine(hog, iv, good);
    expect(scores.polite).toEqual({ pass: null, detail: "not run (no judge)" });
    expect(scores.inventsNothing.pass).toBeNull();
    expect(scores.underWordLimit.pass).toBe(true);
  });

  it("never sends an empty line to the judge", async () => {
    const judge = fakeJudge(true);
    const scores = await scoreLine(hog, iv, "", judge);
    expect(judge.judge).not.toHaveBeenCalled();
    expect(scores.underWordLimit.pass).toBe(false);
    expect(scores.polite.pass).toBeNull();
  });

  it("holds a group redirect to the group expectation from its own case file", async () => {
    const singled = await scoreLine(group, iv, "Marc, back to Where we actually are.");
    expect(singled.namesRightPerson.pass).toBe(false);
    const grouped = await scoreLine(group, iv, "Let's park pricing and get back to Where we actually are.");
    expect(grouped.namesRightPerson.pass).toBe(true);
    expect(grouped.handsFloorSomewhere.pass).toBe(true);
  });
});
