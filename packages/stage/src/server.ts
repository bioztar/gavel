/**
 * The stage server: serves the screen and streams brain's state to it.
 *
 *   GET /          the screen (public/stage.html) — document.title is `gavel-stage`
 *   GET /events    SSE: `state` events carrying brain's GET /state as it changes,
 *                  `link` events when brain comes and goes, a comment ping every 15 s
 *   GET /state     the last state seen from brain (503 before the first)
 *   GET /health    { ok, brain, clients, stateAgeMs }
 *
 * One poller reads brain's GET /state (the same source the ears console uses through
 * its /api/brain-state bridge) and fans every change out to every open tab. Tabs never
 * talk to brain and brain never knows the screen exists.
 *
 * Runs on Node ≥ 24 as plain `node src/server.ts` — no dependencies, no build.
 */
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const PUBLIC_DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "public");

const TYPES: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".woff2": "font/woff2",
};

export interface Options {
  brainStateUrl: string;
  /** How often brain is asked. Every change is pushed; unchanged polls push nothing. */
  pollMs: number;
  /** Give up on one poll after this long; brain is then "unreachable" until the next answer. */
  fetchTimeoutMs: number;
  pingMs: number;
  fetchImpl: typeof fetch;
  now: () => number;
  log: (event: string, fields?: Record<string, unknown>) => void;
}

export interface Stage {
  readonly clients: Set<ServerResponse>;
  readonly brainOk: boolean;
  readonly state: unknown;
  handle(req: IncomingMessage, res: ServerResponse): void;
  /** One poll of brain, pushed to every client if anything changed. */
  poll(): Promise<void>;
  start(): void;
  stop(): void;
}

const DEFAULTS: Options = {
  brainStateUrl: "http://127.0.0.1:8788/state",
  pollMs: 750,
  fetchTimeoutMs: 1500,
  pingMs: 15_000,
  fetchImpl: fetch,
  now: Date.now,
  log: (event, fields) => console.log(JSON.stringify({ at: new Date().toISOString(), event, ...fields })),
};

