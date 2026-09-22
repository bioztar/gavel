import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { afterEach, describe, expect, it } from "vitest";
import { createStage, type Stage } from "../src/server.ts";

type Brain = { state: unknown; down: boolean; calls: number };

function fakeBrain(): { brain: Brain; fetchImpl: typeof fetch } {
  const brain: Brain = { state: { phase: "idle", people: [] }, down: false, calls: 0 };
  const fetchImpl = (async (input: string | URL | Request) => {
    brain.calls += 1;
    expect(String(input)).toBe("http://brain.test/state");
    if (brain.down) throw new TypeError("fetch failed");
    return new Response(JSON.stringify(brain.state), { status: 200, headers: { "content-type": "application/json" } });
  }) as typeof fetch;
  return { brain, fetchImpl };
}

const servers: Server[] = [];
const stages: Stage[] = [];
afterEach(async () => {
  for (const s of stages) s.stop();
  await Promise.all(servers.map((s) => new Promise((r) => s.close(r))));
  servers.length = stages.length = 0;
});

async function up(fetchImpl: typeof fetch) {
  const stage = createStage({ brainStateUrl: "http://brain.test/state", fetchImpl, log: () => {}, pollMs: 100_000, pingMs: 100_000 });
  const server = createServer(stage.handle);
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  servers.push(server);
  stages.push(stage);
  return { stage, base: `http://127.0.0.1:${(server.address() as AddressInfo).port}` };
}

/** Reads SSE frames off a fetch body until `count` events have arrived. */
async function events(res: Response, count: number, ms = 3000) {
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  const out: Array<{ event: string; data: unknown; id?: string }> = [];
  const deadline = Date.now() + ms;
  while (out.length < count && Date.now() < deadline) {
    const { value, done } = await Promise.race([reader.read(), new Promise<never>((_, rej) => setTimeout(() => rej(new Error("sse timeout")), deadline - Date.now()))]);
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const raw = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const frame: Record<string, string> = {};
      for (const line of raw.split("\n")) {
        if (line.startsWith(":")) continue;
        const i = line.indexOf(":");
        frame[line.slice(0, i)] = line.slice(i + 1).trim();
      }
      if (frame.event) out.push({ event: frame.event, data: JSON.parse(frame.data ?? "null"), id: frame.id });
    }
  }
  await reader.cancel().catch(() => {});
  return out;
}

describe("stage server", () => {
  it("serves the page with the right title and type, and only its own files", async () => {
    const { base } = await up(fakeBrain().fetchImpl);
    const page = await fetch(`${base}/`);
    expect(page.status).toBe(200);
    expect(page.headers.get("content-type")).toBe("text/html; charset=utf-8");
    expect(await page.text()).toContain("<title>gavel-stage</title>");
    expect((await fetch(`${base}/app.js`)).headers.get("content-type")).toBe("text/javascript; charset=utf-8");
    expect((await fetch(`${base}/board.js`)).status).toBe(200);
    expect((await fetch(`${base}/nope.js`)).status).toBe(404);
    expect((await fetch(`${base}/..%2Fpackage.json`)).status).toBe(404);
    expect((await fetch(`${base}/package.json`)).status).toBe(404);
    expect((await fetch(`${base}/`, { method: "POST" })).status).toBe(405);
  });

  it("answers /state and /health from what brain said", async () => {
    const { brain, fetchImpl } = fakeBrain();
    const { stage, base } = await up(fetchImpl);
    expect((await fetch(`${base}/state`)).status).toBe(503);
    await stage.poll();
    expect(stage.brainOk).toBe(true);
    expect(await (await fetch(`${base}/state`)).json()).toEqual(brain.state);
    const health = await (await fetch(`${base}/health`)).json();
    expect(health).toMatchObject({ ok: true, brain: true, clients: 0 });
  });

  it("gives a late joiner the current state immediately, then pushes only changes", async () => {
    const { brain, fetchImpl } = fakeBrain();
    const { stage, base } = await up(fetchImpl);
    await stage.poll();
    const res = await fetch(`${base}/events`);
    expect(res.headers.get("content-type")).toBe("text/event-stream");
    const first = await events(res, 1);
    expect(first[0]).toMatchObject({ event: "state", data: { brain: true, state: { phase: "idle" } } });

    const res2 = await fetch(`${base}/events`);
    const stream = events(res2, 2);
    await stage.poll(); // unchanged: nothing goes out
    brain.state = { phase: "active", people: [{ id: "1", name: "Ana", totalSeconds: 3, speaking: true }] };
    await stage.poll();
    const got = await stream;
    expect(got.map((e) => e.event)).toEqual(["state", "state"]);
    expect(got[1]?.data).toMatchObject({ brain: true, state: { phase: "active" } });
    expect(Number(got[1]?.id)).toBeGreaterThan(Number(got[0]?.id));
  });

  it("keeps the last state when brain goes away and says so on the stream", async () => {
    const { brain, fetchImpl } = fakeBrain();
    const { stage, base } = await up(fetchImpl);
    await stage.poll();
    const res = await fetch(`${base}/events`);
    const stream = events(res, 3);
    brain.down = true;
    await stage.poll();
    await stage.poll(); // still down: no second link event
    expect(stage.brainOk).toBe(false);
    expect(stage.state).toEqual({ phase: "idle", people: [] });
    expect(await (await fetch(`${base}/state`)).json()).toEqual({ phase: "idle", people: [] });
    brain.down = false;
    await stage.poll(); // back with the same state: a link event, not a state event
    const got = await stream;
    expect(got.map((e) => [e.event, (e.data as { brain: boolean }).brain])).toEqual([["state", true], ["link", false], ["link", true]]);
  });

  it("tells a joiner who arrives before brain ever answered that brain is down", async () => {
    const { brain, fetchImpl } = fakeBrain();
    brain.down = true;
    const { stage, base } = await up(fetchImpl);
    await stage.poll();
    const got = await events(await fetch(`${base}/events`), 1);
    expect(got[0]).toMatchObject({ event: "link", data: { brain: false } });
  });

  it("forgets clients that hang up", async () => {
    const { stage, base } = await up(fakeBrain().fetchImpl);
    const ac = new AbortController();
    const res = await fetch(`${base}/events`, { signal: ac.signal });
    const reader = res.body!.getReader();
    expect(new TextDecoder().decode((await reader.read()).value)).toContain("retry: 1000");
    expect(stage.clients.size).toBe(1);
    ac.abort();
    await new Promise((r) => setTimeout(r, 50));
    expect(stage.clients.size).toBe(0);
  });
});
