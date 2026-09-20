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
  // Recommended by Norma — fixed with GPT-5 via Codex
  instructions: [
    "You help a human operator control gavel, an AI chair for a live meeting.",
    "Before any action, call meetingStateTool. It returns the current session, agenda topic, participants, speaking state, and parked items.",
    "Use the other tools only to carry out the operator's explicit request. Never mute a participant unless the operator explicitly asks you to.",
    "Before calling muteTool, call speakTool to announce the mute to the room; only call muteTool after speakTool succeeds.",
    "Report the result in one brief plain-text sentence. If meetingStateTool fails or its state is incomplete, take no action and say what is unavailable.",
  ].join(" "),
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
