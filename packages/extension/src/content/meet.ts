// Content script for meet.google.com. On the pre-join screen ("Ready to join?")
// the host can still chair the call: the Meet code identifies the event, the
// service worker finds it on the user's calendar and writes the agenda there.
// There is no editor here, so nothing is written into the page — the Calendar
// API is the only path, and `wrote.description` reports whether it succeeded.

import { onceVisible } from "./dom.js";
import { installLauncher } from "./launcher.js";
import { joinButton, meetCodeFromUrl, readMeet } from "./meet-dom.js";
import type { Surface } from "./panel.js";

const surface: Surface = { read: readMeet };

let installed: { remove(): void } | null = null;

onceVisible(joinButton, () => {
  if (!meetCodeFromUrl(location.href)) return;
  installed?.remove();
  installed = installLauncher(surface, joinButton);
});

new MutationObserver(() => {
  if (installed && !joinButton()) {
    installed.remove();
    installed = null;
  }
}).observe(document.documentElement, { childList: true, subtree: true });
