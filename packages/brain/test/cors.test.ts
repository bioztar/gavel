import { describe, expect, it } from "vitest";
import { corsHeaders, parseOrigins } from "../src/cors";

describe("GET /state CORS", () => {
  it("is same-origin by default: no header for any cross-origin page", () => {
    expect(corsHeaders("https://stage.example", [])).toEqual({});
    expect(corsHeaders(undefined, [])).toEqual({});
  });

  it("echoes an allowlisted origin only, exactly", () => {
    const allowed = parseOrigins(" https://stage.example, http://localhost:5173/ ");
    expect(allowed).toEqual(["https://stage.example", "http://localhost:5173"]);
    expect(corsHeaders("https://stage.example", allowed)).toEqual({
      "access-control-allow-origin": "https://stage.example",
      vary: "origin",
    });
    expect(corsHeaders("http://localhost:5173", allowed)["access-control-allow-origin"]).toBe("http://localhost:5173");
    expect(corsHeaders("https://evil.example", allowed)).toEqual({});
    expect(corsHeaders("http://stage.example", allowed)).toEqual({});
  });

  it("still lets an operator spell out the wildcard", () => {
    expect(corsHeaders("https://anything", parseOrigins("*"))).toEqual({ "access-control-allow-origin": "*" });
  });
});
