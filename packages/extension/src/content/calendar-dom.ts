// Reading the Google Calendar event editor, and writing back into it.
//
// Google's editor has no public DOM contract. Every lookup here is a list of
// selectors tried in order — accessible names first (`aria-label`), which
// Google keeps far more stable than class names — and every read falls back to
// "unknown" rather than guessing. The fixture in `mock/fixtures/calendar.html`
// uses the same accessible names, so a selector that works there is at least
// the *intended* shape; `README.md` says how to re-verify against the live
// editor when Google moves something.
//
// Everything returned is passed through `sanitize.ts`. The page is untrusted.

import { cleanEventId, cleanLine, cleanText, cleanTitle, dedupePeople, personFrom } from "../lib/sanitize.js";
import type { EventContext, Person } from "../lib/types.js";
import { linesOf, textOf } from "./dom.js";

const SEL = {
  editor: ['[role="main"] form', '[role="main"]', '[role="dialog"]'],
  title: ['input[aria-label="Add title"]', 'input[aria-label="Title"]', 'input[aria-label="Add title and time"]', '[data-gv="title"]'],
  description: ['[aria-label="Description"][contenteditable="true"]', '[aria-label="Description"]', '[role="textbox"][aria-multiline="true"]', '[data-gv="description"]'],
  guestChip: ["[data-email]", "[data-gv-guest]"],
  guestInput: ['input[aria-label="Guests"]', 'input[aria-label="Add guests"]', 'input[placeholder="Add guests"]', '[data-gv="guests"]'],
  startDate: ['input[aria-label="Start date"]', '[data-gv="start-date"]'],
  startTime: ['input[aria-label="Start time"]', '[data-gv="start-time"]'],
  endDate: ['input[aria-label="End date"]', '[data-gv="end-date"]'],
  endTime: ['input[aria-label="End time"]', '[data-gv="end-time"]'],
  save: ['button[aria-label="Save"]', '[data-gv="save"]'],
} as const;

function first(list: readonly string[], scope: ParentNode = document): HTMLElement | null {
  for (const s of list) {
    const el = scope.querySelector(s);
    if (el instanceof HTMLElement) return el;
  }
  return null;
}

function all(list: readonly string[], scope: ParentNode = document): HTMLElement[] {
  for (const s of list) {
    const found = Array.from(scope.querySelectorAll(s)).filter((e): e is HTMLElement => e instanceof HTMLElement);
    if (found.length) return found;
  }
  return [];
}

/** The editor is open when its title field is on the page. */
export function editorRoot(): HTMLElement | null {
  const title = first(SEL.title);
  if (!title) return null;
  return title.closest<HTMLElement>('[role="main"], [role="dialog"], form') ?? document.body;
}

export function saveButton(): HTMLElement | null {
  const root = editorRoot();
  if (!root) return null;
  const byLabel = first(SEL.save, root);
  if (byLabel) return byLabel;
  return Array.from(root.querySelectorAll("button")).find((b) => cleanLine(b.textContent) === "Save") ?? null;
}

/** `/calendar/u/0/r/eventedit/<base64("<eventId> <calendar>")>`. A new event
 *  has no segment there (`/eventedit?…`), and no id until the host saves. */
