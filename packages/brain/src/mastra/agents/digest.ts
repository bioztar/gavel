/** Merges the meeting's running notes for the status board. Off the live path; JSON out. */
import { Agent } from "@mastra/core/agent";
import { getConfig } from "../../runtime";

export const digestAgent = new Agent({
  id: "digest",
  name: "gavel digest",
  description: "Deduplicates the meeting's facts, decisions, open items and parked points.",
  instructions: () => getConfig().digest.system,
  model: () => `nebius/${getConfig().models.profiles.digest.model}`,
});
