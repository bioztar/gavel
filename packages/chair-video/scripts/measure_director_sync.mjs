// Measures the one number that decides how Karen's face is used on stage:
// how long after chair-video is told to speak do her lips actually move in the
// live Director WebRTC stream.
//
// The README's other latency table is for *file-based* lipsync models and does
// not transfer to this path — nothing there round-trips through a live WebRTC
// session. This script measures the live path end to end, in a real browser,
// because the browser is the thing that holds the session: chair-video only
// emits an SSE `speak` event, and the page turns that into a data-channel
// `prompt`. No browser, no measurement.
//
// The number is decomposed on purpose:
//
//   upload   POST /director/speak -> response (chair-video uploading the wav to fal)
//   dispatch response -> SSE `speak` received in the page
//   render   SSE receipt -> first frame whose mouth region actually moves
//
// A single end-to-end figure cannot tell you whether the fix is "delay the
// Discord audio" (render is the cost, not fixable, only compensable) or "stop
// round-tripping the audio through an upload" (upload is the cost, and it is
// ours). Hence three columns.
//
// Needs playwright + its chromium. This is a measurement tool, not part of the
// service, so it is deliberately NOT a dependency of any package.json — a
// browser download has no business in the image build the night before a
// freeze. Run it with NODE_PATH pointed at any playwright install:
//
//   cd /tmp && npm i playwright && npx playwright install chromium
//   PLAYWRIGHT_MODULE=/tmp/node_modules/playwright node \
//     <repo>/packages/chair-video/scripts/measure_director_sync.mjs
//
// PLAYWRIGHT_MODULE exists because ESM resolves a bare import by walking up
// from *this file's* directory -- not the cwd, and not NODE_PATH. With no
// node_modules anywhere above a Python package, the only ways in are a path
// and a dynamic import. Unset, it falls back to a plain "playwright" import
// for anyone who does have it installed alongside.
//
// Sessions are billed per second, so the session is stopped in a `finally` and
// the stop is verified against /healthz. If this script is killed mid-run the
// service's own idle sweeper closes the session within ~120s.

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const HERE = dirname(fileURLToPath(import.meta.url));
const LOCAL_CHAIR_VIDEO_HOST = "127.0.0.1";
const LOCAL_CHAIR_VIDEO = `http://${LOCAL_CHAIR_VIDEO_HOST}:8791`;
const BASE = process.env.CHAIR_VIDEO_URL || LOCAL_CHAIR_VIDEO;
const OUT = process.env.SYNC_OUT_DIR || "/tmp/director-sync";
const PERSONA = process.env.SYNC_PERSONA || "formal";
// 20 Hz sampling. The buckets this feeds (300ms / 1-3s / 10s+) do not justify
// anything finer, and a faster loop steals time from video decode.
const SAMPLE_MS = 50;
const BASELINE_MS = 3000;
const SETTLE_MS = 15000; // between utterances: lets the previous one finish, stays under the 120s idle sweep
const ONSET_SIGMA = 6;
const ONSET_RUN = 4; // consecutive samples over threshold before we call it

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function post(path, body) {
  const t0 = Date.now();
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const json = await res.json().catch((err) => {
    console.warn(`POST ${path} returned a non-JSON response`, err);
    return {};
  });
  if (!res.ok) throw new Error(`POST ${path} -> ${res.status} ${JSON.stringify(json)}`);
  return { t0, t1: Date.now(), json };
}

