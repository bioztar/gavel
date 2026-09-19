/**
 * The running engine and config, for the Mastra tools and workflow steps, which Mastra
 * constructs statically. main.ts / replay.ts set them; Studio without a running loop gets
 * a clear "not running" instead of a crash.
 */
import { type Config, loadConfig } from "./config";
import type { Engine } from "./engine";

let engine: Engine | null = null;
let config: Config | null = null;

export function setEngine(e: Engine | null): void {
  engine = e;
}

export function getEngine(): Engine {
  if (!engine) throw new Error("the chair's loop is not running in this process (start it with `pnpm start`)");
  return engine;
}

export function hasEngine(): boolean {
  return engine !== null;
}

export function setConfig(c: Config): void {
  config = c;
}

export function getConfig(): Config {
  config ??= loadConfig();
  return config;
}
