import { describe, expect, it } from "vitest";
import {
  cleanEmail,
  cleanEventId,
  cleanHttpUrl,
  cleanLine,
  cleanMeetCode,
  cleanMinutes,
  cleanText,
  cleanTitle,
  dedupePeople,
  personFrom,
} from "../src/lib/sanitize.js";

describe("cleanText / cleanLine / cleanTitle", () => {
  it("strips control, bidi and zero-width characters, keeps tabs and newlines", () => {
    expect(cleanText("a\u0000b\u202ec\u200bd\te\r\nf")).toBe("abcd\te\nf");
  });
  it("refuses non-strings", () => {
    expect(cleanText(null)).toBe("");
    expect(cleanText({ toString: () => "x" })).toBe("");
  });
  it("caps length", () => {
    expect(cleanTitle("x".repeat(1000))).toHaveLength(300);
    expect(cleanText("x".repeat(20_000))).toHaveLength(8000);
  });
  it("collapses whitespace on a line", () => {
    expect(cleanLine("  Launch \n go /  no-go ")).toBe("Launch go / no-go");
  });
  it("leaves markup as inert text (rendering is textContent-only)", () => {
    expect(cleanTitle('<img src=x onerror="alert(1)">')).toBe('<img src=x onerror="alert(1)">');
  });
});

describe("cleanEmail / personFrom", () => {
  it("lower-cases a real address", () => {
    expect(cleanEmail(" Ana.Ruiz@Example.com ")).toBe("ana.ruiz@example.com");
  });
  it("rejects display strings that are not addresses", () => {
    for (const bad of ["Ana Ruiz <ana@example.com>", "ana@", "@example.com", "a b@example.com", "ana@localhost", "javascript:alert(1)"]) {
      expect(cleanEmail(bad)).toBeNull();
    }
  });
  it("derives a name from the local part when the chip had none", () => {
    expect(personFrom("", "ana.ruiz@example.com")).toEqual({ name: "Ana Ruiz", email: "ana.ruiz@example.com" });
    expect(personFrom("ana@example.com", "ana@example.com")).toEqual({ name: "Ana", email: "ana@example.com" });
  });
  it("is null without a valid address", () => {
    expect(personFrom("Ana", "not-an-email")).toBeNull();
  });
});

describe("dedupePeople", () => {
  it("keeps the first of each address and caps the list", () => {
    const many = Array.from({ length: 300 }, (_, i) => ({ email: `p${i}@example.com` }));
    expect(dedupePeople([{ email: "a@example.com" }, { email: "a@example.com" }, ...many])).toHaveLength(200);
  });
});

describe("cleanMinutes", () => {
  it("accepts whole positive integers only", () => {
    expect(cleanMinutes(" 15 ")).toBe(15);
    for (const bad of ["0", "-5", "1.5", "ten", "", "99999"]) expect(cleanMinutes(bad)).toBeNull();
  });
});

describe("cleanHttpUrl", () => {
  it("accepts https, rejects everything else by default", () => {
    expect(cleanHttpUrl("https://gavel.example.com/join/x")).toBe("https://gavel.example.com/join/x");
    for (const bad of ["javascript:alert(1)", "data:text/html,hi", "http://gavel.example.com", "//evil", "gavel.example.com"]) {
      expect(cleanHttpUrl(bad)).toBeNull();
    }
  });
  it("allows plain http only for localhost, and only when asked", () => {
    expect(cleanHttpUrl("http://localhost:8790/x", true)).toBe("http://localhost:8790/x");
    expect(cleanHttpUrl("http://localhost:8790/x")).toBeNull();
    expect(cleanHttpUrl("http://evil.example.com/", true)).toBeNull();
  });
});

describe("cleanMeetCode / cleanEventId", () => {
  it("accepts only xxx-xxxx-xxx meet codes", () => {
    expect(cleanMeetCode("ABC-defg-hij")).toBe("abc-defg-hij");
    expect(cleanMeetCode("abc-defg-hij/extra")).toBeNull();
    expect(cleanMeetCode("abcd-efg-hij")).toBeNull();
  });
  it("accepts calendar ids including recurring-instance suffixes, rejects paths", () => {
    expect(cleanEventId("abc123def456ghi")).toBe("abc123def456ghi");
    expect(cleanEventId("abc123def456ghi_20260924T120000Z")).toBe("abc123def456ghi_20260924T120000Z");
    expect(cleanEventId("../primary")).toBeNull();
    expect(cleanEventId("a b")).toBeNull();
    expect(cleanEventId("abc")).toBeNull();
  });
});
