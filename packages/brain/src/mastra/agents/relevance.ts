/** Labels a speaker's recent words against the agenda. Small, fast model; JSON out. */
import { Agent } from "@mastra/core/agent";
import { getConfig } from "../../runtime";

export const relevanceAgent = new Agent({
  id: "relevance",
  name: "gavel relevance",
  description: "Is this speaker on the current agenda topic, another one, or off the agenda?",
  instructions: () => getConfig().relevance.system,
  model: () => `nebius/${getConfig().models.profiles.fast.model}`,
});
