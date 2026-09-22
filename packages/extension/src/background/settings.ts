// Non-secret configuration, set on the options page. `chrome.storage.local` is
// right for this: it is a URL and a flag, not a credential — tokens go through
// `session.ts` and `chrome.storage.session` only.

export interface Settings {
  /** Origin of the `packages/calendar` deployment, e.g. `https://gavel.example.com`. */
  serverUrl: string;
  /** Dev builds only: skip Google sign-in and send the mock a fixed bearer.
   *  Ignored (always false) in a production build. */
  mockAuth: boolean;
}

const DEV_DEFAULTS: Settings = { serverUrl: "http://localhost:8790", mockAuth: true };
const PROD_DEFAULTS: Settings = { serverUrl: "", mockAuth: false };

export const DEFAULTS: Settings = __DEV_BUILD__ ? DEV_DEFAULTS : PROD_DEFAULTS;

export async function loadSettings(): Promise<Settings> {
  const stored = (await chrome.storage.local.get(["serverUrl", "mockAuth"])) as Partial<Settings>;
  const serverUrl = typeof stored.serverUrl === "string" && stored.serverUrl ? stored.serverUrl : DEFAULTS.serverUrl;
  const mockAuth = __DEV_BUILD__ ? (typeof stored.mockAuth === "boolean" ? stored.mockAuth : DEFAULTS.mockAuth) : false;
  return { serverUrl, mockAuth };
}

export async function saveSettings(next: Partial<Settings>): Promise<void> {
  await chrome.storage.local.set(next);
}
