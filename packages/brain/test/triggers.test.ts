import { describe, expect, it } from "vitest";
import { pickSpeaker } from "../src/policy/pickSpeaker";
import { evaluate } from "../src/policy/triggers";
import { TOPICS, person, snap } from "./helpers";

const episode = (offSince: number, verdict: "offAgenda" | "otherTopic" = "offAgenda", topicId: string | null = null) => ({
  offSince,
  verdict,
  topicId,
  summary: "pricing page",
  quote: "the pricing page needs a redesign",
});

describe("offAgenda", () => {
  const now = 1_000_000;
  const talking = [person("vit"), person("ana"), person("marc", { holding: true })];

  it("waits out the grace period, then parks and redirects with priority", () => {
    const early = snap({ people: talking, episodes: [{ id: "marc", episode: episode(now - 19_000) }] });
    expect(evaluate(early)).toBeNull();
    const due = evaluate(snap({ people: talking, episodes: [{ id: "marc", episode: episode(now - 20_000) }] }));
    expect(due).toMatchObject({ kind: "offAgenda", targetId: "marc", actions: ["park", "speak"], priority: true, redirects: true });
    expect(due?.park).toMatchObject({ discordId: "marc", summary: "pricing page", topicId: "t1" });
    expect(due?.vars.question).toBe("What slipped?");
  });

  it("does nothing once they stopped talking", () => {
    const quiet = [person("vit"), person("ana"), person("marc")];
    expect(evaluate(snap({ people: quiet, episodes: [{ id: "marc", episode: episode(now - 60_000) }] }))).toBeNull();
  });

  it("a jump to a later topic is acknowledged, not parked", () => {
    const iv = evaluate(snap({ people: talking, episodes: [{ id: "marc", episode: episode(now - 25_000, "otherTopic", "t2") }] }));
    expect(iv).toMatchObject({ kind: "otherTopic", actions: ["speak"] });
    expect(iv?.vars.otherTopicTitle).toBe("The date");
  });

  it("redirects a shared tangent as a group and parks it for everyone involved", () => {
    const episodes = [
      { id: "ana", episode: { ...episode(now - 24_000), summary: "pricing page redesign" } },
      { id: "marc", episode: { ...episode(now - 22_000), summary: "pricing redesign" } },
    ];
    const people = [person("vit"), person("ana"), person("marc", { holding: true })];
    const iv = evaluate(snap({ people, episodes }));
    expect(iv).toMatchObject({ kind: "groupOffAgenda", actions: ["park", "speak"], priority: true });
    expect(iv?.targetId).toBeUndefined();
    expect(iv?.parks?.map((p) => p.discordId)).toEqual(["ana", "marc"]);
  });

  it("holds a redirect once someone else has moved the room on, as in the 2026-09-19 session", () => {
    const ep = [{ id: "marc", episode: episode(now - 25_000) }];
    const people = (anaSaidAt: number) => [
      person("vit"),
      person("ana", { holding: true, lastSaidAt: anaSaidAt }),
      person("marc", { holding: true, lastSaidAt: now - 8_000 }),
    ];
    // Ana spoke up after Marc's last remark: "Marc, …" now would land on her turn.
    expect(evaluate(snap({ people: people(now - 3_000), episodes: ep }))).toBeNull();
    // Ana's words came before Marc's: he is still the one drifting.
    expect(evaluate(snap({ people: people(now - 12_000), episodes: ep }))).toMatchObject({ kind: "offAgenda", targetId: "marc" });
  });

  it("respects the gap between interventions and never talks over itself", () => {
    const ep = [{ id: "marc", episode: episode(now - 30_000) }];
    expect(evaluate(snap({ people: talking, episodes: ep, lastInterventionAt: now - 10_000 }))).toBeNull();
    expect(evaluate(snap({ people: talking, episodes: ep, chairBusy: true }))).toBeNull();
    expect(evaluate(snap({ people: talking, episodes: ep, lastInterventionAt: now - 45_000 }))).not.toBeNull();
  });
});

