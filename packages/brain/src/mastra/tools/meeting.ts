/** Memory and meeting-state tools. Memories live in ears' Postgres, shared by everything. */
import { createTool } from "@mastra/core/tools";
import { z } from "zod";
import { getEngine } from "../../runtime";

const MemoryOut = z.object({
  id: z.string(),
  discordId: z.string(),
  name: z.string().nullable(),
  kind: z.string(),
  summary: z.string(),
  topicId: z.string().nullable(),
  status: z.string(),
});

export const parkItemTool = createTool({
  id: "park-item",
  description: "Put an off-agenda point on the parking lot, under the person who raised it, for a later meeting.",
  inputSchema: z.object({
    discordId: z.string(),
    name: z.string(),
    summary: z.string().max(200),
    quote: z.string().optional(),
  }),
  outputSchema: z.object({ memory: MemoryOut.nullable() }),
  execute: async (input) => {
    const e = getEngine();
    const memory = await e.park({ ...input, topicId: e.topic()?.id ?? null });
    return { memory };
  },
});

export const recallTool = createTool({
  id: "recall-memories",
  description: "Open parked points and notes, optionally for specific people (Discord ids).",
  inputSchema: z.object({ discordIds: z.array(z.string()).optional() }),
  outputSchema: z.object({ memories: z.array(MemoryOut) }),
  execute: async ({ discordIds }) => ({ memories: await getEngine().recall(discordIds) }),
});

export const resolveMemoryTool = createTool({
  id: "resolve-memory",
  description: "Mark a parked point as dealt with.",
  inputSchema: z.object({ id: z.string() }),
  outputSchema: z.object({ memory: MemoryOut.nullable() }),
  execute: async ({ id }) => {
    try {
      return { memory: await getEngine().resolveMemory(id) };
    } catch (error) {
      throw new Error(`could not resolve meeting memory ${id}`, { cause: error });
    }
  },
});

export const meetingStateTool = createTool({
  id: "meeting-state",
  description: "The live meeting: current topic and clock, who talked how long, who is off the agenda, what was parked.",
  inputSchema: z.object({}),
  outputSchema: z.object({ state: z.record(z.string(), z.unknown()) }),
  execute: async () => ({ state: getEngine().view() as unknown as Record<string, unknown> }),
});

export const advanceTopicTool = createTool({
  id: "advance-topic",
  description: "Move the meeting to the next agenda topic.",
  inputSchema: z.object({}),
  outputSchema: z.object({ topic: z.string().nullable() }),
  execute: async () => {
    const e = getEngine();
    e.advanceTopic();
    return { topic: e.topic()?.title ?? null };
  },
});
