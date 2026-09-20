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
const openConnections = new Set();
let heartbeatTimer = null;
let stageState = "idle";
let sceneGeneration = 0;

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
    }).catch((err) => console.debug("director heartbeat failed", err));
  }, 5000);
}

function closeSession() {
  sceneGeneration += 1;
  stopHeartbeat();
  for (const connection of openConnections) {
    try {
      connection.close();
    } catch (err) {
      // A connection can already be gone during teardown; retain a breadcrumb
      // without turning an idempotent close into a user-visible failure.
      console.debug("director connection was already closed", err);
    }
  }
  openConnections.clear();
  conn = null;
  currentToken = null;
  video.srcObject = null;
}

function joinSession(evt) {
  // Scene rotations are make-before-break. Keep the current MediaStream on
  // screen while the replacement performs its ~5s WebRTC startup, then close
  // every superseded connection after the first new media frame arrives.
  // Clearing the old video here would turn a healthy rotation into a black or
  // idle gap for viewers.
  const generation = ++sceneGeneration;
  currentToken = evt.token;
  setStatus(openConnections.size ? "changing scene" : "connecting");

  // Subscribe to both tracks, then mute the element. The endpoint streams
  // audio+video and rejects an offer that asks for video alone -- asking for
  // one track fails negotiation outright with "the offer is incompatible with
  // the media this endpoint streams", which means no Karen at all.
  //
  // The audio still must never reach the room: the model re-synthesises its own
  // voice from the audio we send it, and Karen is already being heard for real
  // in the Discord call, so playing it gave the room two Karens a beat apart --
  // that is what made her land as creepy rather than present. Muting the
  // element is what silences the second one. The stream is the picture of her
  // speaking; the Discord TTS is the speech.
  const nextConn = fal.realtime.open(wma(evt.endpointId), {
    receive: ["video", "audio"],
    onState: (state) => {
      if (generation === sceneGeneration && state === "live") setStatus("live");
    },
    onError: (err) => {
      if (generation === sceneGeneration) setStatus("error");
      console.error("director session error", err);
    },
    onMedia: (stream) => {
      if (generation !== sceneGeneration) {
        try {
          nextConn.close();
        } catch (err) {
          console.debug("superseded director connection was already closed", err);
        }
        openConnections.delete(nextConn);
        return;
      }
      video.srcObject = stream;
      // This is the mute that matters -- the audio track is always present, so
      // this is the only thing standing between the room and a second Karen.
      // Muted also means autoplay is not blocked.
      video.muted = true;
      video.play().catch(() => {
        // Autoplay was blocked — the click-to-start overlay is the recovery
        // path; leave it visible until the user interacts.
        if (overlay) overlay.hidden = false;
      });
      for (const connection of openConnections) {
        if (connection === nextConn) continue;
        try {
          connection.close();
        } catch (err) {
          console.debug("previous director connection was already closed", err);
        }
        openConnections.delete(connection);
      }
    },
  });
  conn = nextConn;
  openConnections.add(nextConn);

  nextConn.send({
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
    if (msg.origin !== window.location.origin) {
      console.warn("ignored director event from unexpected origin", msg.origin);
      return;
    }
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
    video.play().catch((err) => console.debug("video still could not start after interaction", err));
  });
}

connectEvents();
