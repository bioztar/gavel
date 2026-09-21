// Everything read out of the page is untrusted: Google's DOM, a colleague's
// event description, a guest chip whose label came from another org's
// directory. Nothing leaves the content script or reaches a render call
// without passing through here. Rendering itself is `textContent` only — see
// `panel.ts` — so this is the second wall, not the only one.

const MAX_TITLE = 300;
const MAX_TEXT = 8000;
const MAX_NAME = 120;
const MAX_LINE = 400;
const MAX_ATTENDEES = 200;

/** Drop control characters (except tab / newline), bidi overrides and
 *  zero-width characters, and cap length. Keeps the text readable, keeps a
 *  pasted `\u202e` from flipping the confirm table. */
export function cleanText(raw: unknown, max = MAX_TEXT): string {
  if (typeof raw !== "string") return "";
  return raw
    .replace(/\r\n?/g, "\n")
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, "")
    .replace(/[\u200b-\u200f\u2028-\u202e\u2060-\u2064\ufeff]/g, "")
    .slice(0, max);
}

export function cleanLine(raw: unknown, max = MAX_LINE): string {
  return cleanText(raw, max).replace(/\s+/g, " ").trim();
}

export function cleanTitle(raw: unknown): string {
  return cleanLine(raw, MAX_TITLE);
}

export function cleanName(raw: unknown): string {
  return cleanLine(raw, MAX_NAME);
}

// Deliberately strict — display strings with angle brackets, spaces or
// quotes are not addresses, whatever the chip's label says.
const EMAIL = /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/;

/** A lower-cased address, or null when the string is not one. */
export function cleanEmail(raw: unknown): string | null {
  const s = cleanLine(raw, 254).toLowerCase();
  return EMAIL.test(s) ? s : null;
}

/** "Name <email>" / "email" → a person; the local part stands in for a
 *  missing name, the same convention as `ics_parser._attendee_name`. */
export function personFrom(nameRaw: unknown, emailRaw: unknown): { name: string; email: string } | null {
  const email = cleanEmail(emailRaw);
  if (!email) return null;
  let name = cleanName(nameRaw);
  if (!name || name.toLowerCase() === email) {
    name = email
      .split("@")[0]!
      .replace(/[._]/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }
  return { name, email };
}

export function dedupePeople<T extends { email: string }>(people: T[]): T[] {
  const seen = new Set<string>();
  const out: T[] = [];
  for (const p of people) {
    if (seen.has(p.email)) continue;
    seen.add(p.email);
    out.push(p);
    if (out.length >= MAX_ATTENDEES) break;
  }
  return out;
}

/** A whole positive integer from user-typed text, else null. */
export function cleanMinutes(raw: unknown): number | null {
  const s = cleanLine(raw, 8);
  if (!/^\d{1,4}$/.test(s)) return null;
  const n = Number(s);
  return n > 0 ? n : null;
}

/** An https URL on an allowed host, else null. Used before any link read
 *  from a server response is put into a `href`. */
export function cleanHttpUrl(raw: unknown, allowInsecureLocalhost = false): string | null {
  const s = cleanLine(raw, 2048);
  let url: URL;
  try {
    url = new URL(s);
  } catch {
    return null;
  }
  if (url.protocol === "https:") return url.toString();
  if (allowInsecureLocalhost && url.protocol === "http:" && /^(localhost|127\.0\.0\.1)$/.test(url.hostname)) {
    return url.toString();
  }
  return null;
}

/** Google Meet codes are exactly `xxx-xxxx-xxx`, lower-case letters. */
export function cleanMeetCode(raw: unknown): string | null {
  const s = cleanLine(raw, 20).toLowerCase();
  return /^[a-z]{3}-[a-z]{4}-[a-z]{3}$/.test(s) ? s : null;
}

/** Google Calendar event ids are base32hex (their own rule), with an
 *  `_<timestamp>` suffix on an instance of a recurring event. */
export function cleanEventId(raw: unknown): string | null {
  const s = cleanLine(raw, 1024);
  return /^[A-Za-z0-9_-]{5,1024}$/.test(s) ? s : null;
}