export function createStage(overrides: Partial<Options> = {}): Stage {
  const opts: Options = { ...DEFAULTS, ...overrides };
  const clients = new Set<ServerResponse>();
  let state: unknown = null;
  let stateJson = "";
  let stateAt = 0;
  let brainOk = false;
  let everPolled = false;
  let seq = 0;
  let pollTimer: NodeJS.Timeout | null = null;
  let pingTimer: NodeJS.Timeout | null = null;
  let polling: Promise<void> | null = null;

  function frame(event: string, data: string): string {
    seq += 1;
    return `event: ${event}\nid: ${seq}\ndata: ${data}\n\n`;
  }

  function broadcast(chunk: string): void {
    for (const res of clients) {
      if (res.destroyed) {
        clients.delete(res);
        continue;
      }
      res.write(chunk);
    }
  }

  function stateEvent(): string {
    return frame("state", JSON.stringify({ at: opts.now(), brain: brainOk, state }));
  }

  function linkEvent(): string {
    return frame("link", JSON.stringify({ at: opts.now(), brain: brainOk }));
  }

  async function poll(): Promise<void> {
    let json: string;
    let parsed: unknown;
    try {
      const res = await opts.fetchImpl(opts.brainStateUrl, { signal: AbortSignal.timeout(opts.fetchTimeoutMs) });
      if (!res.ok) throw new Error(`brain answered ${res.status}`);
      json = await res.text();
      parsed = JSON.parse(json);
      if (!parsed || typeof parsed !== "object") throw new Error("brain state is not an object");
    } catch (err) {
      const was = brainOk;
      brainOk = false;
      if (was || !everPolled) opts.log("brain.unreachable", { error: String(err instanceof Error ? err.message : err) });
      everPolled = true;
      if (was) broadcast(linkEvent());
      return;
    }
    const was = brainOk;
    brainOk = true;
    everPolled = true;
    const changed = json !== stateJson;
    if (changed) {
      stateJson = json;
      state = parsed;
      stateAt = opts.now();
    }
    if (!was) opts.log("brain.reachable", { url: opts.brainStateUrl });
    // A state event also says brain is back; a link event alone covers the rare case of
    // brain returning with exactly the state it left with.
    if (changed) broadcast(stateEvent());
    else if (!was) broadcast(linkEvent());
  }

  function events(req: IncomingMessage, res: ServerResponse): void {
    res.writeHead(200, {
      "content-type": "text/event-stream",
      "cache-control": "no-store",
      connection: "keep-alive",
      "x-accel-buffering": "no",
    });
    // Late join, reconnect, first paint: the newest state goes out at once, so a tab is
    // never blank for longer than one round trip. Nothing is replayed — every event is
    // the whole state, so Last-Event-ID has nothing to add.
    res.write("retry: 1000\n\n");
    res.write(state ? stateEvent() : linkEvent());
    clients.add(res);
    const drop = () => {
      clients.delete(res);
    };
    req.on("close", drop);
    res.on("close", drop);
    res.on("error", drop);
  }

  function file(res: ServerResponse, name: string): void {
    const ext = name.slice(name.lastIndexOf("."));
    const path = join(PUBLIC_DIR, name);
    if (!TYPES[ext] || name.includes("..") || name.includes("/") || !existsSync(path)) {
      res.writeHead(404, { "content-type": "text/plain" }).end("not found");
      return;
    }
    res.writeHead(200, { "content-type": TYPES[ext], "cache-control": "no-cache" });
    res.end(readFileSync(path));
  }

  function handle(req: IncomingMessage, res: ServerResponse): void {
    const url = new URL(req.url ?? "/", "http://stage");
    if (req.method !== "GET" && req.method !== "HEAD") {
      res.writeHead(405).end();
      return;
    }
    switch (url.pathname) {
      case "/":
      case "/index.html":
      case "/stage.html":
        return file(res, "stage.html");
      case "/events":
        return events(req, res);
      case "/state":
        if (!state) {
          res.writeHead(503, { "content-type": "application/json" }).end(JSON.stringify({ error: "no state from brain yet" }));
          return;
        }
        res.writeHead(200, { "content-type": "application/json", "cache-control": "no-store" }).end(stateJson);
        return;
      case "/health":
        res.writeHead(200, { "content-type": "application/json", "cache-control": "no-store" }).end(
          JSON.stringify({ ok: true, brain: brainOk, clients: clients.size, stateAgeMs: state ? opts.now() - stateAt : null }),
        );
        return;
      default:
        return file(res, url.pathname.slice(1));
    }
  }

  function start(): void {
    if (pollTimer) return;
    const tick = () => {
      if (polling) return;
      polling = poll().finally(() => {
        polling = null;
      });
    };
    tick();
    pollTimer = setInterval(tick, opts.pollMs);
    pingTimer = setInterval(() => broadcast(`: ping ${opts.now()}\n\n`), opts.pingMs);
  }

  function stop(): void {
    if (pollTimer) clearInterval(pollTimer);
    if (pingTimer) clearInterval(pingTimer);
    pollTimer = pingTimer = null;
    for (const res of clients) res.end();
    clients.clear();
  }

  return {
    clients,
    get brainOk() {
      return brainOk;
    },
    get state() {
      return state;
    },
    handle,
    poll,
    start,
    stop,
  };
}

function blank(value: string | undefined): string | undefined {
  const v = value?.trim();
  return v ? v : undefined;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const host = blank(process.env.HOST) ?? "127.0.0.1";
  const port = Number(blank(process.env.PORT) ?? 8793);
  const stage = createStage({
    brainStateUrl: blank(process.env.BRAIN_STATE_URL) ?? DEFAULTS.brainStateUrl,
    pollMs: Number(blank(process.env.BRAIN_POLL_MS) ?? DEFAULTS.pollMs),
  });
  const server = createServer(stage.handle);
  server.listen(port, host, () => {
    DEFAULTS.log("stage.ready", { url: `http://${host}:${port}/`, brain: process.env.BRAIN_STATE_URL ?? DEFAULTS.brainStateUrl });
    stage.start();
  });
  const shutdown = () => {
    stage.stop();
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(0), 1000).unref();
  };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}
