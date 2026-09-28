/**
 * CORS for GET /state. Same-origin unless STAGE_CORS_ORIGINS lists the page's origin
 * (comma-separated, exact match, scheme included). `*` is still spellable, but must be.
 */
export function parseOrigins(raw: string | undefined): string[] {
  return (raw ?? "")
    .split(",")
    .map((s) => s.trim().replace(/\/$/, ""))
    .filter(Boolean);
}

export function corsHeaders(origin: string | undefined, allowed: string[]): Record<string, string> {
  if (!origin) return {};
  if (allowed.includes("*")) return { "access-control-allow-origin": "*" };
  if (!allowed.includes(origin)) return {};
  return { "access-control-allow-origin": origin, vary: "origin" };
}
