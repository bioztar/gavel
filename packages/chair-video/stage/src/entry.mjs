// The stage page: renders Karen full-screen for the projector, joins the
// Director WebRTC session, and speaks whatever chair-video tells it to over
// SSE. It never holds FAL_KEY — every fal request goes through chair-video's
// /director/fal-proxy, gated by a per-session token this page gets from the
// same SSE stream that tells it to start.
//
// Real API confirmed against fal in the Phase 0 spike (see README): one data
// channel, `configure` first, `prompt` for each utterance with a
// strictly-increasing `prompt_version`, media arrives as a MediaStream via
// onMedia. See wma.js's own docs: messages sent before the data channel opens
// are lost, and the channel can die while ICE still reports "connected" — so
// this page tracks its own "am I actually receiving media" state rather than
// trusting the peer connection's ICE status alone.
import { fal } from "@fal-ai/client";
import { wma } from "@fal-ai/client/realtime/wma";

const video = document.getElementById("stage-video");
const statusEl = document.getElementById("stage-status");
const overlay = document.getElementById("start-overlay");

let currentToken = null;
let conn = null;
let heartbeatTimer = null;
let stageState = "idle";

fal.config({
  proxyUrl: `${window.location.origin}/director/fal-proxy`,
  requestMiddleware: (config) =>
    Promise.resolve({
      ...config,
      headers: { ...(config.headers || {}), "x-director-token": currentToken || "" },
    }),
});

function setStatus(text) {
  stageState = text;
  if (statusEl) statusEl.textContent = text;
}

function stopHeartbeat() {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }
}

function startHeartbeat(token) {
  stopHeartbeat();
  heartbeatTimer = setInterval(() => {
    fetch("/director/heartbeat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ token, state: stageState }),
    }).catch(() => {});
  }, 5000);
}

function closeSession() {
  stopHeartbeat();
  if (conn) {
    try {
      conn.close();
    } catch {
      // already gone
    }
    conn = null;
  }
  currentToken = null;
  video.srcObject = null;
}

function joinSession(evt) {
  closeSession();
  currentToken = evt.token;
  setStatus("connecting");

  conn = fal.realtime.open(wma(evt.endpointId), {
    receive: ["video", "audio"],
    onState: (state) => {
      if (state === "live") setStatus("live");
    },
    onError: (err) => {
      setStatus("error");
      console.error("director session error", err);
    },
    onMedia: (stream) => {
      video.srcObject = stream;
      video.play().catch(() => {
        // Autoplay was blocked — the click-to-start overlay is the recovery
        // path; leave it visible until the user interacts.
        if (overlay) overlay.hidden = false;
      });
    },
  });

  conn.send({
    type: "configure",
    protocol_version: 1,
    prompt_version: evt.promptVersion,
    prompt: evt.prompt,
    resolution: evt.resolution,
    aspect_ratio: evt.aspectRatio,
  });

  startHeartbeat(evt.token);
}

function handleEvent(evt) {
  if (evt.type === "start") {
    joinSession(evt);
  } else if (evt.type === "speak") {
    if (conn) {
      conn.send({ type: "prompt", prompt_version: evt.promptVersion, audio_url: evt.audioUrl, audio_behavior: "replace" });
    }
  } else if (evt.type === "stop") {
    closeSession();
    setStatus("idle");
  } else if (evt.type === "idle") {
    setStatus("idle");
  }
}

function connectEvents() {
  const source = new EventSource("/director/events");
  source.onmessage = (msg) => {
    try {
      handleEvent(JSON.parse(msg.data));
    } catch (err) {
      console.error("bad director event", err, msg.data);
    }
  };
  source.onerror = () => {
    // The browser's EventSource auto-reconnects; nothing to do but reflect it.
    setStatus("reconnecting");
  };
}

// Sessions are billed per second — a page that silently closes without this
// firing is exactly the leak the heartbeat timeout on the Python side exists
// to detect, but closing cleanly on a normal navigation is free.
window.addEventListener("pagehide", closeSession);
window.addEventListener("beforeunload", closeSession);

if (overlay) {
  overlay.addEventListener("click", () => {
    overlay.hidden = true;
    video.play().catch(() => {});
  });
}

connectEvents();
