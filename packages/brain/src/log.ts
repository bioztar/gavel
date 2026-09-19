/** One-line structured logs: `HH:MM:SS.mmm level event {json}`. */
type Fields = Record<string, unknown>;

let clock: () => number = Date.now;
let quiet = false;

function line(level: string, event: string, fields?: Fields): void {
  if (quiet && level === "debug") return;
  const ts = new Date(clock()).toISOString().slice(11, 23);
  const extra = fields && Object.keys(fields).length ? ` ${JSON.stringify(fields)}` : "";
  const out = `${ts} ${level.padEnd(5)} ${event}${extra}`;
  if (level === "warn" || level === "error") console.error(out);
  else console.log(out);
}

export const log = {
  debug: (event: string, fields?: Fields) => line("debug", event, fields),
  info: (event: string, fields?: Fields) => line("info", event, fields),
  warn: (event: string, fields?: Fields) => line("warn", event, fields),
  error: (event: string, fields?: Fields) => line("error", event, fields),
  /** Replay runs on a fake clock; logs should show meeting time, not wall time. */
  useClock(fn: () => number) {
    clock = fn;
  },
  setQuiet(value: boolean) {
    quiet = value;
  },
};
