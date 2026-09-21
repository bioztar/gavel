// The one control the host sees before anything else: "Chair this meeting".
// Placed inline next to an anchor when the surface offers one (the editor's
// Save button), floating bottom-right otherwise. Clicking it opens the panel.

import { h, mount } from "./dom.js";
import { Panel, type Surface, css } from "./panel.js";

const HOST_ID = "gavel-chair-host";

export function installLauncher(surface: Surface, anchor: () => HTMLElement | null): { remove(): void } {
  const { root } = mount(HOST_ID, css);
  let panel: Panel | null = null;
  const open = (): void => {
    panel?.close();
    panel = new Panel(root, surface);
  };

  const button = h("button", { class: "gv-launcher", type: "button", "data-gv-launcher": true }, h("span", { class: "gv-gavel" }, "\u2696"), "Chair this meeting");
  button.addEventListener("click", open);

  // Inline placement puts our button in the page's light DOM, so its styles
  // come from a second copy of the stylesheet scoped to it; the panel itself
  // always lives in the shadow root.
  const inlineHost = h("span", { id: `${HOST_ID}-inline` });
  const inlineRoot = inlineHost.attachShadow({ mode: "closed" });
  const style = document.createElement("style");
  style.textContent = css;
  inlineRoot.append(style);

  const place = (): void => {
    const a = anchor();
    if (a && a.parentElement && !inlineHost.isConnected) {
      button.classList.add("gv-inline");
      inlineRoot.append(button);
      a.parentElement.insertBefore(inlineHost, a);
    } else if (!a && !button.isConnected) {
      button.classList.remove("gv-inline");
      root.append(button);
    }
  };
  place();
  const observer = new MutationObserver(place);
  observer.observe(document.documentElement, { childList: true, subtree: true });

  return {
    remove(): void {
      observer.disconnect();
      panel?.close();
      button.remove();
      inlineHost.remove();
    },
  };
}
