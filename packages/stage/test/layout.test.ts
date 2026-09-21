/**
 * The screen-share invariant, measured in a real Chrome: no glyph is ever painted partially
 * clipped, at either resolution the page supports, in every scene the demo can show.
 *
 * jsdom has no layout, so this drives headless Chrome over raw CDP (no dependency) and
 * asks the page for its own geometry: for every element that carries text, the text's box
 * must sit inside the padding box of every ancestor that clips (overflow ≠ visible), a
 * line-clamped block must be a whole number of lines tall, nothing may be smaller than 18px,
 * and the document must not scroll.
 *
 * Chrome is found via $CHROME_BIN, then the usual binaries, then Playwright's cache. Set
 * STAGE_NO_CHROME=1 to skip on a machine that has none; the skip is loud.
 */
import { spawn, type ChildProcess } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync } from "node:fs";
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { homedir, tmpdir } from "node:os";
import { delimiter, join } from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createStage } from "../src/server.ts";

const SCENES = [
  "?demo=1&t=60", "?demo=1&t=1400", "?demo=1&scene=crowd&t=60", "?demo=1&scene=crowd&t=1400",
  "?demo=1&scene=open&t=300", "?demo=1&scene=gathering", "?demo=1&scene=idle", "?demo=1&scene=finished",
  "?demo=1&scene=untimed&t=200", "?demo=1&t=90&link=down", "?demo=1&t=60&owners=0", "?demo=1&t=60&owners=some", "",
];
const SIZES = [[1280, 720], [1920, 1080]] as const;

