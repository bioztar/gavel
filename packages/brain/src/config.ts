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
  // Replies to someone who asked Karen directly: they are waiting, so a real answer a
  // little later beats a canned line now.
  directTimeoutMs: z.number().int().positive().optional(),
  jsonPromptInjection: z.boolean().default(false),
});

export const ModelsConfig = z.object({
  profiles: z.object({ fast: Profile, normal: Profile }),
  prices: z.record(z.string(), z.object({ input: z.number(), output: z.number() })),
  tts: z.object({
    // stream: one warm WebSocket, audio forwarded to ears as it is synthesized.
    // http: the whole clip per request, then one `speak` frame.
    transport: z.enum(["stream", "http"]).default("http"),
    baseUrl: z.string(),
    model: z.string(),
    voice: z.string(),
    language: z.string().default("en"),
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
  addressed: z
    .object({ followUpSeconds: z.number(), settleSeconds: z.number().default(2), contextSeconds: z.number() })
    .default({ followUpSeconds: 6, settleSeconds: 2, contextSeconds: 20 }),
  speak: z
    .object({ quietMs: z.number().int().nonnegative(), maxWaitMs: z.number().int().nonnegative(), priorityMaxWaitMs: z.number().int().nonnegative() })
    .default({ quietMs: 700, maxWaitMs: 8000, priorityMaxWaitMs: 3000 }),
  compose: z.object({
    precompose: z.boolean(),
    lineCacheSeconds: z.number(),
    templateFallback: z.boolean().default(false),
  }),
  pickSpeaker: z.object({
    order: z.array(z.enum(["mustHear", "owner", "leastOnTopic"])),
    avoidLastSpeaker: z.boolean(),
    avoidLastPrompted: z.boolean(),
  }),
});
export type PolicyConfig = z.infer<typeof PolicyConfig>;

export const INTERVENTION_KINDS = [
  "startMeeting",
  "waitingForPeople",
  "addressed",
  "offAgenda",
  "groupOffAgenda",
  "otherTopic",
  "groupOtherTopic",
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

// The chair's two voices (config/personas.yaml). `tone` is folded into `chair.system` — the
// stable prompt prefix — never into a per-call suffix, so Nebius keeps caching it.
export const PERSONA_IDS = ["formal", "funky"] as const;
export type PersonaId = (typeof PERSONA_IDS)[number];

const Persona = z.object({
  id: z.enum(PERSONA_IDS),
  displayName: z.string(),
  tone: z.string(),
  avatar: z.string(),
  idle: z.string(),
  voice: z.string().default(""),
});
export type Persona = z.infer<typeof Persona>;

export const PersonasFile = z.object({
  active: z.enum(PERSONA_IDS),
  personas: z.object(Object.fromEntries(PERSONA_IDS.map((p) => [p, Persona])) as Record<PersonaId, typeof Persona>),
});

// A persona's own fallback-line set: same kinds as ChairPrompts, only `templates` differ.
const PersonaKind = z.object({ templates: z.array(z.string()).min(4) });
export const ChairPersonaTemplates = z.object({
  // A persona file overrides only the lines that differ from chair.yaml. Missing kinds
  // deliberately keep the base templates.
  kinds: z
    .object(
      Object.fromEntries(INTERVENTION_KINDS.map((k) => [k, PersonaKind])) as Record<
        InterventionKind,
        typeof PersonaKind
      >,
    )
    .partial(),
});

export interface Config {
  dir: string;
  models: z.infer<typeof ModelsConfig>;
  policy: PolicyConfig;
  chair: ChairPrompts;
  relevance: z.infer<typeof RelevancePrompts>;
  persona: Persona;
}

const FILES = {
  models: ["models.yaml", ModelsConfig],
  policy: ["policy.yaml", PolicyConfig],
  chair: ["prompts/chair.yaml", ChairPrompts],
  relevance: ["prompts/relevance.yaml", RelevancePrompts],
  personas: ["personas.yaml", PersonasFile],
  chairFormal: ["prompts/chair.formal.yaml", ChairPersonaTemplates],
  chairFunky: ["prompts/chair.funky.yaml", ChairPersonaTemplates],
} as const;

export function loadConfig(dir = process.env.BRAIN_CONFIG_DIR ?? DEFAULT_CONFIG_DIR): Config {
  const read = <T>(file: string, schema: z.ZodType<T>): T => {
    const raw = parse(readFileSync(join(dir, file), "utf8"));
    const parsed = schema.safeParse(raw);
    if (!parsed.success) throw new Error(`${file}: ${z.prettifyError(parsed.error)}`);
    return parsed.data;
  };
  // CHAIR_PERSONA at boot beats personas.yaml's `active`; editing `active` while running is
  // the live-switch path (config/ is hot-reloaded, see watchConfig below).
  const personas = read(...FILES.personas);
  if (process.env.CHAIR_PERSONA && !(PERSONA_IDS as readonly string[]).includes(process.env.CHAIR_PERSONA)) {
    throw new Error(`CHAIR_PERSONA: must be one of ${PERSONA_IDS.join(", ")}`);
  }
  const activeId = (process.env.CHAIR_PERSONA as PersonaId | undefined) ?? personas.active;
  const persona = personas.personas[activeId];
  const personaTemplates =
    activeId === "formal" ? read(...FILES.chairFormal) : read(...FILES.chairFunky);

  const chair = read(...FILES.chair);
  for (const k of INTERVENTION_KINDS) {
    const override = personaTemplates.kinds[k];
    if (override) chair.kinds[k].templates = override.templates;
  }
  // The persona's tone joins the stable prefix (system + session context, see engine.ts),
  // never the per-call suffix, so it stays cached like the rest of the prefix.
  chair.system = `${chair.system}\n${persona.tone}`;

  const config: Config = {
    dir,
    models: read(...FILES.models),
    policy: read(...FILES.policy),
    chair,
    relevance: read(...FILES.relevance),
    persona,
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