// Everything the page does lives here: patch EventSource to timestamp `speak`
// on arrival, and run one continuous sampler that scores how much the mouth
// region changed between frames. Injected rather than edited into entry.mjs —
// the shipped bundle stays exactly as deployed, which is the thing under test.
const PAGE_INIT = ({ sampleMs }) => {
  window.__sync = { speaks: [], samples: [], sseOpen: false, frames: [] };
  const Native = window.EventSource;
  window.EventSource = function (url, opts) {
    const es = new Native(url, opts);
    const expectedOrigin = new URL(url, window.location.href).origin;
    es.addEventListener("open", () => { window.__sync.sseOpen = true; });
    es.addEventListener("message", (msg) => {
      if (msg.origin !== expectedOrigin) {
        console.warn("ignored measurement event from unexpected origin", msg.origin);
        return;
      }
      try {
        const evt = JSON.parse(msg.data);
        if (evt.type === "speak") window.__sync.speaks.push(Date.now());
      } catch (err) {
        // The page's own handler reports bad events too, but this injected
        // listener must still account for its own parse failure.
        console.debug("measurement listener ignored a bad director event", err);
      }
    });
    return es;
  };
  window.EventSource.prototype = Native.prototype;

  window.__startSampler = () => {
    const video = document.getElementById("stage-video");
    const W = 160, H = 120;
    const canvas = document.createElement("canvas");
    canvas.width = W; canvas.height = H;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    // Head-and-shoulders framing, centred: the mouth sits in the middle
    // horizontally and just below centre vertically. Verified against a saved
    // frame before trusting any number out of this.
    const x0 = Math.floor(W * 0.36), x1 = Math.floor(W * 0.64);
    const y0 = Math.floor(H * 0.55), y1 = Math.floor(H * 0.80);
    let prev = null;
    setInterval(() => {
      if (!video.videoWidth) return;
      ctx.drawImage(video, 0, 0, W, H);
      const px = ctx.getImageData(x0, y0, x1 - x0, y1 - y0).data;
      if (prev && prev.length === px.length) {
        let sum = 0;
        for (let i = 0; i < px.length; i += 4) sum += Math.abs(px[i] - prev[i]);
        window.__sync.samples.push({ t: Date.now(), d: sum / (px.length / 4) });
        if (window.__sync.samples.length > 4000) window.__sync.samples.shift();
      }
      prev = px.slice(0);
      // Small ring of recent frames so an onset can be eyeballed afterwards —
      // `audio_behavior: "replace"` can splice the stream, and a splice is a
      // big frame diff that is not lips.
      window.__sync.frames.push({ t: Date.now(), png: canvas.toDataURL("image/png") });
      if (window.__sync.frames.length > 40) window.__sync.frames.shift();
    }, sampleMs);
  };
};

// Baseline from the quiet window before the request went out; onset is the
// first of ONSET_RUN consecutive samples above mean + ONSET_SIGMA*sd.
function onsetAfter(samples, tRef, baselineFrom, baselineTo) {
  const base = samples.filter((s) => s.t >= baselineFrom && s.t < baselineTo).map((s) => s.d);
  if (base.length < 10) return { error: `only ${base.length} baseline samples` };
  const mean = base.reduce((a, b) => a + b, 0) / base.length;
  const sd = Math.sqrt(base.reduce((a, b) => a + (b - mean) ** 2, 0) / base.length);
  const threshold = mean + ONSET_SIGMA * sd;
  const after = samples.filter((s) => s.t >= tRef);
  for (let i = 0; i + ONSET_RUN <= after.length; i++) {
    if (after.slice(i, i + ONSET_RUN).every((s) => s.d > threshold)) {
      return { t: after[i].t, mean, sd, threshold, peak: Math.max(...after.slice(i, i + ONSET_RUN).map((s) => s.d)) };
    }
  }
  return { error: "no onset", mean, sd, threshold, max: after.length ? Math.max(...after.map((s) => s.d)) : null };
}

function saveFrames(frames, around, label) {
  const near = frames.filter((f) => Math.abs(f.t - around) < 400).slice(0, 8);
  near.forEach((f, i) => {
    const b64 = f.png.split(",")[1];
    writeFileSync(join(OUT, `${label}-${i}-${f.t - around}ms.png`), Buffer.from(b64, "base64"));
  });
  return near.length;
}

