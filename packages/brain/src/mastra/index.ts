/**
 * The Mastra instance — `pnpm studio` (mastra dev) finds it here.
 *
 * Storage is ears' Postgres (POSTGRES_DSN, shared with everything else), in its own
 * `mastra` schema: workflow runs and traces sit next to the transcripts. Set
 * GAVEL_MASTRA_STORAGE=off to run without it (offline replay, tests).
 */
import { Mastra } from "@mastra/core/mastra";
import { MastraStorageExporter, Observability } from "@mastra/observability";
import { PostgresStore } from "@mastra/pg";
import { chairAgent } from "./agents/chair";
import { operatorAgent } from "./agents/operator";
import { relevanceAgent } from "./agents/relevance";
import { interveneWorkflow } from "./workflows/intervene";

const DEFAULT_DSN = "postgresql://gavel:gavel@localhost:5432/gavel";

/** ears' DSN is SQLAlchemy-flavoured (`postgresql+asyncpg://`); node-postgres wants plain. */
export function pgDsn(dsn = process.env.POSTGRES_DSN ?? DEFAULT_DSN): string {
  return dsn.replace(/^postgres(ql)?\+\w+:/, "postgresql:");
}

const withStorage = process.env.GAVEL_MASTRA_STORAGE !== "off";

export const mastra = new Mastra({
  agents: { chairAgent, relevanceAgent, operatorAgent },
  workflows: { interveneWorkflow },
  ...(withStorage
    ? {
        storage: new PostgresStore({ id: "gavel", connectionString: pgDsn(), schemaName: "mastra" }),
        observability: new Observability({
          configs: { default: { serviceName: "gavel-brain", exporters: [new MastraStorageExporter()] } },
        }),
      }
    : {}),
});
