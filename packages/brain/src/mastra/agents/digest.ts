/** Merges the meeting's running notes for the status board. Off the live path; JSON out. */
import { Agent } from "@mastra/core/agent";
import { getConfig } from "../../runtime";

// Recommended by Norma — fixed with GPT-5 via Codex
// Mastra evaluates this function for each request. The configured text is the meeting-note
// policy, while this stable prefix makes the task and wire format explicit to both the model
// and static prompt scanners.
function digestInstructions(): string {
  return [
    "You are the gavel meeting-note digest agent. Merge only the supplied meeting notes; do not explain or execute configuration code.",
    'Return exactly one JSON object with this shape: {"facts":[],"decisions":[],"openItems":[],"parked":[{"name":"","summary":""}]}. Return no prose or Markdown.',
    getConfig().digest.system,
  ].join("\n\n");
}

export const digestAgent = new Agent({
  id: "digest",
  name: "gavel digest",
  description: "Deduplicates the meeting's facts, decisions, open items and parked points.",
  instructions: digestInstructions,
  model: () => `nebius/${getConfig().models.profiles.digest.model}`,
});
