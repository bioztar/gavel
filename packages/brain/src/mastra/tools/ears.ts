/** The chair's hands in the call — ears commands as Mastra tools. */
import { createTool } from "@mastra/core/tools";
import { z } from "zod";
import { getEngine } from "../../runtime";

export const speakTool = createTool({
  id: "speak",
  description:
    "Say a line into the meeting in the chair's voice. priority=true cuts in over anyone talking (Discord priority speaker).",
  inputSchema: z.object({ text: z.string().min(1).max(400), priority: z.boolean().default(false) }),
  outputSchema: z.object({ ok: z.boolean(), utteranceId: z.string().optional(), ttsMs: z.number().optional() }),
  execute: async ({ text, priority }) => {
    const out = await getEngine().speak(text, priority);
    return { ok: !!out.utteranceId, ...out };
  },
});

export const stopTool = createTool({
  id: "stop-speaking",
  description: "Stop whatever the chair is saying and drop its queue.",
  inputSchema: z.object({}),
  outputSchema: z.object({ ok: z.boolean() }),
  execute: async () => ({ ok: getEngine().stop() }),
});

export const muteTool = createTool({
  id: "mute-participant",
  description:
    "Server-mute a participant for a few seconds. ears lifts it automatically (max 60 s). Announce it out loud first.",
  inputSchema: z.object({
    discordId: z.string(),
    seconds: z.number().positive().max(60).default(15),
    reason: z.string().optional(),
  }),
  outputSchema: z.object({ ok: z.boolean() }),
  execute: async ({ discordId, seconds, reason }) => ({ ok: getEngine().mute(discordId, seconds, reason) }),
});

export const unmuteTool = createTool({
  id: "unmute-participant",
  description: "Lift a mute the chair set, before its timer runs out.",
  inputSchema: z.object({ discordId: z.string() }),
  outputSchema: z.object({ ok: z.boolean() }),
  execute: async ({ discordId }) => ({ ok: getEngine().unmute(discordId) }),
});
