import { describe, expect, it } from "vitest";
import { Conversation } from "../src/state/conversation";

describe("the channel conversation", () => {
  it("keeps lines in the order they were said, whatever order they arrive in", () => {
    const c = new Conversation();
    c.add({ at: 3_000, id: "g", name: "Gipzo", text: "I think planes are better." });
    c.add({ at: 1_000, id: "b", name: "bioztar", text: "Play." });
    c.add({ at: 4_000, id: "karen", name: "Karen", text: "Back to cats and dogs." });
    expect(c.tail(5_000, { seconds: 60, maxWords: 100 })).toBe(
      "bioztar: Play.\nGipzo: I think planes are better.\nKaren: Back to cats and dogs.",
    );
  });

  it("keeps the newest lines inside the word and time budget, and can leave one person out", () => {
    const c = new Conversation();
    c.add({ at: 0, id: "a", name: "Ana", text: "too old to matter" });
    c.add({ at: 100_000, id: "a", name: "Ana", text: "one two three" });
    c.add({ at: 101_000, id: "m", name: "Marc", text: "four five" });
    c.add({ at: 102_000, id: "a", name: "Ana", text: "six" });
    expect(c.tail(110_000, { seconds: 60, maxWords: 3 })).toBe("Marc: four five\nAna: six");
    expect(c.tail(110_000, { seconds: 60, maxWords: 100, except: "a" })).toBe("Marc: four five");
    expect(c.tail(110_000, { seconds: 60, maxWords: 0 })).toBe("");
  });
});
