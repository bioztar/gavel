// Fails the build if the shipped bundle contains anything an extension must
// never ship: eval / Function(), a remote <script src>, a broad host match, or
// something shaped like a credential. Runs on dist/ (or dist-dev/ with --dev).
//
// This is a tripwire, not a proof — a reviewer still reads the diff. It exists
// so the obvious mistakes fail loudly in CI instead of in the Web Store review.
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const dev = process.argv.includes("--dev");
const dist = path.join(root, dev ? "dist-dev" : "dist");

const FORBIDDEN = [
  // remote code / dynamic evaluation
  { name: "eval()", re: /\beval\s*\(/ },
  { name: "new Function()", re: /\bnew\s+Function\s*\(/ },
  { name: "remote <script src>", re: /<script[^>]+src\s*=\s*["']https?:/i },
  { name: "importScripts()", re: /\bimportScripts\s*\(/ },
  { name: "dynamic import of a URL", re: /\bimport\s*\(\s*["']https?:/ },
  // credential shapes — any of these in client code is a leak by definition
  { name: "client_secret", re: /client_secret/i },
  { name: "Google API key", re: /\bAIza[0-9A-Za-z_-]{35}\b/ },
  { name: "Google OAuth client secret", re: /\bGOCSPX-[0-9A-Za-z_-]{20,}\b/ },
  { name: "OpenAI-style key", re: /\bsk-[0-9A-Za-z_-]{20,}\b/ },
  { name: "Nebius/Bearer literal", re: /Bearer\s+[0-9A-Za-z_.-]{24,}/ },
  { name: "PEM private key", re: /-----BEGIN [A-Z ]*PRIVATE KEY-----/ },
  { name: "AWS access key", re: /\bAKIA[0-9A-Z]{16}\b/ },
  { name: "Resend key", re: /\bre_[0-9A-Za-z]{20,}\b/ },
];

let failed = false;

async function walk(dir) {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await walk(p)));
    else if (!/\.png$/.test(entry.name)) out.push(p);
  }
  return out;
}

const files = await walk(dist);
const manifest = JSON.parse(await readFile(path.join(dist, "manifest.json"), "utf8"));
const declared = [manifest.background.service_worker, ...manifest.content_scripts.flatMap((cs) => cs.js), manifest.options_ui.page];
for (const name of declared) {
  if (!files.includes(path.join(dist, name))) {
    console.error(`audit: manifest refers to ${name} but it was not built`);
    failed = true;
  }
}

for (const file of files) {
  const text = await readFile(file, "utf8");
  for (const { name, re } of FORBIDDEN) {
    if (re.test(text)) {
      console.error(`audit: ${path.relative(root, file)} contains ${name}`);
      failed = true;
    }
  }
}

const matches = [
  ...manifest.content_scripts.flatMap((cs) => cs.matches),
  ...(manifest.host_permissions ?? []),
  ...(manifest.optional_host_permissions ?? []),
];
for (const m of matches) {
  const broad = m === "<all_urls>" || /^\*:\/\/\*\//.test(m) || /^https?:\/\/\*\//.test(m);
  const nonGoogle = !/^https:\/\/(calendar|meet)\.google\.com\//.test(m);
  const devOk = dev && /^http:\/\/localhost:8790\//.test(m);
  if (broad || (nonGoogle && !devOk)) {
    console.error(`audit: manifest match pattern is out of scope: ${m}`);
    failed = true;
  }
}
if (manifest.oauth2?.client_id && !/\.apps\.googleusercontent\.com$/.test(manifest.oauth2.client_id)) {
  console.error("audit: oauth2.client_id does not look like a Google OAuth client id");
  failed = true;
}
const csp = manifest.content_security_policy?.extension_pages ?? "";
if (/unsafe-eval|unsafe-inline|https?:/.test(csp)) {
  console.error(`audit: extension_pages CSP is too loose: ${csp}`);
  failed = true;
}

if (failed) process.exit(1);
console.log(`audit: ${path.relative(root, dist)}/ clean`);
