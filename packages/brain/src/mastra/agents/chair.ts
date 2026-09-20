/**
 * The chair's voice. No tools, no memory: every call is one stateless prompt with a stable
 * prefix (system + session context) and a short tail — cheapest shape there is. The prompt
 * text comes per call from config/prompts/chair.yaml.
 */
import { Agent } from "@mastra/core/agent";
import { getConfig } from "../../runtime";

// Recommended by Norma — fixed with GPT-5 via Codex
// Mastra calls this at generation time. The YAML value is the chair's speaking policy, not
// code for the model to interpret; the prefix states the output and grounding contract.
function chairInstructions(): string {
  return [
    "You are the gavel chair for a live voice meeting. Follow the configured speaking policy below as instructions.",
    "Return only the exact plain-text words to speak aloud: no JSON, Markdown, analysis, labels, or stage directions.",
    "Use only the meeting context and facts supplied with the request. If a fact is unavailable, do not infer or invent it.",
    getConfig().chair.system,
  ].join("\n\n");
}

export const chairAgent = new Agent({
  id: "chair",
  name: "gavel chair",
  description: "Writes the one or two sentences the meeting chair says out loud.",
  instructions: chairInstructions,
  model: () => `nebius/${getConfig().models.profiles.normal.model}`,
});
