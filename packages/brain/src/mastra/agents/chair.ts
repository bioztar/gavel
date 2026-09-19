/**
 * The chair's voice. No tools, no memory: every call is one stateless prompt with a stable
 * prefix (system + session context) and a short tail — cheapest shape there is. The prompt
 * text comes per call from config/prompts/chair.yaml.
 */
import { Agent } from "@mastra/core/agent";
import { getConfig } from "../../runtime";

export const chairAgent = new Agent({
  id: "chair",
  name: "gavel chair",
  description: "Writes the one or two sentences the meeting chair says out loud.",
  instructions: () => getConfig().chair.system,
  model: () => `nebius/${getConfig().models.profiles.normal.model}`,
});
