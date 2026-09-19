/**
 * The Mastra instance — `pnpm studio` (mastra dev) finds it here.
 *
 * Storage is ears' Postgres (POSTGRES_DSN, shared with everything else), in its own
 * `mastra` schema: workflow runs and traces sit next to the transcripts. Set
 * GAVEL_MASTRA_STORAGE=off to run without it (offline replay, tests).
 *
 * Traces also go to Langfuse when LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set
 * (LANGFUSE_BASE_URL for a self-hosted or regional instance), one Langfuse session per meeting.
 */
import { Mastra } from "@mastra/core/mastra";
import { LangfuseExporter } from "@mastra/langfuse";
import { MastraStorageExporter, Observability } from "@mastra/observability";
import { PostgresStore } from "@mastra/pg";
import { env } from "../env";
import { chairAgent } from "./agents/chair";
import { digestAgent } from "./agents/digest";
import { operatorAgent } from "./agents/operator";
import { relevanceAgent } from "./agents/relevance";
import { interveneWorkflow } from "./workflows/intervene";

const DEFAULT_DSN = "postgresql://gavel:gavel@localhost:5432/gavel";

/** ears' DSN is SQLAlchemy-flavoured (`postgresql+asyncpg://`); node-postgres wants plain. */
export function pgDsn(dsn = process.env.POSTGRES_DSN ?? DEFAULT_DSN): string {
  return dsn.replace(/^postgres(ql)?\+\w+:/, "postgresql:");
}

const withStorage = process.env.GAVEL_MASTRA_STORAGE !== "off";
const withLangfuse = !!(env.langfuse.publicKey && env.langfuse.secretKey);

const exporters = [
  ...(withStorage ? [new MastraStorageExporter()] : []),
  ...(withLangfuse ? [new LangfuseExporter({ ...env.langfuse, environment: process.env.LANGFUSE_TRACING_ENVIRONMENT })] : []),
];

export const mastra = new Mastra({
  agents: { chairAgent, relevanceAgent, digestAgent, operatorAgent },
  workflows: { interveneWorkflow },
  ...(withStorage ? { storage: new PostgresStore({ id: "gavel", connectionString: pgDsn(), schemaName: "mastra" }) } : {}),
  ...(exporters.length
    ? { observability: new Observability({ configs: { default: { serviceName: "gavel-brain", exporters } } }) }
    : {}),
});
