// @ts-check
/**
 * The page. One SSE stream in (`GET /events`), a Link record, and a paint a few times a
 * second so the clocks move between frames. No polling, no WebSocket, no fetch: if the
 * stream drops, EventSource reconnects itself and the last-known state stays on screen
 * with a quiet marker.
 */
import { reduce } from "./board.js";
import { paint } from "./render.js";
import { runDemo } from "./demo.js";

/** @type {import("./board.js").Link} */
const link = { state: null, receivedAt: 0, connected: false, brainOk: false };

const params = new URLSearchParams(location.search);
if (params.get("demo")) {
  runDemo(link, params);
} else {
  connect();
}

function connect() {
  const es = new EventSource("/events");
  es.onopen = () => {
    link.connected = true;
  };
  es.addEventListener("state", (ev) => {
    try {
      const frame = JSON.parse(/** @type {MessageEvent<string>} */ (ev).data);
      link.state = frame.state ?? null;
      link.brainOk = !!frame.brain;
      link.receivedAt = Date.now();
      link.connected = true;
    } catch {
      // A torn frame is not worth a blank screen; the next one will be whole.
    }
  });
  es.addEventListener("link", (ev) => {
    try {
      link.brainOk = !!JSON.parse(/** @type {MessageEvent<string>} */ (ev).data).brain;
    } catch {
      /* ignore */
    }
  });
  es.onerror = () => {
    link.connected = false;
    // EventSource retries on its own while CONNECTING; CLOSED means it gave up (e.g. the
    // server answered non-2xx during a redeploy), so start over after a moment.
    if (es.readyState === EventSource.CLOSED) setTimeout(connect, 2000);
  };
}

const frame = () => paint(reduce(link, Date.now()));
frame();
setInterval(frame, 250);
