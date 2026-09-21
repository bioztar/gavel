// Bundles the extension into dist/ (production) or dist-dev/ (--dev).
//
// Everything the browser runs is produced here from src/ and public/ — no CDN,
// no remote code, no eval. The only build-time inputs besides the source are:
//   GAVEL_GOOGLE_CLIENT_ID  — the Google OAuth *client id* (public by design,
//                             it is what a browser shows on the consent screen).
//                             Nothing else from the environment is read on purpose:
//                             a client *secret* or a provider key has no place in
//                             client code and this script has no way to receive one.
//
// --dev adds two things, both stripped from the production bundle:
//   * a content-script match for the mock server's fixture pages
//     (http://localhost:8790/fixtures/*), so the injected UI can be exercised
//     without a Google account;
//   * `__DEV_BUILD__ = true`, which enables the "dev sign-in" path that only
//     the mock server accepts.
import { build, context } from "esbuild";
import { cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { writeIcons } from "./icons.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const dev = process.argv.includes("--dev");
const watch = process.argv.includes("--watch");
const outdir = path.join(root, dev ? "dist-dev" : "dist");

const sourceManifest = JSON.parse(await readFile(path.join(root, "public/manifest.json"), "utf8"));

const MOCK_FIXTURE_MATCH = "http://localhost:8790/fixtures/*";

async function writeManifest() {
  const manifest = structuredClone(sourceManifest);
  const clientId = process.env.GAVEL_GOOGLE_CLIENT_ID ?? "";
  if (clientId) {
    manifest.oauth2.client_id = clientId;
  } else {
    // Left as a visible placeholder: Chrome loads the extension, and
    // `getAuthToken` fails with a readable error that names the setting.
    manifest.oauth2.client_id = "GAVEL_GOOGLE_CLIENT_ID-not-set.apps.googleusercontent.com";
  }
  if (dev) {
    manifest.name += " (dev)";
    // Both content scripts also run on the mock fixture pages; the scripts
    // decide by DOM shape, not host, which surface they are on.
    for (const cs of manifest.content_scripts) cs.matches.push(MOCK_FIXTURE_MATCH);
    // The mock's fixture pages are the only http origin ever touched, and only here.
    manifest.host_permissions = ["http://localhost:8790/*"];
  }
  await writeFile(path.join(outdir, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
}

await rm(outdir, { recursive: true, force: true });
await mkdir(path.join(outdir, "icons"), { recursive: true });
await cp(path.join(root, "public/options.html"), path.join(outdir, "options.html"));
await writeIcons(path.join(outdir, "icons"));
await writeManifest();

/** @type {import("esbuild").BuildOptions} */
const shared = {
  absWorkingDir: root,
  outdir,
  bundle: true,
  target: ["chrome116"],
  platform: "browser",
  sourcemap: dev ? "inline" : false,
  minify: !dev,
  legalComments: "none",
  loader: { ".css": "text" },
  define: {
    __DEV_BUILD__: JSON.stringify(dev),
    __EXTENSION_VERSION__: JSON.stringify(sourceManifest.version),
  },
  logLevel: "info",
};

// The service worker is an ES module (`background.type: "module"`); content
// scripts are classic scripts and must not contain `import`/`export`, so they
// are wrapped as IIFEs.
/** @type {import("esbuild").BuildOptions[]} */
const builds = [
  { ...shared, format: "esm", entryPoints: { background: "src/background/index.ts", options: "src/options/options.ts" } },
  { ...shared, format: "iife", entryPoints: { "content-calendar": "src/content/calendar.ts", "content-meet": "src/content/meet.ts" } },
];

if (watch) {
  for (const options of builds) {
    const ctx = await context(options);
    await ctx.watch();
  }
  console.log(`watching → ${path.relative(root, outdir)}/`);
} else {
  await Promise.all(builds.map((options) => build(options)));
  console.log(`built → ${path.relative(root, outdir)}/`);
}
