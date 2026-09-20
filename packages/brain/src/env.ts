/** Secrets and endpoints from the environment, the repo-root .env, then a local .env. */
import { resolve } from "node:path";
import { config } from "dotenv";
import { PACKAGE_DIR } from "./paths";

export { PACKAGE_DIR };
config({ path: [resolve(PACKAGE_DIR, ".env"), resolve(PACKAGE_DIR, "../../.env")], quiet: true });

const blank = (v: string | undefined) => (v && v.trim() ? v.trim() : undefined);
const localEarsHost = "127.0.0.1";
const localEarsEndpoint = (protocol: "http" | "ws") => `${protocol}://${localEarsHost}:8787`;

export const env = {
  nebiusApiKey: blank(process.env.NEBIUS_API_KEY),
  slngApiKey: blank(process.env.SLNG_API_KEY),
  earsWireUrl: blank(process.env.EARS_WIRE_URL) ?? localEarsEndpoint("ws"),
  earsHttpUrl: blank(process.env.EARS_HTTP_URL) ?? localEarsEndpoint("http"),
  stageHost: blank(process.env.STAGE_HOST) ?? "127.0.0.1",
  stagePort: Number(blank(process.env.STAGE_PORT) ?? 8788),
  // Langfuse tracing (src/mastra/index.ts): on when both keys are set.
  langfuse: {
    publicKey: blank(process.env.LANGFUSE_PUBLIC_KEY),
    secretKey: blank(process.env.LANGFUSE_SECRET_KEY),
    baseUrl: blank(process.env.LANGFUSE_BASE_URL),
  },
  agendaFile: blank(process.env.AGENDA_FILE) ?? resolve(PACKAGE_DIR, "../contract/fixtures/agenda.demo.json"),
};
