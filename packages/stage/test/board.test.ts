import { describe, expect, it } from "vitest";
import { LIMITS, clip, lastLine, mmss, reduce, reducePeople, reduceTopics } from "../public/board.js";
import type { BrainPerson, BrainState, BrainTopic, Link } from "../public/board.js";

const person = (i: number, seconds: number, extra: Partial<BrainPerson> = {}): BrainPerson => ({
  id: `p${i}`,
  name: `Person ${i}`,
  totalSeconds: seconds,
  topicSeconds: seconds,
  windowSeconds: 0,
  speaking: false,
  muted: false,
  ...extra,
});

const topic = (i: number, extra: Partial<BrainTopic> = {}): BrainTopic => ({
  id: `t${i}`,
  title: `Topic ${i}`,
  budgetSeconds: 300,
  type: "discussion",
  done: false,
  discussed: false,
  ...extra,
});

const active = (over: Partial<BrainState> = {}): BrainState => ({
  sessionId: "s",
  title: "Q4 launch sync",
  purpose: "Pick a date",
  chairName: "Karen",
  phase: "active",
  timed: true,
  topic: { index: 1, id: "t1", title: "Topic 1", budgetSeconds: 300, elapsedSeconds: 120 },
  topics: [topic(0, { done: true }), topic(1), topic(2)],
  people: [person(0, 300, { speaking: true }), person(1, 100), person(2, 50)],
  persona: { id: "funky", displayName: "Karen" },
  parked: [],
  understanding: { facts: [], decisions: [], openItems: [], later: [] },
  digest: { decisions: [], openItems: [], parked: [] },
  interventions: [],
  policy: { floorShareThreshold: 0.6, floorWindowSeconds: 120, timed: true },
  ...over,
});

const link = (state: BrainState | null, over: Partial<Link> = {}): Link => ({
  state,
  receivedAt: 1_000_000,
  connected: true,
  brainOk: true,
  ...over,
});

describe("clip", () => {
  it("leaves short text alone and collapses whitespace", () => {
    expect(clip("  a   b ", 10)).toBe("a b");
  });
  it("cuts a 40-character name to the limit with an ellipsis", () => {
    const name = "Alexandra Konstantinopoulou-Papadimitrio";
    expect(name).toHaveLength(40);
    const out = clip(name, LIMITS.name);
    expect(out.length).toBeLessThanOrEqual(LIMITS.name);
    expect(out.endsWith("…")).toBe(true);
  });
  it("prefers a word boundary when one is close", () => {
    expect(clip("Incident review: Tuesday's outage and what we owe", 30)).toBe("Incident review: Tuesday's…");
  });
  it("cuts mid-word rather than losing most of the text", () => {
    expect(clip("Supercalifragilisticexpialidocious plan", 12)).toBe("Supercalifr…");
  });
});

describe("mmss", () => {
  it("formats seconds", () => {
    expect(mmss(0)).toBe("0:00");
    expect(mmss(65)).toBe("1:05");
    expect(mmss(3600)).toBe("60:00");
    expect(mmss(-42)).toBe("−0:42");
  });
});

describe("reducePeople", () => {
  it("computes share of the floor and sorts loudest first", () => {
    const { rows, more, speaker } = reducePeople([person(0, 100), person(1, 300), person(2, 100, { speaking: true })], 0.6);
    expect(rows.map((r) => r.id)).toEqual(["p1", "p2", "p0"]);
    expect(rows[0]?.share).toBeCloseTo(0.6);
    expect(rows[0]?.hog).toBe(true);
    expect(rows[1]?.hog).toBe(false);
    expect(more).toBeNull();
    expect(speaker).toBe("Person 2");
  });

  it("flags a hog on the rolling window even when the whole-meeting share is low", () => {
    const { rows } = reducePeople([person(0, 100, { windowSeconds: 90 }), person(1, 900, { windowSeconds: 10 })], 0.6);
    expect(rows.find((r) => r.id === "p0")?.hog).toBe(true);
    expect(rows.find((r) => r.id === "p1")?.hog).toBe(true); // 90% of the meeting
  });

  it("with 12 attendees shows 8 rows and folds the rest into one", () => {
    const people = Array.from({ length: 12 }, (_, i) => person(i, 120 - i * 5));
    const { rows, more } = reducePeople(people, 0.6);
    expect(rows).toHaveLength(LIMITS.people);
    expect(more).toEqual({ count: 4, share: expect.closeTo(rows.length ? 1 - rows.reduce((a, r) => a + r.share, 0) : 0, 6) });
  });

  it("with 12 attendees the speaker is always visible", () => {
    const people = Array.from({ length: 12 }, (_, i) => person(i, 120 - i * 5));
    people[11] = { ...people[11]!, speaking: true };
    const { rows, more, speaker } = reducePeople(people, 0.6);
    expect(rows).toHaveLength(LIMITS.people);
    expect(rows.some((r) => r.id === "p11" && r.speaking)).toBe(true);
    expect(rows.some((r) => r.id === "p7")).toBe(false); // bumped to make room
    expect(more?.count).toBe(4);
    expect(speaker).toBe("Person 11");
  });

  it("truncates a 40-character name", () => {
    const name = "Alexandra Konstantinopoulou-Papadimitrio";
    expect(name).toHaveLength(40);
    const { rows } = reducePeople([person(0, 10, { name })], 0.6);
    expect(rows[0]?.name.length).toBeLessThanOrEqual(LIMITS.name);
    expect(rows[0]?.name).toMatch(/…$/);
    expect(rows[0]?.name.startsWith("Alexandra")).toBe(true);
  });

  it("copes with nobody having spoken", () => {
    const { rows } = reducePeople([person(0, 0), person(1, 0)], 0.6);
    expect(rows.every((r) => r.share === 0 && !r.hog)).toBe(true);
  });
});

