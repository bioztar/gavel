// Injected into the Meet tab by browser.py. Watches the participant tiles, their speaking
// indicators, the People panel and the captions region, and posts *raw* observations to
// Python through `window.__gavelPost(event)` (a Playwright binding). All smoothing —
// the speaking debounce, the roster diff, caption settling — is done in Python where it
// is unit-tested; this file only says what the DOM shows right now.
//
// Selectors come from selectors.py as `config`; nothing DOM-specific is hardcoded here
// except the structural fallbacks noted inline. `t` on every event is
// performance.timeOrigin + performance.now() in epoch milliseconds, taken at the
// moment the DOM changed, so a slow bridge never skews floor timing.
//
// Events:
//   {kind:"tiles",     t, participants:[{id, name, self, muted}]}   the set on stage changed
//   {kind:"indicator", t, id, on}                                  a tile's indicator flipped
//   {kind:"caption",   t, key, speaker, text}                      a caption line changed
//   {kind:"captions",  t, visible}                                 captions region appeared/left
(function install(config) {
  if (window.__gavelObserver) return window.__gavelObserver.reconfigure(config);

  const now = () => Math.round(performance.timeOrigin + performance.now());
  const post = (ev) => {
    try {
      window.__gavelPost(ev);
    } catch (e) {
      /* binding not ready yet; the next poll re-sends state */
    }
  };

  const firstMatch = (root, candidates) => {
    for (const sel of candidates) {
      try {
        const el = root.querySelector(sel);
        if (el) return el;
      } catch (e) {
        /* invalid selector for this engine; try the next */
      }
    }
    return null;
  };
  const allMatches = (root, candidates) => {
    for (const sel of candidates) {
      try {
        const list = root.querySelectorAll(sel);
        if (list.length) return Array.from(list);
      } catch (e) {
        /* try the next */
      }
    }
    return [];
  };

  // The display name in a tile. Try the configured selectors, then fall back to the
  // first non-empty text node that is not inside a button or an icon — Meet's classes
  // rotate, but the name is always the tile's one piece of plain text.
  const nameOf = (tile) => {
    const self = tile.getAttribute("data-self-name");
    if (self) return self.trim();
    const el = firstMatch(tile, config.name);
    if (el && el.textContent && el.textContent.trim()) return el.textContent.trim();
    const walker = document.createTreeWalker(tile, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const text = node.textContent.trim();
      if (!text) continue;
      if (node.parentElement && node.parentElement.closest("button, [role=button], i, svg")) continue;
      return text;
    }
    return "";
  };

  const hasAnyClass = (el, classes) => classes.some((c) => el.classList.contains(c));
  const animating = (el) => {
    try {
      if (el.getAnimations && el.getAnimations({ subtree: true }).some((a) => a.playState === "running")) return true;
    } catch (e) {
      /* getAnimations can throw on detached nodes */
    }
    return false;
  };

  // Two independent signals — a running animation, or a known "speaking" class — so a
  // class rotation alone does not silence the package. A known "silent" class wins.
  const indicatorOn = (tile) => {
    const ind = firstMatch(tile, config.indicator);
    if (!ind) return null; // no indicator element at all: self_check reports it
    if (hasAnyClass(ind, config.silentClasses)) return false;
    if (hasAnyClass(ind, config.speakingClasses)) return true;
    return animating(ind);
  };

  const isMuted = (tile) => !!firstMatch(tile, config.mutedIcon);

  const state = {
    config,
    tiles: new Map(), // id → {name, self, muted}
    indicator: new Map(), // id → boolean
    captions: new Map(), // key → {speaker, text}
    captionsVisible: false,
    indicatorFound: false,
  };

  const readTiles = () => {
    const seen = new Map();
    for (const tile of allMatches(document, config.tile)) {
      const id = tile.getAttribute("data-participant-id");
      if (!id) continue;
      if (seen.has(id)) continue; // Meet duplicates a tile while re-laying-out
      seen.set(id, {
        el: tile,
        name: nameOf(tile),
        self: tile.hasAttribute("data-self-name"),
        muted: isMuted(tile),
      });
    }
    // The People panel lists everyone, including tiles paged out of the grid.
    for (const item of allMatches(document, config.peopleItem)) {
      const id = item.getAttribute("data-participant-id");
      const label = item.getAttribute("aria-label");
      if (!id || seen.has(id)) continue;
      seen.set(id, { el: null, name: (label || nameOf(item)).trim(), self: false, muted: false });
    }
    return seen;
  };

  const diffTiles = (seen) => {
    let changed = seen.size !== state.tiles.size;
    if (!changed) {
      for (const [id, t] of seen) {
        const prev = state.tiles.get(id);
        if (!prev || prev.name !== t.name || prev.self !== t.self || prev.muted !== t.muted) {
          changed = true;
          break;
        }
      }
    }
    if (!changed) return;
    state.tiles = new Map(Array.from(seen, ([id, t]) => [id, { name: t.name, self: t.self, muted: t.muted }]));
    post({
      kind: "tiles",
      t: now(),
      participants: Array.from(seen, ([id, t]) => ({ id, name: t.name, self: t.self, muted: t.muted })),
    });
  };

  const diffIndicators = (seen) => {
    const t = now();
    for (const [id, tile] of seen) {
      if (!tile.el) continue;
      const on = indicatorOn(tile.el);
      if (on === null) continue;
      state.indicatorFound = true;
      const prev = state.indicator.get(id);
      if (prev !== on) {
        state.indicator.set(id, on);
        post({ kind: "indicator", t, id, on });
      }
    }
    for (const id of Array.from(state.indicator.keys())) {
      if (!seen.has(id)) {
        if (state.indicator.get(id)) post({ kind: "indicator", t, id, on: false });
        state.indicator.delete(id);
      }
    }
  };

  // Captions: the region holds a few lines; each is a speaker block then a text block that
  // Meet edits in place. Key a line by its element (via a WeakMap counter) so an edit and
  // a new line are distinguishable in Python.
  const lineKeys = new WeakMap();
  let nextKey = 1;
  const keyOf = (el) => {
    let k = lineKeys.get(el);
    if (!k) lineKeys.set(el, (k = nextKey++));
    return k;
  };
  const readCaptions = () => {
    const region = firstMatch(document, config.captionsRegion);
    const visible = !!region;
    if (visible !== state.captionsVisible) {
      state.captionsVisible = visible;
      post({ kind: "captions", t: now(), visible });
    }
    if (!region) return;
    const t = now();
    // A line is a direct child of the region that contains some text. Speaker and text
    // are the configured selectors, falling back to "first text block, then the rest".
    for (const line of Array.from(region.children)) {
      const speakerEl = firstMatch(line, config.captionSpeaker);
      const textEl = firstMatch(line, config.captionText);
      let speaker = speakerEl ? speakerEl.textContent.trim() : "";
      let text = textEl ? textEl.textContent.trim() : "";
      if (!speaker || !text) {
        const blocks = Array.from(line.querySelectorAll("div, span"))
          .map((e) => e.textContent.trim())
          .filter((s) => s);
        if (blocks.length >= 2) {
          speaker = speaker || blocks[0];
          text = text || blocks[blocks.length - 1];
        }
      }
      if (!text) continue;
      const key = keyOf(line);
      const prev = state.captions.get(key);
      if (!prev || prev.text !== text || prev.speaker !== speaker) {
        state.captions.set(key, { speaker, text });
        post({ kind: "caption", t, key, speaker, text });
      }
    }
  };

  let scheduled = false;
  const scan = () => {
    scheduled = false;
    const seen = readTiles();
    diffTiles(seen);
    diffIndicators(seen);
    readCaptions();
  };
  const schedule = () => {
    if (scheduled) return;
    scheduled = true;
    // Coalesce a burst of mutations into one scan on the next frame (~16 ms).
    (window.requestAnimationFrame || setTimeout)(scan);
  };

  const observer = new MutationObserver(schedule);
  observer.observe(document.body, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ["class", "data-is-muted", "data-participant-id", "aria-label", "style"],
    characterData: true,
  });
  // CSS animations do not mutate the DOM; the poll catches indicator state driven by them.
  const poll = setInterval(scan, 100);

  window.__gavelObserver = {
    reconfigure(next) {
      state.config = Object.assign(config, next);
      schedule();
    },
    snapshot() {
      return {
        participants: Array.from(state.tiles, ([id, t]) => ({ id, name: t.name, self: t.self, muted: t.muted })),
        speaking: Array.from(state.indicator).filter(([, on]) => on).map(([id]) => id),
        captionsVisible: state.captionsVisible,
        indicatorFound: state.indicatorFound,
      };
    },
    resend() {
      post({ kind: "tiles", t: now(), participants: this.snapshot().participants });
      for (const [id, on] of state.indicator) post({ kind: "indicator", t: now(), id, on });
    },
    stop() {
      observer.disconnect();
      clearInterval(poll);
      delete window.__gavelObserver;
    },
  };
  schedule();
  return true;
})
