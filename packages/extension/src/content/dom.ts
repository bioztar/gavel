// Element building without `innerHTML`. Untrusted text only ever reaches the
// page through `textContent` / `value`, so a description that says
// `<img onerror=…>` renders as those characters.

type Child = Node | string | null | undefined | false;

export function h<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  attrs: Partial<Record<string, string | boolean>> = {},
  ...children: Child[]
): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v === undefined) continue;
    if (k === "class") el.className = String(v);
    else if (k.startsWith("on")) continue; // handlers are attached explicitly, never from strings
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children) {
    if (c === null || c === undefined || c === false) continue;
    el.append(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return el;
}

export function clear(el: Element): void {
  while (el.firstChild) el.removeChild(el.firstChild);
}

/** A shadow root on our own host element: Google's styles do not leak in, ours
 *  do not leak out, and the page's scripts have no reason to look inside. */
export function mount(id: string, css: string): { host: HTMLElement; root: ShadowRoot } {
  let host = document.getElementById(id);
  if (host?.shadowRoot) return { host, root: host.shadowRoot };
  host = h("div", { id });
  const root = host.attachShadow({ mode: "closed" });
  const style = document.createElement("style");
  style.textContent = css;
  root.append(style);
  document.documentElement.append(host);
  return { host, root };
}

/** Text a user typed or a page exposed, read back safely. */
export function textOf(el: Element | null): string {
  if (!el) return "";
  if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) return el.value;
  return el.textContent ?? "";
}

/** `innerText`-like reading of a contenteditable: block elements become
 *  newlines so a description keeps its lines. */
export function linesOf(el: Element | null): string {
  if (!el) return "";
  if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) return el.value;
  const parts: string[] = [];
  const walk = (node: Node): void => {
    if (node.nodeType === Node.TEXT_NODE) {
      parts.push(node.textContent ?? "");
      return;
    }
    if (!(node instanceof HTMLElement)) return;
    const block = node.tagName === "BR" || /^(DIV|P|LI|BR|TR)$/.test(node.tagName);
    if (node.tagName === "BR") parts.push("\n");
    for (const child of Array.from(node.childNodes)) walk(child);
    if (block && node.tagName !== "BR") parts.push("\n");
  };
  walk(el);
  return parts.join("").replace(/\n{3,}/g, "\n\n").trim();
}

export function onceVisible(test: () => Element | null, cb: (el: Element) => void): () => void {
  let seen: Element | null = null;
  const tick = (): void => {
    const el = test();
    if (el && el !== seen) {
      seen = el;
      cb(el);
    } else if (!el) {
      seen = null;
    }
  };
  const observer = new MutationObserver(tick);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  tick();
  return () => observer.disconnect();
}
