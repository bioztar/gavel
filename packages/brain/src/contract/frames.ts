/**
 * The ears↔brain wire — docs/CONTRACT.md §2, mirrored from ears' frames.py.
 * Parsing is lenient: unknown frames and extra fields are ignored, never fatal.
 */
import { z } from "zod";
import { Agenda } from "./agenda";

const stamp = { at: z.string().optional(), atMs: z.number() };
const Participant = z.object({ discordId: z.string(), name: z.string() });
export type Participant = z.infer<typeof Participant>;

export const EarsFrame = z.discriminatedUnion("type", [
  z.object({ type: z.literal("ready"), channelId: z.string(), participants: z.array(Participant), ...stamp }),
  z.object({ type: z.literal("participants"), participants: z.array(Participant), ...stamp }),
  z.object({ type: z.literal("speaking.start"), discordId: z.string(), ...stamp }),
  z.object({ type: z.literal("speaking.end"), discordId: z.string(), ...stamp }),
  z.object({
    type: z.literal("transcript"),
    discordId: z.string(),
    text: z.string(),
    name: z.string().optional(),
    final: z.boolean().optional(),
    utteranceId: z.string().optional(),
    ...stamp,
  }),
  z.object({
    type: z.literal("spoken"),
    utteranceId: z.string(),
    interrupted: z.boolean().optional(),
    error: z.string().nullish(),
    ...stamp,
  }),
  z.object({ type: z.literal("turn.start"), discordId: z.string(), ...stamp }),
  z.object({ type: z.literal("turn.tick"), discordId: z.string(), ...stamp }),
  z.object({ type: z.literal("turn.end"), discordId: z.string(), ...stamp }),
  z.object({
    type: z.literal("session.started"),
    sessionId: z.string(),
    title: z.string().nullish(),
    context: z.string().nullish(),
    agenda: Agenda.nullish(),
    ...stamp,
  }),
  z.object({ type: z.literal("session.ended"), sessionId: z.string(), ...stamp }),
  z.object({
    type: z.literal("moderation"),
    action: z.enum(["muted", "unmuted", "failed"]),
    discordId: z.string(),
    until: z.number().nullish(),
    error: z.string().nullish(),
    ...stamp,
  }),
]);
export type EarsFrame = z.infer<typeof EarsFrame>;

export function parseEarsFrame(raw: unknown): EarsFrame | null {
  const parsed = EarsFrame.safeParse(raw);
  return parsed.success ? parsed.data : null;
}

export type BrainFrame =
  | { type: "speak"; utteranceId: string; audio: string; format?: string; priority?: boolean }
  | { type: "stop" }
  | { type: "mute"; discordId: string; seconds: number; reason?: string }
  | { type: "unmute"; discordId: string };