const run = async () => {
  mkdirSync(OUT, { recursive: true });
  // A directory is not an importable ES module, so point at its entry file
  // when given a bare package directory.
  const mod = process.env.PLAYWRIGHT_MODULE
    ? (process.env.PLAYWRIGHT_MODULE.endsWith(".js")
        ? process.env.PLAYWRIGHT_MODULE
        : `${process.env.PLAYWRIGHT_MODULE}/index.js`)
    : "playwright";
  // playwright ships CommonJS: a dynamic import hands back a namespace whose
  // exports sit under .default, so go through createRequire instead of
  // guessing which shape this node version produces.
  const { chromium } = createRequire(import.meta.url)(mod);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  await page.addInitScript(PAGE_INIT, { sampleMs: SAMPLE_MS }).catch((err) => {
    throw new Error("could not install the measurement hooks", { cause: err });
  });
  page.on("console", (m) => { if (m.type() === "error") console.error("  page error:", m.text()); });

  const results = [];
  try {
    // Page first, then start. /director/events pushes on transition, so a page
    // that connects after the session has started never sees `start` and never
    // joins — it would sit at idle looking exactly like a broken measurement.
    await page.goto(`${BASE}/karen-video`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => window.__sync?.sseOpen === true, null, { timeout: 15000 });
    console.log("SSE open");

    const started = await post("/director/session/start", { persona: PERSONA }).catch((err) => {
      throw new Error("could not start the measured director session", { cause: err });
    });
    console.log("session", started.json.sessionId, "persona", PERSONA);

    // Do not time anything until frames are genuinely arriving: "live" on the
    // connection and zero decoded frames look identical from the outside.
    await page.waitForFunction(
      () => {
        const v = document.getElementById("stage-video");
        if (!v || !v.videoWidth) return false;
        const q = v.getVideoPlaybackQuality?.();
        if (!q) return true;
        const prev = window.__frameProbe ?? -1;
        window.__frameProbe = q.totalVideoFrames;
        return q.totalVideoFrames > 0 && q.totalVideoFrames > prev;
      },
      null,
      { timeout: 90000, polling: 500 },
    );
    const dims = await page.evaluate(() => {
      const v = document.getElementById("stage-video");
      return { w: v.videoWidth, h: v.videoHeight };
    });
    console.log(`media live ${dims.w}x${dims.h}`);
    await page.evaluate(() => window.__startSampler());

    const utterances = [
      ["utterance-3s.wav", "3s"],
      ["utterance-3s.wav", "3s"],
      ["utterance-3s.wav", "3s"],
      ["utterance-8s.wav", "8s"],
      ["utterance-8s.wav", "8s"],
      ["utterance-8s.wav", "8s"],
    ];

    for (const [file, label] of utterances) {
      const n = results.length + 1;
      const audio = readFileSync(join(HERE, "fixtures", file)).toString("base64");
      const quietFrom = Date.now();
      await sleep(BASELINE_MS);
      // Snapshot the counter BEFORE the request. The SSE event can land while
      // the POST's own response is still in flight, and reading the counter
      // afterwards would already include it -- then waiting for "one more"
      // waits for an event that has already happened.
      const speaksBefore = await page.evaluate(() => window.__sync.speaks.length);
      const before = await post("/director/speak", { audioBase64: audio, format: "wav", persona: PERSONA });
      await page.waitForFunction((k) => window.__sync.speaks.length > k, speaksBefore, { timeout: 20000 });
      const tSse = await page.evaluate(() => window.__sync.speaks.at(-1));
      // Give the render every chance before declaring no onset: 20s is well
      // past the point where sync would be a question worth asking.
      await sleep(20000).catch((err) => {
        throw new Error("render-observation delay failed", { cause: err });
      });
      const samples = await page.evaluate(() => window.__sync.samples);
      const onset = onsetAfter(samples, tSse, quietFrom, before.t0);
      const frames = await page.evaluate(() => window.__sync.frames);
      const saved = onset.t ? saveFrames(frames, onset.t, `run${n}-${label}`) : 0;
      const row = {
        run: n,
        utterance: label,
        cold: n === 1,
        uploadMs: before.t1 - before.t0,
        dispatchMs: tSse - before.t1,
        renderMs: onset.t ? onset.t - tSse : null,
        totalMs: onset.t ? onset.t - before.t0 : null,
        threshold: onset.threshold?.toFixed(3),
        peak: onset.peak?.toFixed(3) ?? onset.max?.toFixed(3),
        error: onset.error ?? null,
        framesSaved: saved,
      };
      results.push(row);
      console.log(
        `run ${n} ${label}${row.cold ? " (cold)" : ""}: upload ${row.uploadMs}ms  ` +
          `dispatch ${row.dispatchMs}ms  render ${row.renderMs ?? "—"}ms  ` +
          `total ${row.totalMs ?? "—"}ms${row.error ? `  [${row.error}]` : ""}`,
      );
      await sleep(SETTLE_MS).catch((err) => {
        throw new Error("inter-utterance settling delay failed", { cause: err });
      });
    }

    // The only thing that proves the threshold: she blinks and breathes the
    // whole time, so a detector that fires on that measures nothing.
    console.log("null control: 12s with no speak");
    const controlFrom = Date.now();
    await sleep(12000);
    const samples = await page.evaluate(() => window.__sync.samples);
    const control = onsetAfter(samples, controlFrom + BASELINE_MS, controlFrom, controlFrom + BASELINE_MS);
    console.log(
      control.error
        ? `null control PASS (no onset; max ${control.max?.toFixed(3)} vs threshold ${control.threshold?.toFixed(3)})`
        : `null control FAIL — fired at +${control.t - controlFrom}ms on idle motion`,
    );
    writeFileSync(join(OUT, "results.json"), JSON.stringify({ results, control }, null, 2));
  } finally {
    await post("/director/session/stop", {}).catch((e) => console.error("stop failed:", e.message));
    await browser.close().catch((err) => {
      console.error("browser cleanup failed", err);
    });
    const health = await fetch(`${BASE}/healthz`).then((r) => r.json()).catch(() => ({}));
    console.log("after stop, session active:", health.director?.active ?? health.active ?? "unknown");
  }
};

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
