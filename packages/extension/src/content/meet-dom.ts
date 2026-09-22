// Reading the Google Meet pre-join screen. Same rules as `calendar-dom.ts`:
// accessible names and visible text first, fixture attributes as a fallback,
// everything sanitized, nothing guessed.

import { cleanMeetCode, cleanText, cleanTitle } from "../lib/sanitize.js";
import type { EventContext } from "../lib/types.js";
import { textOf } from "./dom.js";

const SEL = {
  joinButton: ['[data-gv="join"]'],
  title: ["[data-meeting-title]", '[data-gv="title"]', "h1"],
} as const;

function first(list: readonly string[]): HTMLElement | null {
  for (const s of list) {
    const el = document.querySelector(s);
    if (el instanceof HTMLElement) return el;
  }
  return null;
}

/** The pre-join screen is the one with a "Join now" / "Ask to join" button. */
export function joinButton(): HTMLElement | null {
  const known = first(SEL.joinButton);
  if (known) return known;
  return Array.from(document.querySelectorAll("button")).find((b) => /^(Join now|Ask to join)$/.test(cleanText(b.textContent).trim())) ?? null;
}

/** `https://meet.google.com/abc-defg-hij[?…]` → `abc-defg-hij`. The code is a
 *  whole path segment (on Meet, the only one; on the fixture, the last one). */
export function meetCodeFromUrl(href: string): string | null {
  let pathname: string;
  try {
    pathname = new URL(href).pathname;
  } catch {
    return null;
  }
  const segment = pathname.split("/").find((s) => /^[a-z]{3}-[a-z]{4}-[a-z]{3}$/.test(s));
  return cleanMeetCode(segment);
}

export function readMeet(): EventContext {
  const titleEl = first(SEL.title);
  const title = titleEl ? cleanTitle(titleEl.getAttribute("data-meeting-title") ?? textOf(titleEl)) : "";
  return {
    surface: "meet",
    eventId: null,
    meetCode: meetCodeFromUrl(location.href),
    // Meet shows the code itself as the heading when the event has no title.
    title: /^[a-z]{3}-[a-z]{4}-[a-z]{3}$/.test(title) ? "" : title,
    description: "",
    attendees: [],
    start: null,
    durationMinutes: null,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
  };
}
