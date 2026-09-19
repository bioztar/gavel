/**
 * Everything tunable lives in YAML under config/ — models, prices, thresholds, prompts.
 * Loaded and validated here, and hot-reloaded: edit a file mid-call and the next tick
 * uses it. A file that fails validation is logged and the last good config stays.
 */
import { readFileSync, watch } from "node:fs";
import { join } from "node:path";
import { parse } from "yaml";
import { z } from "zod";
import { log } from "./log";
import { CONFIG_DIR } from "./paths";

export const DEFAULT_CONFIG_DIR = CONFIG_DIR;

const Profile = z.object({
  model: z.string(),
  temperature: z.number().min(0).max(2).default(0),
  maxOutputTokens: z.number().int().positive(),
  timeoutMs: z.number().int().positive(),
  jsonPromptInjection: z.boolean().default(false),
});

export const ModelsConfig = z.object({
  profiles: z.object({ fast: Profile, normal: Profile }),
  prices: z.record(z.string(), z.object({ input: z.number(), output: z.number() })),
  tts: z.object({
    baseUrl: z.string(),
    model: z.string(),
    voice: z.string(),
    timeoutMs: z.number().int().positive(),
    cacheSize: z.number().int().nonnegative(),
  }),
});

export const Policy = z.object({
  floorShareThreshold: z.number(),
  floorWindowSeconds: z.number(),
  floorMinSpeakingSeconds: z.number(),
  topicOverrunFactor: z.number(),
  silenceSeconds: z.number(),
  minSecondsBetweenInterventions: z.number(),
  offAgendaGraceSeconds: z.number(),
  allowMute: z.boolean(),
  escalateAfterSeconds: z.number(),
  muteSeconds: z.number(),
});
export type Policy = z.infer<typeof Policy>;

export const TRIGGERS = ["escalate", "offAgenda", "floorHog", "topicOverrun", "silence"] as const;
export type TriggerName = (typeof TRIGGERS)[number];

export const PolicyConfig = z.object({
  defaults: Policy,
  engine: z.object({
    tickMs: z.number().int().positive(),
    triggerOrder: z.array(z.enum(TRIGGERS)),
    floorGapMs: z.number().int().nonnegative(),
    escalateCooldownSeconds: z.number(),
    redirectExpirySeconds: z.number(),
    neverMuteRoles: z.array(z.string()),
    spokenTimeoutSeconds: z.number(),
  }),
  relevance: z.object({
    minNewWords: z.number().int().positive(),
    minFloorSeconds: z.number(),
    windowWords: z.number().int().positive(),
    recheckSeconds: z.number(),
    cacheSize: z.number().int().nonnegative(),
  }),
  compose: z.object({
    precompose: z.boolean(),
    lineCacheSeconds: z.number(),
  }),
  pickSpeaker: z.object({
    order: z.array(z.enum(["mustHear", "owner", "leastOnTopic"])),
    avoidLastSpeaker: z.boolean(),
    avoidLastPrompted: z.boolean(),
  }),
});
export type PolicyConfig = z.infer<typeof PolicyConfig>;

export const INTERVENTION_KINDS = [
  "offAgenda",
  "otherTopic",
  "floorHog",
  "escalateMute",
  "escalateFirm",
  "topicOverrun",
  "wrapUp",
  "silence",
  "roundRobin",
] as const;
export type InterventionKind = (typeof INTERVENTION_KINDS)[number];

const Kind = z.object({
  instruction: z.string(),
  examples: z.array(z.string()).default([]),
  templates: z.array(z.string()).min(1),
});

export const ChairPrompts = z.object({
  system: z.string(),
  user: z.string(),
  fallbackQuestion: z.string(),
  implicitTopic: z.object({ title: z.string(), goal: z.string(), questions: z.array(z.string()) }),
  kinds: z.object(Object.fromEntries(INTERVENTION_KINDS.map((k) => [k, Kind])) as Record<
    InterventionKind,
    typeof Kind
  >),
});
export type ChairPrompts = z.infer<typeof ChairPrompts>;

export const RelevancePrompts = z.object({ system: z.string(), user: z.string() });

export interface Config {
  dir: string;
  models: z.infer<typeof ModelsConfig>;
  policy: PolicyConfig;
  chair: ChairPrompts;
  relevance: z.infer<typeof RelevancePrompts>;
}

const FILES = {
  models: ["models.yaml", ModelsConfig],
  policy: ["policy.yaml", PolicyConfig],
  chair: ["prompts/chair.yaml", ChairPrompts],
  relevance: ["prompts/relevance.yaml", RelevancePrompts],
} as const;

export function loadConfig(dir = process.env.BRAIN_CONFIG_DIR ?? DEFAULT_CONFIG_DIR): Config {
  const read = <T>(file: string, schema: z.ZodType<T>): T => {
    const raw = parse(readFileSync(join(dir, file), "utf8"));
    const parsed = schema.safeParse(raw);
    if (!parsed.success) throw new Error(`${file}: ${z.prettifyError(parsed.error)}`);
    return parsed.data;
  };
  const config: Config = {
    dir,
    models: read(...FILES.models),
    policy: read(...FILES.policy),
    chair: read(...FILES.chair),
    relevance: read(...FILES.relevance),
  };
  // Env beats YAML for the model ids only — handy for a quick A/B without editing files.
  if (process.env.BRAIN_MODEL_FAST) config.models.profiles.fast.model = process.env.BRAIN_MODEL_FAST;
  if (process.env.BRAIN_MODEL_NORMAL)
    config.models.profiles.normal.model = process.env.BRAIN_MODEL_NORMAL;
  return config;
}

/** Reload on any change under the config dir. Returns a stop function. */
export function watchConfig(config: Config, onChange: (next: Config) => void): () => void {
  let timer: NodeJS.Timeout | undefined;
  const watcher = watch(config.dir, { recursive: true }, () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      try {
        const next = loadConfig(config.dir);
        onChange(next);
        log.info("config.reloaded", { dir: config.dir });
      } catch (err) {
        log.warn("config.invalid", { error: String(err) });
      }
    }, 150);
  });
  return () => watcher.close();
}
