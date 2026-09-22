// Sign-in, and where the resulting tokens live.
//
// Two tokens exist and both stay inside the service worker:
//   1. the Google access token (scopes in manifest `oauth2.scopes`), obtained by
//      `chrome.identity.getAuthToken` on Chrome, or by
//      `chrome.identity.launchWebAuthFlow` (implicit grant, `response_type=token`,
//      client id only — no secret exists anywhere in this extension) on browsers
//      without `getAuthToken`, and for non-Google providers later;
//   2. our own session token, which `POST /ext/v1/session` hands back in
//      exchange for (1).
// Both are kept in `chrome.storage.session`: memory-only, cleared when the
// browser closes, unreadable from a content script or the page. Nothing here
// touches `localStorage`.

import { createApi } from "../lib/api.js";
import type { SessionResponse } from "../lib/types.js";
import { loadSettings } from "./settings.js";

const KEY_PROVIDER = "providerToken";
const KEY_SESSION = "session";

/** Sentinel bearer the local mock accepts; only reachable in a dev build. */
const MOCK_PROVIDER_TOKEN = "mock-dev-token";

export class AuthCancelled extends Error {}
export class NotSignedIn extends Error {}

type StoredSession = SessionResponse;

async function sessionGet<T>(key: string): Promise<T | undefined> {
  const got = await chrome.storage.session.get(key);
  return got[key] as T | undefined;
}

function hasGetAuthToken(): boolean {
  return typeof chrome.identity?.getAuthToken === "function";
}

function manifestOAuth(): { client_id: string; scopes: string[] } {
  const oauth2 = (chrome.runtime.getManifest() as { oauth2?: { client_id: string; scopes: string[] } }).oauth2;
  if (!oauth2) throw new Error("manifest.oauth2 missing");
  return oauth2;
}

/** Chrome: the browser's own account picker; the token is cached by Chrome and
 *  scoped to the manifest's `oauth2.scopes`. */
async function tokenViaGetAuthToken(interactive: boolean): Promise<string> {
  const result = await chrome.identity.getAuthToken({ interactive });
  const token = typeof result === "string" ? result : result?.token;
  if (!token) throw new AuthCancelled("Sign-in was cancelled.");
  return token;
}

/** Everything else: a standard OAuth implicit-grant round trip in a browser
 *  window, redirecting to the extension's own `chromiumapp.org` URL. */
async function tokenViaWebAuthFlow(interactive: boolean): Promise<string> {
  const { client_id, scopes } = manifestOAuth();
  const redirect = chrome.identity.getRedirectURL("oauth2");
  const state = crypto.randomUUID();
  const url = new URL("https://accounts.google.com/o/oauth2/v2/auth");
  url.searchParams.set("client_id", client_id);
  url.searchParams.set("response_type", "token");
  url.searchParams.set("redirect_uri", redirect);
  url.searchParams.set("scope", scopes.join(" "));
  url.searchParams.set("state", state);
  url.searchParams.set("prompt", interactive ? "select_account" : "none");
  const final = await chrome.identity.launchWebAuthFlow({ url: url.toString(), interactive });
  if (!final) throw new AuthCancelled("Sign-in was cancelled.");
  const fragment = new URLSearchParams(new URL(final).hash.replace(/^#/, ""));
  if (fragment.get("state") !== state) throw new AuthCancelled("Sign-in response did not match the request.");
  const token = fragment.get("access_token");
  if (!token) throw new AuthCancelled(fragment.get("error") ?? "Sign-in returned no token.");
  return token;
}

async function providerToken(interactive: boolean): Promise<string> {
  const settings = await loadSettings();
  if (__DEV_BUILD__ && settings.mockAuth) return MOCK_PROVIDER_TOKEN;

  const cached = await sessionGet<string>(KEY_PROVIDER);
  if (cached) return cached;
  const token = hasGetAuthToken() ? await tokenViaGetAuthToken(interactive) : await tokenViaWebAuthFlow(interactive);
  await chrome.storage.session.set({ [KEY_PROVIDER]: token });
  return token;
}

async function forgetProviderToken(): Promise<void> {
  const cached = await sessionGet<string>(KEY_PROVIDER);
  await chrome.storage.session.remove(KEY_PROVIDER);
  if (cached && hasGetAuthToken()) {
    try {
      await chrome.identity.removeCachedAuthToken({ token: cached });
    } catch {
      /* already gone */
    }
  }
}

function notExpired(s: StoredSession): boolean {
  const t = Date.parse(s.expiresAt);
  return Number.isFinite(t) && t - Date.now() > 30_000;
}

/** Our session token: from storage if still valid, else exchanged fresh. */
export async function session(interactive: boolean): Promise<StoredSession> {
  const cached = await sessionGet<StoredSession>(KEY_SESSION);
  if (cached && notExpired(cached)) return cached;

  const settings = await loadSettings();
  if (!settings.serverUrl) throw new NotSignedIn("No server configured. Set it on the extension's options page.");
  const api = createApi(settings.serverUrl);

  const token = await providerToken(interactive);
  let fresh: SessionResponse;
  try {
    fresh = await api.exchangeSession(token);
  } catch (err) {
    // A stale Google token is the usual cause of a 401 here; drop it and let the
    // next attempt fetch a new one rather than looping.
    await forgetProviderToken();
    throw err;
  }
  await chrome.storage.session.set({ [KEY_SESSION]: fresh });
  return fresh;
}

/** The Google token for direct Calendar API calls — never leaves the worker. */
export async function googleToken(interactive: boolean): Promise<string> {
  return providerToken(interactive);
}

export async function currentUser(): Promise<StoredSession["user"] | null> {
  const cached = await sessionGet<StoredSession>(KEY_SESSION);
  return cached && notExpired(cached) ? cached.user : null;
}

export async function signOut(): Promise<void> {
  await forgetProviderToken();
  await chrome.storage.session.remove(KEY_SESSION);
}

/** Wraps a server call so that one 401 drops the session and retries once. */
export async function withSession<T>(fn: (sessionToken: string) => Promise<T>, interactive: boolean): Promise<T> {
  const s = await session(interactive);
  try {
    return await fn(s.sessionToken);
  } catch (err) {
    if (isUnauthorized(err)) {
      await chrome.storage.session.remove(KEY_SESSION);
      const again = await session(interactive);
      return fn(again.sessionToken);
    }
    throw err;
  }
}

function isUnauthorized(err: unknown): boolean {
  return typeof err === "object" && err !== null && (err as { status?: unknown }).status === 401;
}
