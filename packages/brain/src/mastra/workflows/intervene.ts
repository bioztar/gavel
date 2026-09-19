/**
 * One intervention, as a traced Mastra workflow: compose the line → park / speak / mute /
 * advance → record it in ears. The decision to intervene was already made in code
 * (policy/triggers.ts); this only carries it out, with every step visible in Studio.
 */
import { createStep, createWorkflow } from "@mastra/core/workflows";
import { z } from "zod";
import { INTERVENTION_KINDS, TRIGGERS } from "../../config";
import type { Intervention } from "../../policy/snapshot";
import { getEngine } from "../../runtime";

export const InterventionSchema = z.object({
  trigger: z.enum(TRIGGERS),
  kind: z.enum(INTERVENTION_KINDS),
  topicId: z.string().nullable(),
  targetId: z.string().optional(),
  addresseeId: z.string().optional(),
  vars: z.record(z.string(), z.string()),
  actions: z.array(z.enum(["park", "speak", "mute", "advance"])),
  priority: z.boolean(),
  park: z
    .object({
      discordId: z.string(),
      name: z.string(),
      summary: z.string(),
      quote: z.string(),
      topicId: z.string().nullable(),
    })
    .optional(),
  muteSeconds: z.number().optional(),
  redirects: z.boolean().optional(),
  question: z.string().optional(),
});

const Composed = z.object({
  intervention: InterventionSchema,
  line: z.string(),
  source: z.enum(["llm", "template", "cache"]),
  composeMs: z.number(),
});

const compose = createStep({
  id: "compose",
  description: "Pre-composed line, else the chair model within its timeout, else the YAML template.",
  inputSchema: z.object({ intervention: InterventionSchema }),
  outputSchema: Composed,
  execute: async ({ inputData }) => {
    const iv = inputData.intervention as Intervention;
    return { intervention: inputData.intervention, ...(await getEngine().compose(iv)) };
  },
});

const act = createStep({
  id: "act",
  description: "Park the point in ears, speak (priority cuts in), mute, move the agenda on.",
  inputSchema: Composed,
  outputSchema: Composed.extend({ ttsMs: z.number().optional(), utteranceId: z.string().optional() }),
  execute: async ({ inputData }) => {
    const out = await getEngine().act(inputData.intervention as Intervention, inputData.line);
    return { ...inputData, ...out };
  },
});

const record = createStep({
  id: "record",
  description: "What the chair said and why, into ears' interventions table.",
  inputSchema: Composed.extend({ ttsMs: z.number().optional(), utteranceId: z.string().optional() }),
  outputSchema: z.object({ line: z.string(), source: z.string() }),
  execute: async ({ inputData }) => {
    const { intervention, line, source, composeMs, ttsMs } = inputData;
    getEngine().record(intervention as Intervention, { line, source, composeMs }, ttsMs);
    return { line, source };
  },
});

export const interveneWorkflow = createWorkflow({
  id: "intervene",
  description: "Carry out one chair intervention decided by the deterministic policy.",
  inputSchema: z.object({ intervention: InterventionSchema }),
  outputSchema: z.object({ line: z.string(), source: z.string() }),
})
  .then(compose)
  .then(act)
  .then(record)
  .commit();