describe("reduceTopics", () => {
  const names = new Map([["u1", "Ana"]]);

  it("marks done, live and next and clips titles", () => {
    const state = active({ topics: [topic(0, { done: true }), topic(1, { title: "x".repeat(80), owner: "u1" }), topic(2)] });
    const { rows, more } = reduceTopics(state, names, 330);
    expect(rows.map((r) => r.status)).toEqual(["done", "live", "next"]);
    expect(rows[1]?.title.length).toBeLessThanOrEqual(LIMITS.topic);
    expect(rows[1]?.owner).toBe("Ana");
    expect(rows[1]?.over).toBe(true);
    expect(rows[1]?.elapsedSeconds).toBe(330);
    expect(rows[2]?.elapsedSeconds).toBeNull();
    expect(more).toEqual({ done: 0, next: 0 });
  });

  it("with 9 topics shows 7 around the live one and counts the rest", () => {
    const topics = Array.from({ length: 9 }, (_, i) => topic(i, { done: i < 4 }));
    const state = active({ topics, topic: { index: 4, id: "t4", title: "Topic 4", budgetSeconds: 300, elapsedSeconds: 10 } });
    const { rows, more } = reduceTopics(state, names, 10);
    expect(rows).toHaveLength(LIMITS.topics);
    expect(rows.some((r) => r.status === "live")).toBe(true);
    expect(more.done + more.next).toBe(2);
    expect(rows.map((r) => r.n)).toEqual([3, 4, 5, 6, 7, 8, 9]);
    expect(more).toEqual({ done: 2, next: 0 });
  });

  it("with 9 topics and the first one live, upcoming ones win the space", () => {
    const topics = Array.from({ length: 9 }, (_, i) => topic(i));
    const state = active({ topics, topic: { index: 0, id: "t0", title: "Topic 0", budgetSeconds: 300, elapsedSeconds: 10 } });
    const { rows, more } = reduceTopics(state, names, 10);
    expect(rows.map((r) => r.n)).toEqual([1, 2, 3, 4, 5, 6, 7]);
    expect(more).toEqual({ done: 0, next: 2 });
  });

  it("with an empty agenda returns no rows", () => {
    expect(reduceTopics(active({ topics: [], topic: null }), names, 0)).toEqual({ rows: [], more: { done: 0, next: 0 } });
  });

  it("marks everything done once the agenda is finished", () => {
    const state = active({ phase: "finished", agendaFinished: true, topic: null });
    expect(reduceTopics(state, names, 0).rows.every((r) => r.status === "done")).toBe(true);
  });

  it("is not over budget when the meeting is untimed", () => {
    const state = active({ timed: false });
    expect(reduceTopics(state, names, 9999).rows[1]?.over).toBe(false);
    const viaPolicy = active({ timed: undefined, policy: { timed: false } });
    expect(reduceTopics(viaPolicy, names, 9999).rows[1]?.over).toBe(false);
    expect(reduce(link(viaPolicy), 1_000_000).topicClock?.timed).toBe(false);
  });
});

