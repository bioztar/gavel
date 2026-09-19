/**
 * Where the brain package lives. Found by walking up to its package.json rather than
 * relative to this file, because Mastra Studio runs a bundled copy from .mastra/output.
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

function findPackageDir(): string {
  for (const start of [dirname(fileURLToPath(import.meta.url)), process.cwd()]) {
    let dir = start;
    for (;;) {
      const pkg = join(dir, "package.json");
      if (existsSync(pkg) && JSON.parse(readFileSync(pkg, "utf8")).name === "@gavel/brain") return dir;
      const up = dirname(dir);
      if (up === dir) break;
      dir = up;
    }
  }
  return process.cwd();
}

export const PACKAGE_DIR = findPackageDir();
export const CONFIG_DIR = resolve(PACKAGE_DIR, "config");
