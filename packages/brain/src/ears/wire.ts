/**
 * The WebSocket to ears (CONTRACT §2). Reconnects forever with backoff; ears re-announces
 * `ready` / `participants` / `session.started` on every connect, so nothing is lost.
 */
import { EventEmitter } from "node:events";
import WebSocket from "ws";
import type { BrainFrame, EarsFrame } from "../contract/frames";
import { parseEarsFrame } from "../contract/frames";
import { log } from "../log";

export interface Wire {
  readonly connected: boolean;
  send(frame: BrainFrame): boolean;
}

export class EarsWire extends EventEmitter<{ frame: [EarsFrame]; connected: []; disconnected: [] }> implements Wire {
  private ws: WebSocket | null = null;
  private backoffMs = 500;
  private closed = false;

  constructor(private url: string) {
    super();
  }

  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  start(): void {
    if (this.closed) return;
    const ws = new WebSocket(this.url);
    this.ws = ws;
    ws.on("open", () => {
      this.backoffMs = 500;
      log.info("wire.connected", { url: this.url });
      this.emit("connected");
    });
    ws.on("message", (data) => {
      let raw: unknown;
      try {
        raw = JSON.parse(data.toString());
      } catch {
        return;
      }
      const frame = parseEarsFrame(raw);
      if (frame) this.emit("frame", frame);
    });
    ws.on("close", () => {
      if (this.ws === ws) this.ws = null;
      this.emit("disconnected");
      if (this.closed) return;
      log.warn("wire.disconnected", { retryInMs: this.backoffMs });
      setTimeout(() => this.start(), this.backoffMs);
      this.backoffMs = Math.min(this.backoffMs * 2, 5000);
    });
    ws.on("error", (err) => log.debug("wire.error", { error: String(err) }));
  }

  send(frame: BrainFrame): boolean {
    if (!this.connected || !this.ws) return false;
    this.ws.send(JSON.stringify(frame));
    return true;
  }

  close(): void {
    this.closed = true;
    this.ws?.close();
  }
}
