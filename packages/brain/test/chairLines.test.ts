/**
 * The spoken line, in both voices: every eval case, template mode, no model and no network.
 *
 * The rubric's three arithmetic dimensions are asserted together on purpose — a line that
 * fits by dropping the name or the handover is a worse failure than a long one.
 */
import { afterAll, describe, expect, it } from "vitest";
import { StubLlm } from "../src/chair/llm";
import { type Config, PERSONA_IDS, loadConfig } from "../src/config";
import { MAX_SPOKEN_WORDS, render } from "../src/template";
import { loadCases } from "../evals/cases";
import { generateLine } from "../evals/harness";
import { scoreFloor, scoreLength, scoreNames, words } from "../evals/score";

const persona = process.env.CHAIR_PERSONA;
afterAll(() => {
  if (persona === undefined) delete process.env.CHAIR_PERSONA;
  else process.env.CHAIR_PERSONA = persona;
});

function configFor(id: string): Config {
  process.env.CHAIR_PERSONA = id;
  return loadConfig();
}

const cases = loadCases();

describe.each(PERSONA_IDS)("%s Karen's lines", (id) => {
  const config = configFor(id);

  it.each(cases.map((c) => [c.id, c] as const))("%s stays inside the rubric", async (_id, c) => {
    const { composed } = await generateLine(c, config, new StubLlm());
    const everyone = c.agenda.attendees.map((a) => a.name);
    expect(scoreLength(composed.line, c.expect.maxWords), composed.line).toMatchObject({ pass: true });
    expect(scoreNames(composed.line, c.expect.names, everyone), composed.line).toMatchObject({ pass: true });
    expect(scoreFloor(composed.line, c.expect.floorTo), composed.line).toMatchObject({ pass: true });
  });
});

describe("fitting a line to the word budget", () => {
  const template = "Thanks {{name}}. {{addresseeName}}, over to you: {{question?}}";

  it("says the whole thing when the whole thing fits", () => {
    expect(render(template, { name: "Vitaly", addresseeName: "Marc", question: "What slipped?" })).toBe(
      "Thanks Vitaly. Marc, over to you: What slipped?",
    );
  });

  it("shortens a long question to its leading clause", () => {
    const line = render(template, {
      name: "Vitaly",
      addresseeName: "Marc",
      question: "What is not done that you expected to be done by the end of this week?",
    });
    expect(line).toBe("Thanks Vitaly. Marc, over to you: What is not done?");
    expect(words(line).length).toBeLessThanOrEqual(MAX_SPOKEN_WORDS);
  });

  it("drops the optional tail, and the colon left hanging, when shortening is not enough", () => {
    const line = render(template, {
      name: "Vitaly",
      addresseeName: "Marc",
      question: "Which of the remaining launch blockers would you personally fix first before we get to the release?",
    });
    expect(line).toBe("Thanks Vitaly. Marc, over to you.");
  });

  it("never drops the name or the handover, even when nothing else will fit", () => {
    const line = render(template, {
      name: "Vitaly",
      addresseeName: "Marc",
      question: Array.from({ length: 40 }, () => "word").join(" "),
    });
    expect(line).toBe("Thanks Vitaly. Marc, over to you.");
  });

  it("leaves prompt text, which marks no optional tail, exactly as it is", () => {
    const long = Array.from({ length: 40 }, () => "word").join(" ");
    expect(render("{{instruction}}", { instruction: long })).toBe(long);
  });
});
