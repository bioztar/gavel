/**
 * SLNG text-to-speech — the chair's voice. Same route and per-model body as ears' tts.py.
 * Identical lines are served from a small cache: templates repeat, audio costs money.
 */
import type { Config } from "../config";

export interface Speech {
  audio: Buffer;
  format: string;
  latencyMs: number;
  cached: boolean;
}

export interface Tts {
  synthesize(text: string): Promise<Speech>;
}

export class SlngTts implements Tts {
  private cache = new Map<string, Speech>();

  constructor(
    private cfg: () => Config["models"]["tts"],
    private apiKey: string,
  ) {}

  async synthesize(text: string): Promise<Speech> {
    const cfg = this.cfg();
    const key = `${cfg.model}|${cfg.voice}|${text}`;
    const hit = this.cache.get(key);
    if (hit) return { ...hit, latencyMs: 0, cached: true };
    const started = performance.now();
    const res = await fetch(`${cfg.baseUrl.replace(/\/$/, "")}/v1/tts/${cfg.model}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${this.apiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify(body(cfg.model, cfg.voice, text)),
      signal: AbortSignal.timeout(cfg.timeoutMs),
    });
    const type = res.headers.get("content-type") ?? "";
    if (!res.ok || !type.startsWith("audio/")) {
      throw new Error(`TTS HTTP ${res.status}: ${(await res.text()).slice(0, 200)}`);
    }
    const speech: Speech = {
      audio: Buffer.from(await res.arrayBuffer()),
      format: type.split("/")[1]?.split(";")[0] ?? "wav",
      latencyMs: Math.round(performance.now() - started),
      cached: false,
    };
    if (cfg.cacheSize) {
      this.cache.set(key, speech);
      while (this.cache.size > cfg.cacheSize) this.cache.delete(this.cache.keys().next().value as string);
    }
    return speech;
  }
}

function body(model: string, voice: string, text: string): Record<string, string> {
  if (model.includes("fish")) return { text, reference_id: voice };
  if (model.includes("aura")) return { text, model: voice };
  return { text, voice_id: voice };
}

/** Offline: no audio, no cost. */
export class SilentTts implements Tts {
  async synthesize(): Promise<Speech> {
    return { audio: Buffer.alloc(0), format: "wav", latencyMs: 0, cached: false };
  }
}
