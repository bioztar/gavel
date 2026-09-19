import { describe, expect, it } from "vitest";
import { RelevanceTracker } from "../src/state/relevance";
import { TalkLedger } from "../src/state/talk";
import { render } from "../src/template";
import { config } from "./helpers";

describe("TalkLedger", () => {
  it("totals, per-topic time, rolling window and holding the floor", () => {
    let topic = "t1";
    const l = new TalkLedger(() => topic);
    l.start("a", 0);
    l.end("a", 10_000);
    l.start("b", 11_000);
    l.end("b", 13_000);
    l.start("a", 14_000);
    l.splitAt(20_000); // the engine closes open speech, then moves the topic
    topic = "t2";
    l.end("a", 30_000);
    expect(l.person("a", 30_000, "t1", 120_000)).toMatchObject({ totalMs: 26_000, topicMs: 16_000 });
    expect(l.person("a", 30_000, "t2", 120_000).topicMs).toBe(10_000);
    expect(l.person("a", 30_000, "t1", 5_000).windowMs).toBe(5_000);
    expect(l.holding("a", 31_000, 1_500)).toBe(true);
    expect(l.holding("a", 32_000, 1_500)).toBe(false);
    expect(l.silenceMs(40_000, 0)).toBe(10_000);
  });

  it("counts time still being spoken", () => {
    const l = new TalkLedger(() => "t1");
    l.start("a", 0);
    expect(l.person("a", 7_000, "t1", 60_000)).toMatchObject({ totalMs: 7_000, speaking: true });
    expect(l.silenceMs(7_000, 0)).toBe(0);
  });
});

describe("RelevanceTracker", () => {
  const cfg = () => config.policy.relevance;
  const words = (n: number) => Array.from({ length: n }, (_, i) => `w${i}`).join(" ");

  it("rations calls: enough new words, long enough on the floor, one in flight", () => {
    const r = new RelevanceTracker(cfg);
    r.addTranscript("a", words(5), 0);
    expect(r.due("a", 0, 10_000)).toBe(false);
    r.addTranscript("a", words(8), 0);
    expect(r.due("a", 0, 2_000)).toBe(false);
    expect(r.due("a", 0, 3_000)).toBe(true);
    const { key } = r.begin("a", 0, "t1");
    r.addTranscript("a", words(20), 0);
    expect(r.due("a", 1_000, 5_000)).toBe(false); // in flight
    expect(r.finish("a", 1_000, key, { verdict: "offAgenda", summary: "pricing" })).toBe("opened");
    r.addTranscript("a", words(20), 0);
    expect(r.due("a", 5_000, 9_000)).toBe(false); // episode open: recheck later
    expect(r.due("a", 8_000, 9_000)).toBe(true);
  });

  it("an episode's grace starts at the first words of the drift, not at the verdict", () => {
    const r = new RelevanceTracker(cfg);
    r.addTranscript("a", words(6), 1_000);
    const first = r.begin("a", 2_000, "t1");
    r.addTranscript("a", words(8), 3_000); // said while the call was out
    expect(r.finish("a", 4_000, first.key, { verdict: "current" })).toBeNull();
    r.addTranscript("a", words(8), 5_000);
    const second = r.begin("a", 6_000, "t1");
    expect(r.finish("a", 7_000, second.key, { verdict: "unclear" })).toBeNull();
    const third = r.begin("a", 8_000, "t1");
    expect(r.finish("a", 9_000, third.key, { verdict: "offAgenda", summary: "weather" })).toBe("opened");
    // The run the "current" verdict did not cover began at 3 s.
    expect(r.episode("a")?.offSince).toBe(3_000);
    r.clear("a");
    r.addTranscript("a", words(12), 20_000);
    const fourth = r.begin("a", 21_000, "t1");
    r.finish("a", 22_000, fourth.key, { verdict: "offAgenda", summary: "helicopters" });
    expect(r.episode("a")?.offSince).toBe(20_000);
  });

  it("a failed call hands its words back, retried after a short pause", () => {
    const r = new RelevanceTracker(cfg);
    r.addTranscript("a", words(14), 0);
    const { key } = r.begin("a", 1_000, "t1");
    expect(r.finish("a", 5_000, key, null)).toBeNull(); // timed out
    expect(r.due("a", 5_500, 10_000)).toBe(false);
    expect(r.due("a", 6_000, 10_000)).toBe(true);
  });

  it("opens and closes episodes, and caches identical windows", () => {
    const r = new RelevanceTracker(cfg);
    r.addTranscript("a", "the pricing page needs a full redesign right now please", 0);
    const first = r.begin("a", 0, "t2");
    r.finish("a", 0, first.key, { verdict: "offAgenda", summary: "pricing" });
    expect(r.episode("a")).toMatchObject({ offSince: 0, summary: "pricing" });
    expect(r.begin("a", 10, "t2").cached).toMatchObject({ verdict: "offAgenda" });
    expect(r.finish("a", 20_000, first.key, { verdict: "current" })).toBe("closed");
    expect(r.episode("a")).toBeNull();
  });
});

describe("render", () => {
  it("fills, drops unknowns and tidies spacing", () => {
    expect(render("{{name}}, parked {{summary}} . {{missing}} {{question}}", { name: "Ana", summary: "x", question: "Why?" })).toBe(
      "Ana, parked x. Why?",
    );
  });
});
