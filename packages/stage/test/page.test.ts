// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { beforeAll, describe, expect, it } from "vitest";
import { reduce } from "../public/board.js";
import type { BrainState, Link } from "../public/board.js";
import { fitRows, paint } from "../public/render.js";
import { demoState } from "../public/demo.js";

const html = readFileSync(join(import.meta.dirname, "..", "public", "stage.html"), "utf8");

beforeAll(() => {
  document.open();
  document.write(html);
  document.close();
});

const at = (state: BrainState | null, over: Partial<Link> = {}) =>
  reduce({ state, receivedAt: 1_000_000, connected: true, brainOk: true, ...over }, 1_000_000);

const text = (sel: string) => document.querySelector(sel)?.textContent?.replace(/\s+/g, " ").trim() ?? "";

describe("the page", () => {
  it("has document.title exactly `gavel-stage`", () => {
    expect(document.title).toBe("gavel-stage");
    // ears-meet matches the tab by this exact string; a paint must never touch it.
    paint(at(demoState("meeting", 60)));
    expect(document.title).toBe("gavel-stage");
    expect(html).toContain("<title>gavel-stage</title>");
  });

  it("loads nothing from the network but its own origin", () => {
    expect(html).not.toMatch(/https?:\/\//);
    expect(html).not.toMatch(/@import|@font-face|<link/);
    expect(html).toMatch(/<script type="module" src="\/app\.js">/);
  });

  it("has no controls", () => {
    expect(document.querySelectorAll("a, button, input, select, textarea, [onclick], [tabindex]")).toHaveLength(0);
  });

  it("starts in the empty state and leaves it once state arrives", () => {
    paint(at(null, { connected: false }));
    expect(document.getElementById("stage")?.dataset.mode).toBe("empty");
    expect(text("#empty-msg")).toBe("Connecting to the meeting…");
    paint(at(demoState("meeting", 0)));
    expect(document.getElementById("stage")?.dataset.mode).toBe("active");
    expect(text("#title")).toBe("Q4 launch sync");
  });

  it("paints the demo meeting: floor, agenda, clocks, Karen's line", () => {
    paint(at(demoState("meeting", 60)));
    const people = [...document.querySelectorAll("#floor .person")];
    expect(people).toHaveLength(5);
    expect(people[0]?.querySelector(".name")?.textContent).toBe("Vitaly");
    expect(people[0]?.classList.contains("hog")).toBe(true);
    expect(people[0]?.querySelector(".pct")?.textContent).toMatch(/^6\d%/);
    expect((people[0]?.querySelector(".fill") as HTMLElement).style.width).toMatch(/^6\d(\.\d)?%$/);
    expect(document.querySelectorAll("#agenda .topic:not([hidden])")).toHaveLength(5);
    expect(document.querySelector("#agenda .topic.live.over")).not.toBeNull();
    expect(document.getElementById("clock-topic")?.classList.contains("over")).toBe(true);
    expect(text("#clock-topic .v")).toBe("8:35 / 8:00");
    expect(text("#clock-meeting .v")).toBe("14:25 left");
    expect(text("#line")).toBe("“We're over on the date. Marc, name a date you can defend.”");
    expect(text("#link")).toBe("");
  });

  it("says `7:55 over`, not `−7:55 left`, once the meeting is past its budget", () => {
    paint(at(demoState("meeting", 1400)));
    const clock = document.getElementById("clock-meeting")!;
    expect(clock.classList.contains("over")).toBe(true);
    expect(text("#clock-meeting .v")).toBe("7:55 over");
    expect(text("#agenda .topic.live .b")).toBe("+22:55 over");
    // No signed duration anywhere on the board.
    expect(document.getElementById("stage")!.textContent).not.toMatch(/[−-]\d+:\d\d/);
  });

  it("lists notes newest first and folds the rest into a `+N more` row", () => {
    const state = demoState("meeting", 60);
    state.digest!.decisions = Array.from({ length: 6 }, (_, i) => `Decision ${i + 1}`);
    paint(at(state));
    const rows = [...document.querySelectorAll("#l-decisions li:not(.more)")].map((li) => li.textContent);
    expect(rows).toEqual(["Decision 6", "Decision 5", "Decision 4", "Decision 3"]);
    const fold = document.querySelector<HTMLElement>("#l-decisions li.more")!;
    expect(fold.hidden).toBe(false);
    expect(fold.textContent).toBe("+2 more");
    expect(text("#n-decisions")).toBe("6");
    // The other columns have room for everything: no fold row shows.
    expect(document.querySelector<HTMLElement>("#l-open li.more")!.hidden).toBe(true);
  });

  it("renders a missing owner as a kept column, a dash only when other rows have one", () => {
    const state = demoState("meeting", 60);
    // What brain publishes today: no owner on any topic.
    for (const t of state.topics!) delete t.owner;
    paint(at(state));
    const bare = [...document.querySelectorAll("#agenda .topic:not(.more) .o")];
    expect(bare).toHaveLength(5);
    expect(bare.every((o) => o.classList.contains("none") && o.textContent === "")).toBe(true);

    const mixed = demoState("meeting", 60);
    delete mixed.topics![2]!.owner;
    paint(at(mixed));
    const owners = [...document.querySelectorAll("#agenda .topic:not(.more) .o")].map((o) => [o.textContent, o.classList.contains("none")]);
    expect(owners).toEqual([["Ana", false], ["Vitaly", false], ["—", true], ["Priya", false], ["Marc", false]]);
    // Same DOM shape either way: the column never comes and goes with the data.
    expect(document.querySelectorAll("#agenda .topic:not(.more) .o")).toHaveLength(5);
    expect(html).toMatch(/\.topic \{[^}]*grid-template-columns:[^;]*calc\(var\(--u\) \* 8\)/);
  });

  it("with 12 attendees shows 8 rows plus a fold, and the 40-character name is cut", () => {
    paint(at(demoState("crowd", 60)));
    const rows = [...document.querySelectorAll("#floor .person")];
    expect(rows).toHaveLength(9);
    expect(rows.filter((r) => !r.classList.contains("more"))).toHaveLength(8);
    expect(text("#floor .person.more .name")).toBe("+4 more");
    const long = rows.map((r) => r.querySelector(".name")?.textContent ?? "").find((n) => n.startsWith("Alexandra"));
    expect(long).toBeDefined();
    expect(long!.length).toBeLessThanOrEqual(18);
    expect(long).toMatch(/…$/);
  });

  it("with 9 topics shows 7 agenda rows and counts the rest", () => {
    paint(at(demoState("crowd", 60)));
    const rows = [...document.querySelectorAll<HTMLElement>("#agenda .topic")].filter((r) => !r.hidden);
    expect(rows.filter((r) => !r.classList.contains("more"))).toHaveLength(7);
    expect(rows.filter((r) => r.classList.contains("more")).map((r) => r.querySelector(".t")?.textContent)).toEqual(["1 earlier topic done", "+1 more"]);
    expect(text("#agenda-more")).toBe("3 of 9 done");
    expect(document.getElementById("agenda")?.classList.contains("dense")).toBe(true);
  });

  it("with an empty agenda shows the floor and says so", () => {
    paint(at(demoState("open", 60)));
    expect(text("#agenda")).toBe("No agenda — open discussion");
    expect(text("#banner")).toBe("Open discussion — no agenda.");
    expect(document.querySelectorAll("#floor .person")).toHaveLength(5);
    expect(text("#clock-topic")).toBe("");
  });

  it("keeps the last board and shows a quiet marker when the stream drops", () => {
    paint(at(demoState("meeting", 60)));
    paint(reduce({ state: demoState("meeting", 60), receivedAt: 1_000_000, connected: false, brainOk: false }, 1_000_000 + 41_000));
    expect(document.getElementById("stage")?.dataset.mode).toBe("active");
    expect(document.querySelectorAll("#floor .person")).toHaveLength(5);
    expect(text("#link")).toBe("reconnecting · last update 0:41 ago");
  });

  it("escapes what brain sends", () => {
    const evil = demoState("meeting", 60);
    evil.topics![2]!.title = "<img src=x onerror=alert(1)>";
    evil.digest!.decisions = ["<b>bold</b>"];
    paint(at(evil));
    expect(document.querySelector("#agenda img")).toBeNull();
    expect(document.querySelector("#l-decisions b")).toBeNull();
    expect(text("#l-decisions")).toContain("<b>bold</b>");
  });
});

describe("fitRows — whole rows or nothing", () => {
  // jsdom has no layout, so the geometry is stubbed: a 100px-tall list, rows stacked from
  // its top, each `h` tall with a 5px gap. The fold row is 20px tall.
  const build = (heights: number[], listHeight = 100) => {
    const ul = document.createElement("ul");
    const rows: HTMLElement[] = [];
    let y = 0;
    const rect = (top: number, h: number) => () => ({ top, bottom: top + h, left: 0, right: 200, width: 200, height: h, x: 0, y: top, toJSON() {} }) as DOMRect;
    ul.getBoundingClientRect = rect(0, listHeight);
    for (const h of heights) {
      const li = document.createElement("li");
      li.getBoundingClientRect = rect(y, h);
      y += h + 5;
      rows.push(li);
      ul.append(li);
    }
    const fold = document.createElement("li");
    fold.className = "more";
    // The fold sits under the last visible row, wherever that ends up.
    fold.getBoundingClientRect = () => {
      const shown = rows.filter((r) => !r.hidden);
      const top = shown.reduce((a, r) => Math.max(a, r.getBoundingClientRect().bottom + 5), 0);
      return rect(top, 20)();
    };
    ul.append(fold);
    const labels: number[] = [];
    const shown = fitRows(ul, rows, fold, 0, (n) => labels.push(n));
    return { rows, fold, labels, shown };
  };

  it("hides nothing when everything fits", () => {
    const { rows, fold, shown } = build([40, 40]);
    expect(shown).toBe(2);
    expect(rows.map((r) => r.hidden)).toEqual([false, false]);
    expect(fold.hidden).toBe(true);
  });

  it("drops the row that would be cut and says how many are missing", () => {
    // Rows end at 30, 65, 100, 135 in a 130px list: the fourth would be painted half.
    const { rows, fold, labels, shown } = build([30, 30, 30, 30], 130);
    expect(shown).toBe(3);
    expect(rows.map((r) => r.hidden)).toEqual([false, false, false, true]);
    expect(fold.hidden).toBe(false);
    expect(labels.at(-1)).toBe(1);
  });

  it("drops one more row when the fold itself would not fit", () => {
    // 45 + 5 + 45 = 95 fits; a third 45 does not; the 20px fold at y=100 does not either.
    const { rows, labels, shown } = build([45, 45, 45]);
    expect(shown).toBe(1);
    expect(rows.map((r) => r.hidden)).toEqual([false, true, true]);
    expect(labels.at(-1)).toBe(2);
  });

  it("counts what the reducer already left out", () => {
    const ul = document.createElement("ul");
    const li = document.createElement("li");
    const fold = document.createElement("li");
    ul.append(li, fold);
    const labels: number[] = [];
    expect(fitRows(ul, [li], fold, 3, (n) => labels.push(n))).toBe(1);
    expect(fold.hidden).toBe(false);
    expect(labels).toEqual([3]);
  });
});
