// The four calls to `packages/calendar`. Only the service worker imports this;
// a content script never sees a URL or a token.
//
// The server is expected to answer CORS preflights for the extension's own
// origin (`chrome-extension://<id>`), which is why the manifest needs no
// `host_permissions` for it — see README "Server endpoints".

import type {
  DraftRequest,
  DraftResponse,
  RegisterRequest,
  RegisterResponse,
  ServerConfig,
  SessionResponse,
} from "./types.js";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export interface Api {
  exchangeSession(providerToken: string): Promise<SessionResponse>;
  config(sessionToken: string): Promise<ServerConfig>;
  draft(sessionToken: string, body: DraftRequest): Promise<DraftResponse>;
  register(sessionToken: string, body: RegisterRequest): Promise<RegisterResponse>;
}

type Fetch = typeof fetch;

async function call<T>(fetchImpl: Fetch, url: string, init: RequestInit): Promise<T> {
  let res: globalThis.Response;
  try {
    res = await fetchImpl(url, init);
  } catch (err) {
    throw new ApiError(0, err instanceof Error ? err.message : String(err));
  }
  if (!res.ok) {
    let detail = "";
    try {
      const body = (await res.json()) as { error?: unknown; detail?: unknown };
      const d = body.error ?? body.detail;
      detail = typeof d === "string" ? d : JSON.stringify(d ?? "");
    } catch {
      /* not JSON; keep detail empty */
    }
    throw new ApiError(res.status, detail || `${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

function json(method: "GET" | "POST", body: unknown, sessionToken: string | null): RequestInit {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (sessionToken !== null) headers["Authorization"] = `Bearer ${sessionToken}`;
  return { method, headers, body: body === undefined ? undefined : JSON.stringify(body), credentials: "omit" };
}

export function createApi(baseUrl: string, fetchImpl: Fetch = fetch): Api {
  const base = baseUrl.replace(/\/+$/, "");
  return {
    exchangeSession: (providerToken) =>
      call<SessionResponse>(fetchImpl, `${base}/ext/v1/session`, json("POST", { provider: "google", accessToken: providerToken }, null)),
    config: (sessionToken) => call<ServerConfig>(fetchImpl, `${base}/ext/v1/config`, json("GET", undefined, sessionToken)),
    draft: (sessionToken, body) => call<DraftResponse>(fetchImpl, `${base}/ext/v1/agenda/draft`, json("POST", body, sessionToken)),
    register: (sessionToken, body) => call<RegisterResponse>(fetchImpl, `${base}/ext/v1/agendas`, json("POST", body, sessionToken)),
  };
}