function findChrome(): string | null {
  const env = process.env.CHROME_BIN;
  if (env && existsSync(env)) return env;
  const names = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"];
  for (const dir of (process.env.PATH ?? "").split(delimiter)) {
    for (const n of names) if (dir && existsSync(join(dir, n))) return join(dir, n);
  }
  const candidates = ["/opt/google/chrome/chrome", "/snap/bin/chromium", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"];
  for (const c of candidates) if (existsSync(c)) return c;
  const cache = join(homedir(), ".cache", "ms-playwright");
  if (existsSync(cache)) {
    for (const dir of readdirSync(cache).filter((d) => d.startsWith("chromium")).sort().reverse()) {
      for (const rel of ["chrome-linux/chrome", "chrome-linux64/chrome", "chrome-mac/Chromium.app/Contents/MacOS/Chromium"]) {
        const p = join(cache, dir, rel);
        if (existsSync(p)) return p;
      }
    }
  }
  return null;
}

/** What the page reports about itself; `clipped` is the list of offending text boxes. */
interface Audit {
  title: string;
  scroll: [number, number, number, number];
  minFont: number;
  mode: string;
  clipped: string[];
  texts: number;
}

// Runs inside the page. Kept as a string so it needs no bundling and no jsdom polyfills.
const AUDIT = `(() => {
  const T = 0.5;
  const clipped = [];
  let minFont = Infinity;
  let texts = 0;
  const describe = (el) => el.tagName.toLowerCase() + (el.id ? "#" + el.id : "") + (el.className ? "." + String(el.className).trim().replace(/\\s+/g, ".") : "");
  const padBox = (el) => {
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    return { top: r.top + parseFloat(cs.borderTopWidth), bottom: r.bottom - parseFloat(cs.borderBottomWidth),
             left: r.left + parseFloat(cs.borderLeftWidth), right: r.right - parseFloat(cs.borderRightWidth) };
  };
  for (const el of document.querySelectorAll("body *")) {
    const own = [...el.childNodes].filter((n) => n.nodeType === 3 && n.textContent.trim());
    if (!own.length) continue;
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || !el.getClientRects().length) continue;
    texts++;
    const font = parseFloat(cs.fontSize);
    minFont = Math.min(minFont, font);
    const text = own.map((n) => n.textContent.trim()).join(" ").slice(0, 40);
    const lineClamp = cs.webkitLineClamp !== "none" && cs.webkitLineClamp !== "";
    const ellipsis = cs.textOverflow === "ellipsis" && cs.whiteSpace === "nowrap" && cs.overflowX !== "visible";
    const self = el.getBoundingClientRect();
    // Where the text actually is: the element box for a clamped block (the hidden lines are
    // still laid out, but the box is what is painted), the text's own range otherwise.
    let box = self;
    if (!lineClamp) {
      const range = document.createRange();
      range.selectNodeContents(el);
      const rects = [...range.getClientRects()];
      if (rects.length) box = { top: Math.min(...rects.map((r) => r.top)), bottom: Math.max(...rects.map((r) => r.bottom)),
                                left: Math.min(...rects.map((r) => r.left)), right: Math.max(...rects.map((r) => r.right)) };
    }
    // A glyph's content area can overhang its line box a little when line-height is tight;
    // that is not a clip. A tenth of the font size is well under a descender.
    const slack = font * 0.1;
    if (lineClamp) {
      const lh = parseFloat(cs.lineHeight);
      const lines = el.clientHeight / lh;
      if (lh > 0 && Math.abs(lines - Math.round(lines)) > 1 / lh || el.clientHeight < lh - 1) {
        clipped.push(describe(el) + ' "' + text + '" is ' + lines.toFixed(2) + " lines tall");
      }
    }
    for (let a = el; a && a !== document.documentElement; a = a.parentElement) {
      const acs = getComputedStyle(a);
      if (acs.overflowX === "visible" && acs.overflowY === "visible") continue;
      const p = padBox(a);
      const vertical = box.top < p.top - slack - T || box.bottom > p.bottom + slack + T;
      const horizontal = !ellipsis && (box.left < p.left - T || box.right > p.right + T);
      if (vertical || horizontal) {
        clipped.push(describe(el) + ' "' + text + '" [' + [box.top, box.bottom, box.left, box.right].map((v) => v.toFixed(1)).join(",") +
          "] is cut by " + describe(a) + " [" + [p.top, p.bottom, p.left, p.right].map((v) => v.toFixed(1)).join(",") + "]");
      }
    }
  }
  const d = document.documentElement;
  return JSON.stringify({ title: document.title, scroll: [d.scrollWidth, d.clientWidth, d.scrollHeight, d.clientHeight],
    minFont, mode: document.getElementById("stage").dataset.mode, clipped, texts });
})()`;

class Cdp {
  private id = 0;
  private pending = new Map<number, (m: { result?: Record<string, unknown>; error?: unknown }) => void>();
  private ws: WebSocket;
  constructor(ws: WebSocket) {
    this.ws = ws;
    ws.onmessage = (ev) => {
      const m = JSON.parse(String(ev.data));
      if (m.id && this.pending.has(m.id)) {
        this.pending.get(m.id)!(m);
        this.pending.delete(m.id);
      }
    };
  }
  static async connect(url: string) {
    const ws = new WebSocket(url);
    await new Promise<void>((ok, fail) => { ws.onopen = () => ok(); ws.onerror = () => fail(new Error("cdp: connect failed")); });
    return new Cdp(ws);
  }
  send(method: string, params: Record<string, unknown> = {}) {
    return new Promise<Record<string, unknown>>((ok, fail) => {
      this.pending.set(++this.id, (m) => (m.error ? fail(new Error(`${method}: ${JSON.stringify(m.error)}`)) : ok(m.result ?? {})));
      this.ws.send(JSON.stringify({ id: this.id, method, params }));
    });
  }
  async eval<T>(expression: string): Promise<T> {
    const r = (await this.send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true })) as { result: { value: T } };
    return r.result.value;
  }
  close() { this.ws.close(); }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

