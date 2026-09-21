// @ts-check
/**
 * Paints a Board (board.js) onto stage.html. Called a few times a second with a fresh
 * Board; keyed rows are reused so the bars animate instead of jumping, everything else
 * is only rewritten when its text changed.
 */
import { mmss } from "./board.js";

/** @typedef {import("./board.js").Board} Board */

const COLORS = ["#7c8cff", "#3ddc97", "#ffc24b", "#ff8a65", "#4dd0e1", "#c98bff", "#aed581", "#f06292"];
/** @param {string} id */
function colorOf(id) {
  let h = 0;
  for (const c of String(id)) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return COLORS[h % COLORS.length] ?? "#7c8cff";
}

/** @param {unknown} s */
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] ?? c);

/** @type {Map<string, string>} */
const last = new Map();
/**
 * Writes innerHTML only when it changed — a redraw a few times a second must not restart
 * CSS animations or flicker text under video compression.
 * @param {string} id @param {string} html
 */
function put(id, html) {
  if (last.get(id) === html) return;
  last.set(id, html);
  const el = document.getElementById(id);
  if (el) el.innerHTML = html;
}
/** @param {string} id @param {string} text */
function text(id, text) {
  if (last.get("t:" + id) === text) return;
  last.set("t:" + id, text);
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}
/** @param {Element | null} el @param {string} cls @param {boolean} on */
function toggle(el, cls, on) {
  if (el) el.classList.toggle(cls, on);
}

/** @param {Board["topicClock"]} c */
function topicClock(c) {
  if (!c) return "";
  const v = c.timed && c.budgetSeconds > 0
    ? `${mmss(c.elapsedSeconds)}<small> / ${mmss(c.budgetSeconds)}</small>`
    : mmss(c.elapsedSeconds);
  return `<div class="k">This topic</div><div class="v">${v}</div>`;
}
/** @param {Board["meetingClock"]} c */
function meetingClock(c) {
  if (!c) return "";
  const v = c.over ? `−${mmss(-c.remainingSeconds)}` : mmss(c.remainingSeconds);
  return `<div class="k">Meeting</div><div class="v">${v}<small> left</small></div>`;
}

/** @param {Board["people"]} rows @param {Board["morePeople"]} more @param {number} threshold */
function floor(rows, more, threshold) {
  const root = document.getElementById("floor");
  if (!root) return;
  if (!rows.length) {
    put("floor", `<div class="nobody">Nobody has spoken yet</div>`);
    return;
  }
  if (last.get("floor") !== undefined) {
    last.delete("floor");
    root.innerHTML = "";
  }
  const want = more ? [...rows, null] : rows;
  /** @type {Map<string, HTMLElement>} */
  const have = new Map();
  for (const el of root.children) have.set(/** @type {HTMLElement} */ (el).dataset.id ?? "", /** @type {HTMLElement} */ (el));
  const seen = new Set();
  want.forEach((row, i) => {
    const id = row ? row.id : "+more";
    seen.add(id);
    let el = have.get(id);
    if (!el) {
      el = document.createElement("div");
      el.dataset.id = id;
      el.innerHTML = `<div class="name"></div><div class="track"><div class="fill"></div><div class="mark"></div></div><div class="pct"></div>`;
      root.append(el);
    }
    if (root.children[i] !== el) root.insertBefore(el, root.children[i] ?? null);
    const name = /** @type {HTMLElement} */ (el.querySelector(".name"));
    const fill = /** @type {HTMLElement} */ (el.querySelector(".fill"));
    const mark = /** @type {HTMLElement} */ (el.querySelector(".mark"));
    const pct = /** @type {HTMLElement} */ (el.querySelector(".pct"));
    if (row) {
      el.className = `person${row.speaking ? " speaking" : ""}${row.hog ? " hog" : ""}${row.muted ? " muted" : ""}`;
      name.textContent = row.name;
      name.title = row.name;
      fill.style.width = `${Math.round(row.share * 1000) / 10}%`;
      fill.style.setProperty("--bar", colorOf(row.id));
      mark.style.left = `${threshold * 100}%`;
      mark.style.display = threshold > 0 && threshold < 1 ? "" : "none";
      pct.innerHTML = `${Math.round(row.share * 100)}%<small>${mmss(row.seconds)}</small>`;
    } else if (more) {
      el.className = "person more";
      name.textContent = `+${more.count} more`;
      fill.style.width = `${Math.round(more.share * 1000) / 10}%`;
      fill.style.setProperty("--bar", "var(--dim)");
      mark.style.display = "none";
      pct.innerHTML = `${Math.round(more.share * 100)}%`;
    }
  });
  for (const [id, el] of have) if (!seen.has(id)) el.remove();
}

