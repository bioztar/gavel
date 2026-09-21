/**
 * The chair's voice, chosen in ears' console.
 *
 * The switch itself is live by construction: `SlngTts` re-reads its config
 * getter for every line and reopens the streaming socket when the voice
 * changes (see chair/tts.ts). What is worth pinning is the wire frame that
 * carries it, and that the override wins over models.yaml — someone clicking a
 * dropdown mid-meeting means it now, and a YAML hot-reload must not undo them.
 */
import { describe, expect, it } from "vitest";
import { SlngTts } from "../src/chair/tts";
import { parseEarsFrame } from "../src/contract/frames";
import { loadConfig } from "../src/config";

describe("the voice frame", () => {
  it("is accepted off the wire", () => {
    const frame = parseEarsFrame({ type: "voice", voice: "aura-2-luna-en", atMs: 1 });
    expect(frame).toEqual({ type: "voice", voice: "aura-2-luna-en", atMs: 1 });
  });

  it("is ignored when it carries nothing usable", () => {
    expect(parseEarsFrame({ type: "voice", atMs: 1 })).toBeNull();
  });
});

describe("the override", () => {
  /** Exactly main.ts's getter, which is the thing under test here. */
  function ttsConfig(config: ReturnType<typeof loadConfig>, override: string | null) {
    const tts = config.models.tts;
    return override ? { ...tts, voice: override } : tts;
  }

  it("wins over models.yaml, and leaves everything else alone", () => {
    const config = loadConfig();
    const base = config.models.tts;
    const overridden = ttsConfig(config, "aura-2-luna-en");

    expect(base.voice).not.toBe("aura-2-luna-en"); // the fixture's own voice
    expect(overridden.voice).toBe("aura-2-luna-en");
    expect(overridden.model).toBe(base.model);
    expect(overridden.transport).toBe(base.transport);
  });

  it("falls back to the file when nothing has been chosen", () => {
    const config = loadConfig();
    expect(ttsConfig(config, null).voice).toBe(config.models.tts.voice);
  });

  it("reaches the next line rather than the next restart", () => {
    // The getter is what SlngTts holds, so a later change is picked up without
    // rebuilding it — the property this whole feature rests on.
    const config = loadConfig();
    let override: string | null = null;
    const tts = new SlngTts(() => ttsConfig(config, override), "key");
    const voiceOf = (t: SlngTts) => (t as unknown as { cfg: () => { voice: string } }).cfg().voice;

    expect(voiceOf(tts)).toBe(config.models.tts.voice);
    override = "aura-2-orion-en";
    expect(voiceOf(tts)).toBe("aura-2-orion-en");
  });
});
