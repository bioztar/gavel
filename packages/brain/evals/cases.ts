/** Loading the frozen cases off disk. One JSON file per case, in id order. */
import { readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import { EvalCase } from "./types";

export const EVALS_DIR = resolve(fileURLToPath(new URL(".", import.meta.url)));
export const CASES_DIR = join(EVALS_DIR, "cases");

export function loadCase(path: string): EvalCase {
  const parsed = EvalCase.safeParse(JSON.parse(readFileSync(path, "utf8")));
  if (!parsed.success) throw new Error(`${path}: ${z.prettifyError(parsed.error)}`);
  return parsed.data;
}

export function loadCases(dir = CASES_DIR): EvalCase[] {
  const files = readdirSync(dir)
    .filter((f) => f.endsWith(".json"))
    .sort();
  const cases = files.map((f) => loadCase(join(dir, f)));
  const seen = new Set<string>();
  for (const c of cases) {
    if (seen.has(c.id)) throw new Error(`duplicate case id: ${c.id}`);
    seen.add(c.id);
  }
  return cases;
}
