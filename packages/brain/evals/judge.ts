/**
 * The two rubric dimensions a model has to judge: is the line polite enough to survive a
 * real meeting, and did it invent anything the chair was never told. Everything else is
 * counted in code (score.ts).
 *
 * One interface, two implementations: `NebiusJudge` for the scored pass a human runs with
 * NEBIUS_API_KEY set, and whatever the tests pass in. No test ever touches the network.
 */
import { Agent } from "@mastra/core/agent";
import { z } from "zod";
import type { Config } from "../src/config";
import { env } from "../src/env";

export type Dimension = "polite" | "grounded";

export interface JudgeRequest {
  dimension: Dimension;
  /** The line the chair produced. */
  line: string;
  /** Exactly the facts the chair was given for this intervention — nothing else is allowed in the line. */
  facts: string;
}

export interface Verdict {
  pass: boolean;
  reason: string;
}

export interface Judge {
  judge(req: JudgeRequest): Promise<Verdict>;
}

const RUBRIC: Record<Dimension, string> = {
  polite: [
    "You are grading one sentence a meeting chair says out loud, cutting into a live call.",
    "PASS if a real person could hear it in front of their colleagues without feeling put down:",
    "it acknowledges before it redirects, it is warm and brief, it is not sarcastic, not scolding,",
    "and it does not embarrass anyone. FAIL if it blames, lectures, mocks, or is curt to the point of rude.",
  ].join(" "),
  grounded: [
    "You are checking one sentence a meeting chair says out loud for invented content.",
    "You are given every fact the chair was told. PASS if the line only uses those facts:",
    "names, topics, numbers, dates, decisions and commitments must all appear in the facts.",
    "A fact of '(none)' means there is nothing there. FAIL if the line states or implies anything",
    "the facts do not contain — including a topic that is not listed, a number nobody gave it,",
    "or an action it promises to take. Generic facilitation language is not invention.",
  ].join(" "),
};

const Graded = z.object({
  pass: z.boolean(),
  reason: z.string(),
});

/** Judging is not latency-bound the way a live interruption is. */
const JUDGE_TIMEOUT_MS = 30_000;

/**
 * The scored pass, on the same Nebius model the chair itself uses (config/models.yaml →
 * profiles.normal). The key is read from the environment and never printed: if it is
 * missing, this throws before any call is made.
 */
export class NebiusJudge implements Judge {
  private agent: Agent;

  constructor(private cfg: Config) {
    if (!env.nebiusApiKey) throw new Error("NEBIUS_API_KEY is not set");
    const model = cfg.models.profiles.normal.model;
    this.agent = new Agent({
      id: "evalJudge",
      name: "gavel eval judge",
      description: "Grades one chair line against one rubric dimension.",
      instructions: "You grade meeting-chair lines against a rubric. Answer only with the verdict.",
      model: `nebius/${model}`,
    });
  }

  async judge(req: JudgeRequest): Promise<Verdict> {
    const res = await this.agent.generate(
      [RUBRIC[req.dimension], "", "FACTS THE CHAIR WAS GIVEN:", req.facts, "", `LINE: ${req.line}`].join("\n"),
      {
        modelSettings: { temperature: 0, maxOutputTokens: 120 },
        abortSignal: AbortSignal.timeout(JUDGE_TIMEOUT_MS),
        structuredOutput: {
          schema: Graded,
          // Nebius models are not flagged for native structured output in Mastra's catalog,
          // the same reason the relevance profile sets this.
          jsonPromptInjection: true,
          errorStrategy: "fallback",
          fallbackValue: { pass: false, reason: "the judge returned nothing usable" },
        },
      },
    );
    return res.object as Verdict;
  }
}