export function eventIdFromUrl(href: string): string | null {
  const m = new URL(href).pathname.match(/\/eventedit\/([^/?#]+)/);
  if (!m?.[1]) return null;
  let decoded: string;
  try {
    decoded = atob(m[1].replace(/-/g, "+").replace(/_/g, "/"));
  } catch {
    return null;
  }
  return cleanEventId(decoded.split(/\s+/)[0]);
}

export function readGuests(root: ParentNode): Person[] {
  const people: Person[] = [];
  for (const chip of all(SEL.guestChip, root)) {
    const email = chip.getAttribute("data-email") ?? chip.getAttribute("data-gv-guest") ?? "";
    const name = chip.getAttribute("data-name") ?? chip.getAttribute("aria-label") ?? chip.textContent ?? "";
    // Chip labels read "Ana Ruiz, Optional" / "Ana Ruiz – organizer"; the name is
    // the first clause.
    const p = personFrom(cleanLine(name).split(/[,\u2013\u2014(]/)[0], email);
    if (p) people.push(p);
  }
  return dedupePeople(people);
}

const TIME = /^\s*(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)?\s*$/i;

/** "2:00pm" / "14:00" → minutes since midnight, or null. */
export function parseClock(raw: string): number | null {
  const m = TIME.exec(raw);
  if (!m) return null;
  let h = Number(m[1]);
  const min = Number(m[2] ?? "0");
  const ap = m[3]?.toLowerCase().replace(/\./g, "");
  if (ap === "pm" && h < 12) h += 12;
  if (ap === "am" && h === 12) h = 0;
  if (h > 23 || min > 59) return null;
  return h * 60 + min;
}

/** A local date string as Google prints it ("Thursday, September 24") plus a
 *  clock → ISO with the page's offset. Year-less dates take the nearest year. */
export function combine(dateRaw: string, clockRaw: string, now = new Date()): Date | null {
  const clock = parseClock(clockRaw);
  if (clock === null) return null;
  const withYear = /\d{4}/.test(dateRaw) ? dateRaw : `${dateRaw} ${now.getFullYear()}`;
  const day = new Date(withYear.replace(/^[A-Za-z]+,\s*/, ""));
  if (Number.isNaN(day.getTime())) return null;
  day.setHours(Math.floor(clock / 60), clock % 60, 0, 0);
  // A year-less date already gone by more than a month is probably next year.
  if (!/\d{4}/.test(dateRaw) && day.getTime() < now.getTime() - 30 * 86_400_000) day.setFullYear(day.getFullYear() + 1);
  return day;
}

export function readTimes(root: ParentNode): { start: string | null; durationMinutes: number | null } {
  const sd = textOf(first(SEL.startDate, root));
  const st = textOf(first(SEL.startTime, root));
  const ed = textOf(first(SEL.endDate, root)) || sd;
  const et = textOf(first(SEL.endTime, root));
  const start = combine(cleanLine(sd), cleanLine(st));
  const end = combine(cleanLine(ed), cleanLine(et));
  if (!start) return { start: null, durationMinutes: null };
  let duration: number | null = null;
  if (end) {
    const mins = Math.round((end.getTime() - start.getTime()) / 60_000);
    duration = mins > 0 && mins <= 24 * 60 ? mins : null;
  }
  return { start: isoWithOffset(start), durationMinutes: duration };
}

export function isoWithOffset(d: Date): string {
  const pad = (n: number): string => String(Math.abs(n)).padStart(2, "0");
  const off = -d.getTimezoneOffset();
  const sign = off >= 0 ? "+" : "-";
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:00${sign}${pad(Math.floor(off / 60))}:${pad(off % 60)}`;
}

export function readEvent(): EventContext {
  const root = editorRoot() ?? document.body;
  const { start, durationMinutes } = readTimes(root);
  return {
    surface: "calendar",
    eventId: eventIdFromUrl(location.href),
    meetCode: null,
    title: cleanTitle(textOf(first(SEL.title, root))),
    description: cleanText(linesOf(first(SEL.description, root))),
    attendees: readGuests(root),
    start,
    durationMinutes,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
  };
}

/** Put text into the description field so the host's Save carries it. Prefers
 *  the editing command path (Google listens for it) and falls back to setting
 *  the content and firing `input`. Returns whether a field was found. */
export function writeDescription(text: string): boolean {
  const root = editorRoot() ?? document.body;
  const field = first(SEL.description, root);
  if (!field) return false;
  if (field instanceof HTMLTextAreaElement || field instanceof HTMLInputElement) {
    field.value = text;
    field.dispatchEvent(new Event("input", { bubbles: true }));
    field.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }
  field.focus();
  const sel = window.getSelection();
  if (sel) {
    sel.removeAllRanges();
    const range = document.createRange();
    range.selectNodeContents(field);
    sel.addRange(range);
  }
  let ok = false;
  try {
    ok = document.execCommand("insertText", false, text);
  } catch {
    ok = false;
  }
  if (!ok) {
    field.textContent = "";
    for (const [i, line] of text.split("\n").entries()) {
      if (i > 0) field.append(document.createElement("br"));
      field.append(document.createTextNode(line));
    }
    field.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: text }));
  }
  return true;
}

/** Type the bot's address into the guest box and press Enter, as a person
 *  would. Returns whether the box was found; whether Google accepted the chip
 *  is visible to the host in the guest list. */
export function addGuest(email: string): boolean {
  const root = editorRoot() ?? document.body;
  if (readGuests(root).some((p) => p.email === email.toLowerCase())) return true;
  const input = first(SEL.guestInput, root);
  if (!(input instanceof HTMLInputElement)) return false;
  input.focus();
  input.value = email;
  input.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: email }));
  for (const type of ["keydown", "keypress", "keyup"] as const) {
    input.dispatchEvent(new KeyboardEvent(type, { key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true }));
  }
  return true;
}
