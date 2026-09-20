/**
 * SLNG text-to-speech — the chair's voice. Two transports (config/models.yaml → tts):
 * `http` returns a whole clip per line; `stream` keeps one WebSocket to SLNG's unified
 * bridge open and warm, and hands back 48 kHz mono PCM as it is synthesized.
 * Identical lines are served from a small cache: templates repeat, audio costs money.
 */
import WebSocket from "ws";
import type { Config } from "../config";
import { log } from "../log";

/** ears plays streamed audio at Discord's own rate, so it is asked for at exactly that. */
export const STREAM_RATE = 48_000;

export interface Speech {
  audio: Buffer;
  format: string;
  latencyMs: number;
  cached: boolean;
}

export interface Streamed {
  /** From sending the text to the first audio; 0 when served from the cache. */
  firstAudioMs: number;
  cached: boolean;
}

/** Wrap Discord-rate PCM in a standard WAV container for APIs that fetch audio by URL. */
export function pcmS16leToWav(pcm: Buffer, sampleRate = STREAM_RATE, channels = 1): Buffer {
  const bitsPerSample = 16;
  const bytesPerSample = bitsPerSample / 8;
  const header = Buffer.alloc(44);
  header.write("RIFF", 0, "ascii");
  header.writeUInt32LE(36 + pcm.length, 4);
  header.write("WAVE", 8, "ascii");
  header.write("fmt ", 12, "ascii");
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20); // PCM
  header.writeUInt16LE(channels, 22);
  header.writeUInt32LE(sampleRate, 24);
  header.writeUInt32LE(sampleRate * channels * bytesPerSample, 28);
  header.writeUInt16LE(channels * bytesPerSample, 32);
  header.writeUInt16LE(bitsPerSample, 34);
  header.write("data", 36, "ascii");
  header.writeUInt32LE(pcm.length, 40);
  return Buffer.concat([header, pcm]);
}

export interface Tts {
  synthesize(text: string): Promise<Speech>;
  /** 48 kHz mono s16le PCM, handed to `onChunk` as it is synthesized. Resolves when the line is complete. */
  stream?(text: string, onChunk: (pcm: Buffer) => void): Promise<Streamed>;
  /** Open the streaming socket ahead of the first line. */
  warm?(): void;
}

export class SlngTts implements Tts {
  private cache = new Map<string, Speech>();
  private pcmCache = new Map<string, Buffer>();
  private socket: BridgeSocket | null = null;
  private queue: Promise<unknown> = Promise.resolve();

  constructor(
    private cfg: () => Config["models"]["tts"],
    private apiKey: string,
  ) {}

  warm(): void {
    if (this.cfg().transport !== "stream") return;
    this.bridge()
      .ready()
      .catch((err) => log.warn("tts.warm_failed", { error: String(err) }));
  }

  stream(text: string, onChunk: (pcm: Buffer) => void): Promise<Streamed> {
    // One line at a time on the one socket.
    const run = this.queue.then(() => this.streamNow(text, onChunk));
    this.queue = run.catch(() => {});
    return run;
  }

  private async streamNow(text: string, onChunk: (pcm: Buffer) => void): Promise<Streamed> {
    const cfg = this.cfg();
    const key = `${cfg.model}|${cfg.voice}|${text}`;
    const hit = this.pcmCache.get(key);
    if (hit) {
      onChunk(hit);
      return { firstAudioMs: 0, cached: true };
    }
    const socket = this.bridge();
    const chunks: Buffer[] = [];
    try {
      const done = await socket.say(text, (pcm) => {
        chunks.push(pcm);
        onChunk(pcm);
      }, cfg.timeoutMs);
      if (cfg.cacheSize) {
        this.pcmCache.set(key, Buffer.concat(chunks));
        while (this.pcmCache.size > cfg.cacheSize) this.pcmCache.delete(this.pcmCache.keys().next().value as string);
      }
      return { firstAudioMs: done.firstAudioMs, cached: false };
    } catch (err) {
      // A failed line leaves the socket in an unknown state: start the next one fresh.
      socket.close();
      if (this.socket === socket) this.socket = null;
      throw err;
    } finally {
      // Keep a socket warm for the next line, whatever happened to this one.
      if (!this.socket?.usable) this.warm();
    }
  }