describe("escalate", () => {
  const now = 1_000_000;
  const redirect = { targetId: "marc", topicId: "t1", spokenAt: now - 10_000 };
  const talking = [person("vit"), person("ana"), person("marc", { holding: true })];

  it("is a firm redirect when muting is not allowed", () => {
    const iv = evaluate(snap({ people: talking, redirect, lastInterventionAt: now - 12_000 }));
    expect(iv).toMatchObject({ trigger: "escalate", kind: "escalateFirm", actions: ["speak"] });
  });

  it("announces and mutes when allowed — exempt from the gap", () => {
    const s = snap({ people: talking, redirect, lastInterventionAt: now - 12_000 });
    s.policy.allowMute = true;
    expect(evaluate(s)).toMatchObject({ kind: "escalateMute", actions: ["speak", "mute"], muteSeconds: 15 });
  });

  it("mutes the host when no role is protected", () => {
    const s = snap({
      people: [person("vit", { holding: true }), person("ana")],
      redirect: { ...redirect, targetId: "vit" },
    });
    s.policy.allowMute = true;
    expect(evaluate(s)?.kind).toBe("escalateMute");
  });

  it("never mutes a role configured as protected", () => {
    const s = snap({
      people: [person("vit", { holding: true }), person("ana")],
      redirect: { ...redirect, targetId: "vit" },
    });
    s.policy.allowMute = true;
    s.engine = { ...s.engine, neverMuteRoles: ["host"] };
    expect(evaluate(s)?.kind).toBe("escalateFirm");
  });

  it("waits escalateAfterSeconds after the chair finished, and honours the cooldown", () => {
    expect(evaluate(snap({ people: talking, redirect: { ...redirect, spokenAt: now - 9_000 } }))).toBeNull();
    expect(evaluate(snap({ people: talking, redirect: { ...redirect, spokenAt: null } }))).toBeNull();
    expect(evaluate(snap({ people: talking, redirect, escalatedAt: { marc: now - 60_000 } }))).toBeNull();
  });
});

describe("silence", () => {
  it("invites mustHear first, by name, with the topic's question", () => {
    const iv = evaluate(snap({ silenceMs: 15_000 }));
    expect(iv).toMatchObject({ kind: "silence", addresseeId: "marc" });
    expect(iv?.vars.notHeardOn).toBe("Status");
  });

  it("not before silenceSeconds", () => {
    expect(evaluate(snap({ silenceMs: 14_000 }))).toBeNull();
  });

  it("runs a round when everyone has spoken on the topic", () => {
    const people = [person("vit", { topicMs: 9_000 }), person("ana", { topicMs: 5_000 }), person("marc", { topicMs: 7_000 })];
    const iv = evaluate(snap({ silenceMs: 20_000, people }));
    expect(iv).toMatchObject({ kind: "roundRobin" });
    expect(iv?.vars.names).toBe("Ana, then Marc, then Vitaly");
  });
});

describe("floorHog", () => {
  it("hands the floor on when one person dominates the window", () => {
    const people = [
      person("vit", { holding: true, windowMs: 70_000, topicMs: 70_000 }),
      person("ana", { windowMs: 10_000, topicMs: 10_000 }),
      person("marc"),
    ];
    const iv = evaluate(snap({ people }));
    expect(iv).toMatchObject({ kind: "floorHog", targetId: "vit", addresseeId: "marc" });
  });

  it("waits for the talker to breathe past the soft threshold, and cuts in past the hard one", () => {
    const soft = [person("vit", { holding: true, windowMs: 70_000 }), person("ana", { windowMs: 10_000 }), person("marc")];
    const s = snap({ people: soft });
    expect(s.policy).toMatchObject({ softHandoverSeconds: 45, hardHandoverSeconds: 90 });
    expect(evaluate(s)).toMatchObject({ kind: "floorHog", priority: false, waitForRoom: true });

    const hard = [person("vit", { holding: true, windowMs: 95_000 }), person("ana", { windowMs: 10_000 }), person("marc")];
    expect(evaluate(snap({ people: hard }))).toMatchObject({ kind: "floorHog", priority: true, waitForRoom: false });
  });

  it("hardHandoverSeconds 0 means she never talks over anyone", () => {
    const people = [person("vit", { holding: true, windowMs: 115_000 }), person("ana", { windowMs: 5_000 }), person("marc")];
    const s = snap({ people });
    s.policy.hardHandoverSeconds = 0;
    expect(evaluate(s)).toMatchObject({ kind: "floorHog", priority: false, waitForRoom: true });
  });

  it("never hands the floor on during a presentation", () => {
    const people = [person("vit", { holding: true, windowMs: 70_000 }), person("ana", { windowMs: 10_000 }), person("marc")];
    const s = snap({ people });
    s.topic = { ...s.topic!, type: "presentation" };
    expect(evaluate(s)).toBeNull();
  });

  it("defers to offAgenda for someone already drifting", () => {
    const people = [person("vit", { holding: true, windowMs: 70_000 }), person("ana", { windowMs: 10_000 }), person("marc")];
    const s = snap({ people, episodes: [{ id: "vit", episode: episode(1_000_000 - 5_000) }] });
    expect(evaluate(s)).toBeNull();
  });
});

