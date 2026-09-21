// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { beforeAll, describe, expect, it } from "vitest";
import { reduce } from "../public/board.js";
import type { BrainState, Link } from "../public/board.js";
import { paint } from "../public/render.js";
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
    expect(document.querySelectorAll("#agenda .topic")).toHaveLength(5);
    expect(document.querySelector("#agenda .topic.live.over")).not.toBeNull();
    expect(document.getElementById("clock-topic")?.classList.contains("over")).toBe(true);
    expect(text("#clock-topic .v")).toBe("8:35 / 8:00");
    expect(text("#line")).toBe("“We're over on the date. Marc, name a date you can defend.”");
    expect(text("#link")).toBe("");
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
    const rows = [...document.querySelectorAll("#agenda .topic")];
    expect(rows.filter((r) => !r.classList.contains("more"))).toHaveLength(7);
    expect(rows.filter((r) => r.classList.contains("more"))).toHaveLength(2);
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
