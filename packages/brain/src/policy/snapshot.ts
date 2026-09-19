/** What the policy sees: a frozen view of the meeting at one instant. Built by the engine. */
import type { InterventionKind, Policy, PolicyConfig, TriggerName } from "../config";
import type { Topic } from "../contract/agenda";
import type { Episode } from "../state/relevance";

export interface PersonView {
  id: string;
  name: string;
  role: string;
  totalMs: number;
  topicMs: number;
  windowMs: number;
  holding: boolean;
  holdingSince: number | null;
  /** Their latest final transcript of a few words or more — a real remark, not a "yeah". */
  lastSaidAt: number | null;
}

export interface Redirect {
  targetId: string;
  topicId: string | null;
  /** When the chair finished saying it — escalation counts from here. Null while speaking. */
  spokenAt: number | null;
}

export interface Snapshot {
  now: number;
  purpose: string;
  policy: Policy;
  engine: PolicyConfig["engine"];
  pick: PolicyConfig["pickSpeaker"];
  newcomer: PolicyConfig["newcomer"];
  topics: Topic[];
  topicIndex: number;
  topic: Topic | null;
  topicStartedAt: number;
  /** Present humans, in the call now. */
  people: PersonView[];
  /** Who came into the call after the meeting started, not yet welcomed. */
  arrivals: Array<{ id: string; at: number }>;
  chairBusy: boolean;
  lastInterventionAt: number | null;
  silenceMs: number;
  /** silenceMs, not counting the arrivals' own talk (a hello, "can you hear me?"). */
  roomSilenceMs: number;
  episodes: Array<{ id: string; episode: Episode }>;
  redirect: Redirect | null;
  escalatedAt: Record<string, number>;
  lastSpeakerId: string | null;
  lastPromptedId: string | null;
  /** Questions already put to the room, per topic id. */
  asked: Record<string, string[]>;
  /** Recent summaries of what each person said (from the classifier), for recaps. */
  recaps: Record<string, string>;
  /** Parked this session, for the wrap-up. */
  parked: Array<{ name: string; summary: string }>;
  /** Still open from earlier meetings, for the wrap-up. */
  carried: Array<{ name: string; summary: string }>;
  /** Rendered when a topic has no questions of its own. */
  fallbackQuestion: string;
}

export type Action = "park" | "speak" | "mute" | "advance" | "start";

export interface Intervention {
  trigger: TriggerName | "addressed" | "meetingStart";
  kind: InterventionKind;
  topicId: string | null;
  /** Who it is about (the talker being redirected). */
  targetId?: string;
  /** Who is handed the floor. */
  addresseeId?: string;
  /** Placeholders for the prompt and the templates. */
  vars: Record<string, string>;
  actions: Action[];
  /** Speak as priority speaker, cutting in. */
  priority: boolean;
  park?: { discordId: string; name: string; summary: string; quote: string; topicId: string | null };
  /** A shared tangent can involve several people; preserve each person's memory. */
  parks?: Array<{ discordId: string; name: string; summary: string; quote: string; topicId: string | null }>;
  muteSeconds?: number;
  /** Counts as a redirect the target must follow (escalation watches it). */
  redirects?: boolean;
  question?: string;
}
