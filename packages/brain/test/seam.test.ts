/** The brain's side of SEAM_SHARED_SECRET: sent on the handshake, and refused handshakes stay refused. */
import { once } from "node:events";
import type { IncomingMessage } from "node:http";
import { afterEach, describe, expect, it } from "vitest";
import { WebSocketServer } from "ws";
import { SEAM_HEADER, seamHeaders } from "../src/ears/seam";
import { EarsStore } from "../src/ears/store";
import { EarsWire } from "../src/ears/wire";

const SECRET = "seam-test-secret";
const wires: EarsWire[] = [];
const servers: WebSocketServer[] = [];

afterEach(async () => {
  for (const w of wires.splice(0)) w.close();
  await Promise.all(servers.splice(0).map((s) => new Promise((r) => s.close(r))));
});

/** A fake ears that, like the real one, checks the header before accepting. */
async function fakeEars(expected: string | undefined): Promise<{ url: string; seen: (string | undefined)[] }> {
  const seen: (string | undefined)[] = [];
  const server = new WebSocketServer({
    port: 0,
    verifyClient: ({ req }: { req: IncomingMessage }) => {
      const presented = req.headers[SEAM_HEADER];
      seen.push(typeof presented === "string" ? presented : undefined);
      return !expected || presented === expected;
    },
  });
  servers.push(server);
  await once(server, "listening");
  const address = server.address();
  if (typeof address === "string" || address === null) throw new Error("no port");
  return { url: `ws://127.0.0.1:${address.port}`, seen };
}

function connect(url: string, secret: string | undefined): EarsWire {
  const wire = new EarsWire(url, seamHeaders(secret));
  wires.push(wire);
  wire.start();
  return wire;
}

describe("seam secret on the wire", () => {
  it("is sent on the handshake and accepted when it matches", async () => {
    const ears = await fakeEars(SECRET);
    const wire = connect(ears.url, SECRET);
    await once(wire, "connected");
    expect(wire.connected).toBe(true);
    expect(ears.seen).toEqual([SECRET]);
  });

  it("is refused when wrong or missing, and the brain does not get through", async () => {
    const ears = await fakeEars(SECRET);
    for (const secret of ["nope", undefined]) {
      const wire = connect(ears.url, secret);
      await once(wire, "disconnected");
      expect(wire.connected).toBe(false);
    }
    expect(ears.seen).toEqual(["nope", undefined]);
  });

  it("sends no header when unset, and an unauthenticated ears still accepts", async () => {
    const ears = await fakeEars(undefined);
    const wire = connect(ears.url, undefined);
    await once(wire, "connected");
    expect(ears.seen).toEqual([undefined]);
  });
});

describe("seam secret on the store", () => {
  it("rides along on every call, with and without a body", async () => {
    const calls: (string | null)[] = [];
    const { createServer } = await import("node:http");
    const server = createServer((req, res) => {
      calls.push(req.headers[SEAM_HEADER] === undefined ? null : String(req.headers[SEAM_HEADER]));
      res.writeHead(200, { "content-type": "application/json" });
      res.end("[]");
    });
    await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
    const address = server.address();
    if (typeof address === "string" || address === null) throw new Error("no port");
    const store = new EarsStore(`http://127.0.0.1:${address.port}`, seamHeaders(SECRET));
    await store.listMemories({});
    await store.addMemory({ discordId: "d", kind: "note", summary: "s" });
    await new Promise<void>((r) => server.close(() => r()));
    expect(calls).toEqual([SECRET, SECRET]);
  });
});
