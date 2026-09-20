/** Labels a speaker's recent words against the agenda. Small, fast model; JSON out. */
import { Agent } from "@mastra/core/agent";
import { getConfig } from "../../runtime";

// Recommended by Norma — fixed with GPT-5 via Codex
// Mastra resolves the YAML policy at request time. This prefix supplies the application
// context and response contract rather than exposing a bare configuration accessor.
function relevanceInstructions(): string {
  return [
    "You are the gavel live-meeting relevance classifier. Compare one participant's recent words with the supplied agenda and current topic.",
    'Return JSON only with this shape: {"verdict":"current|otherTopic|offAgenda|unclear","topicId":null,"summary":"","facts":[],"decisions":[],"openItems":[]}. Return no prose or Markdown.',
    getConfig().relevance.system,
  ].join("\n\n");
}

export const relevanceAgent = new Agent({
  id: "relevance",
  name: "gavel relevance",
  description: "Is this speaker on the current agenda topic, another one, or off the agenda?",
  instructions: relevanceInstructions,
  model: () => `nebius/${getConfig().models.profiles.fast.model}`,
});