describe("reduce", () => {
  it("is an empty board before anything arrives", () => {
    const board = reduce(link(null, { connected: false }), 5_000);
    expect(board.mode).toBe("empty");
    expect(board.banner).toBe("Connecting to the meeting…");
    expect(board.link.label).toBeNull();
    expect(board.people).toEqual([]);
  });

  it("renders an active meeting with running clocks", () => {
    const board = reduce(link(active()), 1_000_000 + 30_000);
    expect(board.mode).toBe("active");
    expect(board.title).toBe("Q4 launch sync");
    expect(board.subtitle).toBe("Pick a date");
    expect(board.speaker).toBe("Person 0");
    expect(board.topicClock).toEqual({ elapsedSeconds: 150, budgetSeconds: 300, over: false, timed: true });
    // 300 - 150 left on this topic + 300 for topic 2
    expect(board.meetingClock).toEqual({ remainingSeconds: 450, totalSeconds: 900, over: false });
    expect(board.people[0]?.share).toBeCloseTo(300 / 450);
    expect(board.people[0]?.hog).toBe(true);
    expect(board.banner).toBe("");
    expect(board.link.label).toBeNull();
  });

  it("goes unmistakably over budget", () => {
    const board = reduce(link(active()), 1_000_000 + 400_000);
    expect(board.topicClock?.over).toBe(true);
    expect(board.topics.find((t) => t.status === "live")?.over).toBe(true);
    expect(board.meetingClock?.over).toBe(false);
    expect(board.meetingClock?.remainingSeconds).toBe(300 - 520 + 300);
  });

  it("keeps the last state and says so when the stream drops", () => {
    const board = reduce(link(active(), { connected: false }), 1_000_000 + 41_000);
    expect(board.mode).toBe("active");
    expect(board.people).toHaveLength(3);
    expect(board.link.label).toBe("reconnecting · last update 0:41 ago");
  });

  it("says brain is unreachable when the stream is up but brain is not", () => {
    const board = reduce(link(active(), { brainOk: false }), 1_000_000 + 5_000);
    expect(board.link.label).toBe("brain unreachable · showing 0:05 ago");
  });

  it("does not drift the clock outside an active meeting", () => {
    const board = reduce(link(active({ phase: "gathering", topic: null })), 1_000_000 + 60_000);
    expect(board.topicClock).toBeNull();
    expect(board.mode).toBe("gathering");
  });

  it("describes the lobby", () => {
    expect(reduce(link(active({ phase: "gathering", topic: null, missingAttendees: ["Priya", "Tom"] })), 1_000_000).banner).toBe("Waiting for Priya, Tom");
    expect(reduce(link(active({ phase: "gathering", topic: null, missingAttendees: [], readyToStart: true })), 1_000_000).banner).toBe(
      "Everyone is here. Say “Karen, let's start the meeting.”",
    );
    expect(reduce(link(active({ phase: "idle", topic: null })), 1_000_000).banner).toBe("No meeting running. The agenda is ready.");
    expect(reduce(link(active({ phase: "finished", topic: null })), 1_000_000).banner).toBe("Agenda complete. Thank you.");
  });

  it("with an empty agenda still shows the floor and says it is open discussion", () => {
    const board = reduce(link(active({ topics: [], topic: null })), 1_000_000);
    expect(board.mode).toBe("active");
    expect(board.topics).toEqual([]);
    expect(board.topicClock).toBeNull();
    expect(board.meetingClock).toBeNull();
    expect(board.banner).toBe("Open discussion — no agenda.");
    expect(board.people).toHaveLength(3);
  });

  it("caps each notes column and counts the overflow, newest kept", () => {
    const decisions = Array.from({ length: 7 }, (_, i) => `Decision ${i}`);
    const board = reduce(link(active({ digest: { decisions, openItems: ["x".repeat(200)], parked: [{ name: "Tom", summary: "the office move" }] } })), 1_000_000);
    expect(board.notes.decisions).toEqual(["Decision 3", "Decision 4", "Decision 5", "Decision 6"]);
    expect(board.moreNotes.decisions).toBe(3);
    expect(board.notes.open[0]?.length).toBeLessThanOrEqual(LIMITS.note);
    expect(board.notes.parked).toEqual(["Tom: the office move"]);
  });

  it("falls back to raw understanding when there is no digest", () => {
    const board = reduce(link(active({ digest: undefined, understanding: { decisions: ["Ship it"], openItems: ["Who"] }, parked: [{ name: "Ana", summary: "hiring" }] })), 1_000_000);
    expect(board.notes).toEqual({ decisions: ["Ship it"], open: ["Who"], parked: ["Ana: hiring"] });
  });

  it("shows Karen's last spoken line verbatim", () => {
    const state = active({
      interventions: [
        { at: 1, kind: "floorHog", line: "Vitaly, hold that thought.", source: "llm" },
        { at: 2, kind: "mute", source: "rule" },
        { at: 3, kind: "topicOverrun", line: "  We're over on the date.  ", source: "llm" },
      ],
    });
    expect(lastLine(state)).toEqual({ text: "We're over on the date.", kind: "topicOverrun" });
    expect(reduce(link(state), 1_000_000).line?.text).toBe("We're over on the date.");
    expect(reduce(link(active({ interventions: [] })), 1_000_000).line).toBeNull();
  });

  it("survives a nearly empty state object", () => {
    const board = reduce(link({ phase: "active" }), 1_000_000);
    expect(board.mode).toBe("active");
    expect(board.title).toBe("Meeting");
    expect(board.people).toEqual([]);
    expect(board.topics).toEqual([]);
  });

  it("treats a state without a phase as idle", () => {
    const board = reduce(link({} as BrainState), 1_000_000);
    expect(board.mode).toBe("idle");
    expect(board.banner).toBe("No meeting running.");
    expect(board.topicClock).toBeNull();
  });
});
