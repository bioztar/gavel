/**
 * The chair's model calls, through the Mastra agents (so they are traced), on Nebius.
 * Stateless: no memory threads, so the prompt never grows with the meeting.
 */
import type { Config } from "../config";
import type { Classification } from "../state/relevance";
import { z } from "zod";
import type { ClassifyRequest, ComposeRequest, Llm, Usage } from "./llm";
import { chairAgent } from "../mastra/agents/chair";
import { relevanceAgent } from "../mastra/agents/relevance";

const Verdict = z.object({
  verdict: z.enum(["current", "otherTopic", "offAgenda", "unclear"]),
  topicId: z.string().nullish(),
  summary: z.string().nullish(),
});

interface UsageLike {
  inputTokens?: number;
  outputTokens?: number;
  cachedInputTokens?: number;
}

export class MastraLlm implements Llm {
  constructor(
    private cfg: () => Config["models"],
    private onUsage: (u: Usage) => void,
  ) {}

  async classify(req: ClassifyRequest): Promise<Classification | null> {
    const p = this.cfg().profiles.fast;
    const started = performance.now();
    const res = await relevanceAgent.generate(req.user, {
      instructions: req.system,
      modelSettings: { temperature: p.temperature, maxOutputTokens: p.maxOutputTokens },
      abortSignal: AbortSignal.timeout(p.timeoutMs),
      structuredOutput: {
        schema: Verdict,
        jsonPromptInjection: p.jsonPromptInjection,
        errorStrategy: "fallback",
        fallbackValue: { verdict: "unclear" },
      },
    });
    this.report("relevance", p.model, res.usage as UsageLike | undefined, started);
    return res.object as Classification;
  }

  async compose(req: ComposeRequest): Promise<string | null> {
    const p = this.cfg().profiles.normal;
    const started = performance.now();
    const res = await chairAgent.generate(req.user, {
      instructions: req.system,
      modelSettings: { temperature: p.temperature, maxOutputTokens: p.maxOutputTokens },
      abortSignal: AbortSignal.timeout(p.timeoutMs),
    });
    this.report("chair", p.model, res.usage as UsageLike | undefined, started);
    return res.text?.trim() || null;
  }

  private report(agent: Usage["agent"], model: string, usage: UsageLike | undefined, started: number): void {
    this.onUsage({
      agent,
      model,
      inputTokens: usage?.inputTokens ?? 0,
      outputTokens: usage?.outputTokens ?? 0,
      cachedTokens: usage?.cachedInputTokens ?? 0,
      latencyMs: Math.round(performance.now() - started),
      cacheHit: (usage?.cachedInputTokens ?? 0) > 0,
    });
  }
}
