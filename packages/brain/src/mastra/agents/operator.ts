/**
 * For a human in Mastra Studio: chat with the chair and let it use its hands ("mute Marc for
 * ten seconds", "what is parked for Ana?"). Never part of the live loop — the live chair
 * decides with code, and this agent's tool schemas would cost tokens on every call.
 */
import { Agent } from "@mastra/core/agent";
import { getConfig } from "../../runtime";
import { muteTool, speakTool, stopTool, unmuteTool } from "../tools/ears";
import {
  advanceTopicTool,
  meetingStateTool,
  parkItemTool,
  recallTool,
  resolveMemoryTool,
} from "../tools/meeting";

export const operatorAgent = new Agent({
  id: "operator",
  name: "gavel operator",
  description: "Operator console for the chair: inspect the meeting and act through ears.",
  instructions:
    "You help the human running a meeting operate gavel, the AI chair. Use meeting-state to look before acting. " +
    "Only mute when asked, and say it out loud with speak first. Be brief.",
  model: () => `nebius/${getConfig().models.profiles.normal.model}`,
  tools: {
    speakTool,
    stopTool,
    muteTool,
    unmuteTool,
    parkItemTool,
    recallTool,
    resolveMemoryTool,
    meetingStateTool,
    advanceTopicTool,
  },
});