describe("topicOverrun", () => {
  it("moves on at budget × factor, and wraps up after the last topic", () => {
    const over = snap({ topicStartedAt: 1_000_000 - 108_000 });
    expect(evaluate(over)).toMatchObject({ kind: "topicOverrun", actions: ["speak", "advance"] });
    expect(evaluate(snap({ topicStartedAt: 1_000_000 - 107_000 }))).toBeNull();
    const last = snap({ topicIndex: 1, topic: TOPICS[1]!, topicStartedAt: 1_000_000 - 144_000, parked: [{ name: "Marc", summary: "pricing" }] });
    const wrap = evaluate(last);
    expect(wrap).toMatchObject({ kind: "wrapUp" });
    expect(wrap?.vars.parkedList).toBe("Marc on pricing");
  });
});

describe("newcomer", () => {
  const now = 1_000_000;
  const joined = (at: number, ...ids: string[]) => ids.map((id) => ({ id, at }));

  it("welcomes someone who came in, once the room has gone quiet, with the question the room is on", () => {
    const iv = evaluate(snap({ arrivals: joined(now - 5_000, "marc"), silenceMs: 4_000, asked: { t1: ["What slipped?"] } }));
    expect(iv).toMatchObject({ trigger: "newcomer", kind: "newcomer", addresseeId: "marc", priority: false, question: undefined });
    expect(iv?.vars).toMatchObject({ name: "Marc", names: "Marc", topicTitle: "Status", question: "What slipped?" });
  });

  it("never talks over anyone, and gives the room a moment first", () => {
    const talking = [person("vit", { holding: true }), person("ana"), person("marc")];
    expect(evaluate(snap({ arrivals: joined(now - 5_000, "marc"), silenceMs: 10_000, people: talking }))).toBeNull();
    expect(evaluate(snap({ arrivals: joined(now - 5_000, "marc"), silenceMs: 3_000 }))).toBeNull();
  });

  it("does not count the newcomer's own hello against the quiet", () => {
    const hello = [person("vit"), person("ana"), person("marc", { holding: true })];
    const iv = evaluate(snap({ arrivals: joined(now - 1_000, "marc"), people: hello, silenceMs: 0, roomSilenceMs: 4_000 }));
    expect(iv).toMatchObject({ kind: "newcomer", addresseeId: "marc" });
    expect(evaluate(snap({ arrivals: joined(now - 1_000, "marc"), people: hello, silenceMs: 0, roomSilenceMs: 3_000 }))).toBeNull();
  });

  it("waits for their audio to connect, and lets the moment go once it has passed", () => {
    expect(evaluate(snap({ arrivals: joined(now - 500, "marc"), silenceMs: 10_000 }))).toBeNull();
    expect(evaluate(snap({ arrivals: joined(now - 91_000, "marc"), silenceMs: 10_000 }))).toBeNull();
  });

  it("fills a pause even right after another line, and welcomes people who came in together", () => {
    const iv = evaluate(snap({ arrivals: [...joined(now - 6_000, "ana"), ...joined(now - 8_000, "marc")], silenceMs: 5_000, lastInterventionAt: now - 10_000 }));
    expect(iv).toMatchObject({ kind: "newcomer", addresseeId: "marc" });
    expect(iv?.vars.names).toBe("Marc and Ana");
    expect(iv?.question).toBe("What slipped?"); // nothing asked yet: a fresh question
  });
});

describe("pickSpeaker", () => {
  it("order: mustHear, then owner, then least on topic; avoids the last speaker and last prompted", () => {
    expect(pickSpeaker(snap())?.person.id).toBe("marc");
    const marcSpoke = snap({ people: [person("vit"), person("ana"), person("marc", { topicMs: 5_000 })] });
    expect(pickSpeaker(marcSpoke)).toMatchObject({ reason: "owner", person: { id: "ana" } });
    expect(pickSpeaker({ ...marcSpoke, lastPromptedId: "ana" })?.person.id).toBe("vit");
    expect(pickSpeaker(snap({ lastSpeakerId: "marc" }))?.person.id).toBe("ana");
  });
});