const chrome = findChrome();
const skip = !chrome && process.env.STAGE_NO_CHROME === "1";
if (!chrome && !skip) {
  throw new Error("layout test: no Chrome found. Set CHROME_BIN=/path/to/chrome, or STAGE_NO_CHROME=1 to skip this invariant on purpose.");
}
if (skip) console.warn("layout test SKIPPED: STAGE_NO_CHROME=1 and no Chrome found — the no-clipped-glyph invariant was not checked.");

describe.skipIf(skip)("in a real browser, nothing is ever painted partially clipped", () => {
  let server: Server;
  let origin: string;
  let proc: ChildProcess;
  let profile: string;
  let cdp: Cdp;

  beforeAll(async () => {
    // Serves the page only; brain is never polled (start() is not called).
    server = createServer(createStage({ log: () => {} }).handle);
    await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
    origin = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
    profile = mkdtempSync(join(tmpdir(), "gavel-stage-layout-"));
    proc = spawn(chrome!, [
      "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--disable-extensions",
      "--remote-debugging-port=0", `--user-data-dir=${profile}`, "about:blank",
    ], { stdio: "ignore" });
    let port = 0;
    for (let i = 0; i < 100 && !port; i++) {
      const f = join(profile, "DevToolsActivePort");
      if (existsSync(f)) port = Number(readFileSync(f, "utf8").split("\n")[0]);
      if (!port) await sleep(100);
    }
    if (!port) throw new Error("layout test: Chrome did not open its DevTools port");
    let pageWs = "";
    for (let i = 0; i < 50 && !pageWs; i++) {
      try {
        const list = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()) as { type: string; webSocketDebuggerUrl: string }[];
        pageWs = list.find((t) => t.type === "page")?.webSocketDebuggerUrl ?? "";
      } catch { /* not up yet */ }
      if (!pageWs) await sleep(100);
    }
    cdp = await Cdp.connect(pageWs);
    await cdp.send("Page.enable");
  }, 30_000);

  afterAll(async () => {
    cdp?.close();
    proc?.kill();
    await new Promise<void>((r) => (server ? server.close(() => r()) : r()));
    await sleep(200);
    if (profile) rmSync(profile, { recursive: true, force: true });
  });

  async function audit(query: string, w: number, h: number): Promise<Audit> {
    await cdp.send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: false });
    await cdp.send("Page.navigate", { url: `${origin}/${query}` });
    // The module paints the demo on load and the empty state on the first SSE error; either
    // way the stage has a mode once app.js has run.
    for (let i = 0; i < 50; i++) {
      const ready = await cdp.eval<boolean>(`document.readyState === "complete" && !!document.getElementById("stage")?.dataset.mode`);
      if (ready) break;
      await sleep(100);
    }
    await sleep(350); // one repaint tick, so clocks and bars have settled into their boxes
    return JSON.parse(await cdp.eval<string>(AUDIT)) as Audit;
  }

  for (const [w, h] of SIZES) {
    for (const q of SCENES) {
      it(`${w}×${h} ${q || "(no demo: the empty state)"}`, async () => {
        const a = await audit(q, w, h);
        expect(a.title).toBe("gavel-stage");
        expect(a.texts).toBeGreaterThan(0);
        expect(a.scroll[0]).toBe(a.scroll[1]);
        expect(a.scroll[2]).toBe(a.scroll[3]);
        expect(a.minFont).toBeGreaterThanOrEqual(18);
        expect(a.clipped, a.clipped.join("\n")).toEqual([]);
      }, 20_000);
    }
  }

  it("the notes column really did have to fold at 720p (the test can see a fold)", async () => {
    await audit("?demo=1&t=1400", 1280, 720);
    const folds = await cdp.eval<string[]>(`[...document.querySelectorAll("#notes li.more")].filter((li) => !li.hidden).map((li) => li.textContent)`);
    expect(folds.length).toBeGreaterThan(0);
    expect(folds.every((f) => /^\+\d+ more$/.test(f))).toBe(true);
  }, 20_000);
});