/** @param {Board["topics"]} rows @param {Board["moreTopics"]} more @param {string} mode */
function agenda(rows, more, mode) {
  const root = document.getElementById("agenda");
  if (!rows.length) {
    put("agenda", `<div class="nothing">${mode === "active" ? "No agenda — open discussion" : "No agenda"}</div>`);
    toggle(root, "dense", false);
    text("agenda-more", "");
    return;
  }
  toggle(root, "dense", rows.length + (more.done ? 1 : 0) + (more.next ? 1 : 0) > 6);
  const line = (/** @type {Board["topics"][number]} */ t) => {
    const glyph = t.status === "done" ? "✓" : t.status === "live" ? "▶" : String(t.n);
    const budget = t.status === "live" && t.elapsedSeconds != null
      ? t.budgetSeconds > 0
        ? t.over ? `+${mmss(t.elapsedSeconds - t.budgetSeconds)} over` : `${mmss(t.elapsedSeconds)} / ${mmss(t.budgetSeconds)}`
        : mmss(t.elapsedSeconds)
      : t.budgetSeconds > 0 ? mmss(t.budgetSeconds) : "";
    return `<div class="topic ${t.status}${t.over ? " over" : ""}"><span class="n">${glyph}</span><span class="t">${esc(t.title)}</span><span class="o">${esc(t.owner)}</span><span class="b">${budget}</span></div>`;
  };
  const before = more.done ? `<div class="topic more"><span class="n">✓</span><span class="t">${more.done} earlier topic${more.done === 1 ? "" : "s"} done</span><span class="o"></span><span class="b"></span></div>` : "";
  const after = more.next ? `<div class="topic more"><span class="n">…</span><span class="t">+${more.next} more to come</span><span class="o"></span><span class="b"></span></div>` : "";
  put("agenda", before + rows.map(line).join("") + after);
  const done = rows.filter((t) => t.status === "done").length + more.done;
  const total = rows.length + more.done + more.next;
  text("agenda-more", `${done} of ${total} done`);
}

/** @param {string} key @param {string[]} items @param {number} more @param {string} none */
function notes(key, items, more, none) {
  put(`l-${key}`, items.length ? items.map((x) => `<li>${esc(x)}</li>`).join("") : `<li class="none">${none}</li>`);
  text(`n-${key}`, items.length + more ? String(items.length + more) : "");
  text(`m-${key}`, more ? `+${more} more` : "");
}

/** @param {Board} b */
export function paint(b) {
  const stage = document.getElementById("stage");
  if (!stage) return;
  stage.dataset.mode = b.mode;
  if (b.mode === "empty") {
    text("empty-msg", b.banner);
    text("empty-sub", b.link.label ?? "");
    return;
  }
  text("title", b.title);
  text("subtitle", b.subtitle);
  put("clock-topic", topicClock(b.topicClock));
  toggle(document.getElementById("clock-topic"), "over", !!b.topicClock?.over);
  put("clock-meeting", meetingClock(b.meetingClock));
  toggle(document.getElementById("clock-meeting"), "over", !!b.meetingClock?.over);
  toggle(document.getElementById("clock-meeting"), "warn", !!b.meetingClock && !b.meetingClock.over && b.meetingClock.remainingSeconds < 120);
  text("banner", b.banner);
  put("speaker", b.speaker ? `<span class="live">${esc(b.speaker)} is speaking</span>` : b.people.length ? `<span class="quiet">nobody speaking</span>` : "");
  floor(b.people, b.morePeople, b.threshold);
  agenda(b.topics, b.moreTopics, b.mode);
  notes("decisions", b.notes.decisions, b.moreNotes.decisions, "Nothing decided yet");
  notes("open", b.notes.open, b.moreNotes.open, "Nothing open");
  notes("parked", b.notes.parked, b.moreNotes.parked, "Nothing parked");
  text("chair", b.chair);
  const line = document.getElementById("line");
  text("line", b.line ? `“${b.line.text}”` : `${b.chair} hasn't said anything yet`);
  toggle(line, "none", !b.line);
  text("link", b.link.label ?? "");
}
