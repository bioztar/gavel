// Options page: the server origin and, in a dev build, the mock-auth switch.
// Tokens are never shown or stored here.

import { DEFAULTS, loadSettings, saveSettings } from "../background/settings.js";
import { send } from "../lib/messages.js";
import { cleanHttpUrl } from "../lib/sanitize.js";

function el<T extends HTMLElement>(id: string): T {
  const found = document.getElementById(id);
  if (!found) throw new Error(`options.html is missing #${id}`);
  return found as T;
}

const serverUrl = el<HTMLInputElement>("serverUrl");
const mockAuth = el<HTMLInputElement>("mockAuth");
const status = el<HTMLSpanElement>("status");
const who = el<HTMLSpanElement>("who");

async function refreshWho(): Promise<void> {
  const r = await send({ type: "whoami" });
  who.textContent = r.ok && r.type === "whoami" && r.user ? r.user.email : "nobody yet";
}

async function init(): Promise<void> {
  const s = await loadSettings();
  serverUrl.value = s.serverUrl;
  serverUrl.placeholder = DEFAULTS.serverUrl || "https://gavel.example.com";
  if (__DEV_BUILD__) {
    el("dev").classList.add("on");
    mockAuth.checked = s.mockAuth;
  }
  el("version").textContent = `v${__EXTENSION_VERSION__}${__DEV_BUILD__ ? " (dev build)" : ""}`;
  await refreshWho();
}

el("save").addEventListener("click", async () => {
  const url = cleanHttpUrl(serverUrl.value, __DEV_BUILD__);
  if (!url && serverUrl.value.trim()) {
    status.textContent = __DEV_BUILD__ ? "Enter an https:// origin (or http://localhost)." : "Enter an https:// origin.";
    return;
  }
  const origin = url ? new URL(url).origin : "";
  await saveSettings({ serverUrl: origin, ...(__DEV_BUILD__ ? { mockAuth: mockAuth.checked } : {}) });
  // A different server means a different session.
  await send({ type: "sign-out" });
  serverUrl.value = origin;
  status.textContent = "Saved.";
  await refreshWho();
});

el("signout").addEventListener("click", async () => {
  await send({ type: "sign-out" });
  status.textContent = "Signed out.";
  await refreshWho();
});

void init();
