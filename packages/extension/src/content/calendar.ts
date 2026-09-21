// Content script for calendar.google.com (and, in a dev build, the fixture at
// localhost). Waits for the event editor to appear, then installs the launcher
// next to its Save button; removes it when the editor closes.

import { onceVisible } from "./dom.js";
import { addGuest, editorRoot, readEvent, saveButton, writeDescription } from "./calendar-dom.js";
import { installLauncher } from "./launcher.js";
import type { Surface } from "./panel.js";

const surface: Surface = { read: readEvent, writeDescription, addGuest };

let installed: { remove(): void } | null = null;

onceVisible(editorRoot, () => {
  installed?.remove();
  installed = installLauncher(surface, saveButton);
});

// The editor is a client-side route; when it goes away so does the button.
new MutationObserver(() => {
  if (installed && !editorRoot()) {
    installed.remove();
    installed = null;
  }
}).observe(document.documentElement, { childList: true, subtree: true });