  /** The warm socket for the current model and voice; a config change opens a new one. */
  private bridge(): BridgeSocket {
    const cfg = this.cfg();
    const url = `${cfg.baseUrl.replace(/^http/, "ws").replace(/\/$/, "")}/v1/bridges/unmute/tts/${cfg.model}`;
    const init = { type: "init", voice: cfg.voice, config: { encoding: "linear16", sample_rate: STREAM_RATE, language: cfg.language } };
    const id = `${url}|${JSON.stringify(init)}`;
    if (this.socket?.usable && this.socket.id === id) return this.socket;
    this.socket?.close();
    this.socket = new BridgeSocket(id, url, this.apiKey, init);
    return this.socket;
  }

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

/**
 * One open connection to the unified TTS bridge: `init` once, then `text` + `flush` per
 * line; audio comes back as binary frames and the line ends with `audio_end` (or
 * `flushed` — whichever this model sends first is the one that ends lines from then on).
 */
class BridgeSocket {
  private ws: WebSocket;
  private opened: Promise<void>;
  private line: { onChunk: (pcm: Buffer) => void; resolve: (r: { firstAudioMs: number }) => void; reject: (e: Error) => void; sentAt: number; firstAt: number | null } | null = null;
  private terminal: string | null = null;
  private closed = false;
  private keepalive: NodeJS.Timeout;

  constructor(
    readonly id: string,
    url: string,
    apiKey: string,
    init: Record<string, unknown>,
  ) {
    const started = performance.now();
    this.ws = new WebSocket(url, { headers: { Authorization: `Bearer ${apiKey}` } });
    this.opened = new Promise<void>((resolve, reject) => {
      const fail = (err: Error) => reject(err);
      this.ws.once("open", () => this.ws.send(JSON.stringify(init)));
      this.ws.once("error", fail);
      this.ws.once("close", () => fail(new Error("TTS socket closed before ready")));
      this.ws.on("message", (data, binary) => {
        if (binary) return this.audio(data as Buffer);
        const msg = parse(data.toString());
        if (msg.type === "ready") {
          log.info("tts.ready", { ms: Math.round(performance.now() - started) });
          resolve();
        } else if (msg.type === "audio_end" || msg.type === "flushed") this.end(msg.type);
        else if (msg.type === "error") {
          const err = new Error(`TTS: ${msg.message ?? msg.error ?? msg.code ?? "error"}`);
          fail(err);
          this.fail(err);
        }
      });
    });
    this.opened.catch(() => {});
    this.ws.on("error", (err) => this.fail(err));
    this.ws.on("close", (code, reason) => {
      log.info("tts.closed", { code, reason: reason.toString().slice(0, 120), aliveMs: Math.round(performance.now() - started) });
      this.closed = true;
      clearInterval(this.keepalive);
      this.fail(new Error("TTS socket closed"));
    });
    // An idle socket can be dropped; a keepalive keeps the warm one warm.
    this.keepalive = setInterval(() => this.send({ type: "keepalive" }), 15_000);
  }

  get usable(): boolean {
    return !this.closed;
  }

  ready(): Promise<void> {
    return this.opened;
  }

  async say(text: string, onChunk: (pcm: Buffer) => void, timeoutMs: number): Promise<{ firstAudioMs: number }> {
    await this.opened;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => this.fail(new Error(`TTS line timed out after ${timeoutMs} ms`)), timeoutMs);
      const settle = <T>(f: (v: T) => void) => (v: T) => {
        clearTimeout(timer);
        this.line = null;
        f(v);
      };
      this.line = { onChunk, resolve: settle(resolve), reject: settle(reject), sentAt: performance.now(), firstAt: null };
      this.send({ type: "text", text });
      this.send({ type: "flush" });
    });
  }

  close(): void {
    this.closed = true;
    clearInterval(this.keepalive);
    this.ws.close();
  }

  private audio(pcm: Buffer): void {
    const line = this.line;
    if (!line) return;
    line.firstAt ??= performance.now();
    line.onChunk(pcm);
  }

  private end(type: string): void {
    this.terminal ??= type;
    const line = this.line;
    if (!line || type !== this.terminal) return;
    line.resolve({ firstAudioMs: Math.round((line.firstAt ?? performance.now()) - line.sentAt) });
  }

  private fail(err: Error): void {
    this.line?.reject(err);
  }

  private send(msg: Record<string, unknown>): void {
    if (this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(msg));
  }
}

function parse(raw: string): Record<string, string | undefined> {
  try {
    return JSON.parse(raw) as Record<string, string | undefined>;
  } catch {
    return {};
  }
}

/** Offline: no audio, no cost. */
export class SilentTts implements Tts {
  async synthesize(): Promise<Speech> {
    return { audio: Buffer.alloc(0), format: "wav", latencyMs: 0, cached: false };
  }
}
