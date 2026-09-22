// @ts-check
/**
 * `?demo=1`: the whole board from a fixture, with plausible moving data and no server.
 * The fixture is shaped exactly like brain's GET /state (engine.view()), so what the
 * demo exercises is the real reducer and the real renderer.
 *
 * Scenes, via `?demo=1&scene=…`:
 *   meeting   (default) five people, five topics, one floor hog, the topic runs over
 *   crowd     twelve people incl. a 40-character name, nine topics — the truncation case
 *   gathering the lobby, two people missing
 *   idle      brain up, no session
 *   finished  the agenda is complete
 *   open      an active meeting with an empty agenda
 *   untimed   an agenda with no time budgets
 * `&t=SECONDS` starts the clock that far in; `&link=down` shows the reconnecting marker.
 */

/** @typedef {import("./board.js").BrainState} BrainState */

const P = {
  vitaly: { id: "100000000000000001", name: "Vitaly", role: "host" },
  ana: { id: "100000000000000002", name: "Ana", role: "attendee" },
  marc: { id: "100000000000000003", name: "Marc", role: "attendee" },
  priya: { id: "100000000000000004", name: "Priya", role: "attendee" },
  tom: { id: "100000000000000005", name: "Tom", role: "attendee" },
};

const TOPICS = [
  { id: "t1", title: "Where we actually are", budgetSeconds: 300, owner: P.ana.id },
  { id: "t2", title: "The launch date", budgetSeconds: 480, owner: P.vitaly.id },
  { id: "t3", title: "Blocker owners", budgetSeconds: 360, owner: P.vitaly.id },
  { id: "t4", title: "QA plan and the two-week question", budgetSeconds: 300, owner: P.priya.id },
  { id: "t5", title: "Comms: who tells the customers", budgetSeconds: 240, owner: P.marc.id },
];

/** Who holds the floor, second by second, repeating. Vitaly hogs. */
/** @type {Array<[string, number]>} */
const FLOOR = [
  ["vitaly", 26], ["ana", 7], ["vitaly", 31], ["marc", 9], ["vitaly", 22], ["priya", 6],
  ["vitaly", 18], ["ana", 11], ["vitaly", 27], ["tom", 4], ["vitaly", 24], ["marc", 8],
];
const FLOOR_LEN = FLOOR.reduce((a, [, n]) => a + n, 0);

/** Karen's lines, from t seconds into the demo. */
const LINES = [
  { t: 0, kind: "topicOverrun", line: "Ana, one honest sentence on QA — where are we?" },
  { t: 14, kind: "floorHog", line: "Vitaly, you've had eight of the last ten minutes — Ana, you had a point on this." },
  { t: 42, kind: "topicOverrun", line: "We're over on the date. Marc, name a date you can defend." },
  { t: 75, kind: "offAgenda", line: "Parking the office move, Tom — it's on the list for Thursday." },
  { t: 110, kind: "floorHog", line: "Vitaly, hold that thought. Priya, you haven't had the floor — the QA plan?" },
];

const NOTES = [
  { t: 0, decisions: ["Launch slips one week, not two"], openItems: ["Owner for the payment retry bug"], parked: [] },
  { t: 20, decisions: [], openItems: ["Ana: QA needs two weeks, not one"], parked: [] },
  { t: 45, decisions: ["Marc owns the customer comms"], openItems: [], parked: [] },
  { t: 78, decisions: [], openItems: [], parked: [{ name: "Tom", summary: "the office move" }] },
  { t: 100, decisions: ["Date: Thursday the 9th, said out loud"], openItems: ["Who tells the enterprise accounts"], parked: [] },
  { t: 130, decisions: [], openItems: [], parked: [{ name: "Marc", summary: "hiring a second designer" }] },
];

const BASE_SECONDS = { vitaly: 412, ana: 128, marc: 96, priya: 41, tom: 22 };

/**
 * @param {number} t seconds into the demo
 * @param {Record<string, {id:string,name:string,role:string}>} people
 * @param {number} windowSeconds
 */
function talk(t, people, windowSeconds) {
  const totals = /** @type {Record<string, number>} */ ({});
  const inWindow = /** @type {Record<string, number>} */ ({});
  let speaking = "";
  const full = Math.floor(t / FLOOR_LEN);
  for (const [who, n] of FLOOR) totals[who] = (totals[who] ?? 0) + n * full;
  let cursor = t - full * FLOOR_LEN;
  let pos = 0;
  for (const [who, n] of FLOOR) {
    const take = Math.max(0, Math.min(n, cursor - pos));
    totals[who] = (totals[who] ?? 0) + take;
    if (cursor >= pos && cursor < pos + n) speaking = who;
    pos += n;
  }
  // The window: walk back windowSeconds over the same schedule.
  for (let s = Math.max(0, t - windowSeconds); s < t; s++) {
    const who = holder(s);
    inWindow[who] = (inWindow[who] ?? 0) + 1;
  }
  return Object.keys(people).map((key) => {
    const p = /** @type {{id:string,name:string,role:string}} */ (people[key]);
    return {
      id: p.id,
      name: p.name,
      role: p.role,
      totalSeconds: (BASE_SECONDS[/** @type {keyof typeof BASE_SECONDS} */ (key)] ?? 0) + Math.round(totals[key] ?? 0),
      topicSeconds: Math.round(totals[key] ?? 0),
      windowSeconds: inWindow[key] ?? 0,
      speaking: speaking === key,
      muted: false,
      offAgenda: null,
    };
  });
}
/** @param {number} s */
function holder(s) {
  let cursor = s % FLOOR_LEN;
  for (const [who, n] of FLOOR) {
    if (cursor < n) return who;
    cursor -= n;
  }
  return "vitaly";
}

/** @param {number} t */
function interventions(t) {
  return LINES.filter((l) => l.t <= t).map((l) => ({ at: 1_700_000_000_000 + l.t * 1000, kind: l.kind, line: l.line, source: "llm" }));
}
/** @param {number} t */
function notesAt(t) {
  const out = { decisions: /** @type {string[]} */ ([]), openItems: /** @type {string[]} */ ([]), parked: /** @type {{name:string,summary:string}[]} */ ([]) };
  for (const n of NOTES) {
    if (n.t > t) continue;
    out.decisions.push(...n.decisions);
    out.openItems.push(...n.openItems);
    out.parked.push(...n.parked);
  }
  return out;
}

const POLICY = {
  floorShareThreshold: 0.6, floorWindowSeconds: 120, softHandoverSeconds: 45, hardHandoverSeconds: 90,
  topicOverrunFactor: 1.2, silenceSeconds: 15, minSecondsBetweenInterventions: 45, offAgendaGraceSeconds: 20,
  allowMute: false, escalateAfterSeconds: 30, muteSeconds: 60, requireStart: true, timed: true,
};

/**
 * @param {object} o
 * @param {BrainState["phase"]} o.phase
 * @param {typeof TOPICS} o.topics
 * @param {ReturnType<typeof talk>} o.people
 * @param {number} o.topicIndex
 * @param {number} o.elapsed
 * @param {number} o.t
 * @param {boolean=} o.timed
 * @param {string[]=} o.missing
 * @returns {BrainState}
 */
function view({ phase, topics, people, topicIndex, elapsed, t, timed = true, missing = [] }) {
  const notes = notesAt(phase === "active" || phase === "finished" ? t : -1);
  const current = topics[topicIndex];
  // Cast, not annotated: the fixture carries brain's whole view, including fields the reducer ignores.
  return /** @type {BrainState} */ ({
    sessionId: "demo-session",
    title: "Q4 launch sync",
    purpose: "Decide the launch date and name an owner for each blocker",
    chairName: "Karen",
    phase,
    readyToStart: phase === "gathering" && missing.length === 0,
    requireStart: true,
    timed,
    missingAttendees: missing,
    agendaFinished: phase === "finished",
    topic: phase === "active" && current
      ? { index: topicIndex, id: current.id, title: current.title, budgetSeconds: timed ? current.budgetSeconds : 0, elapsedSeconds: elapsed }
      : null,
    topics: topics.map((tp, i) => ({
      id: tp.id, title: tp.title, budgetSeconds: timed ? tp.budgetSeconds : 0, type: "discussion",
      done: phase === "finished" || (timed && phase === "active" && i < topicIndex), discussed: i <= topicIndex,
      // Not in brain's view today (see docs/STAGE.md); the demo carries it so the column is designed for.
      owner: tp.owner,
    })),
    people,
    persona: { id: "funky", displayName: "Karen" },
    chairBusy: false,
    silenceSeconds: 0,
    parked: notes.parked,
    carried: [],
    understanding: {
      facts: [], decisions: notes.decisions, openItems: notes.openItems,
      later: [...notes.openItems, ...notes.parked.map((p) => p.summary)],
    },
    digest: { decisions: notes.decisions, openItems: notes.openItems, parked: notes.parked },
    interventions: phase === "active" || phase === "finished" ? interventions(t) : [],
    usage: { calls: 12, inputTokens: 18_000, outputTokens: 900, costUsd: 0.0041 },
    policy: POLICY,
  });
}

/**
 * @param {string} scene
 * @param {number} t   seconds into the demo
 * @returns {BrainState}
 */
export function demoState(scene, t) {
  switch (scene) {
    case "crowd": {
      const extra = ["Alexandra Konstantinopoulou-Papadimitriou Jr", "Bartholomew", "Chiara", "Dmitri", "Eleanor", "Faisal", "Gwen"];
      /** @type {Record<string, {id:string,name:string,role:string}>} */
      const people = { ...P };
      extra.forEach((name, i) => {
        people[`x${i}`] = { id: `20000000000000000${i}`, name, role: "attendee" };
      });
      const rows = talk(t, people, POLICY.floorWindowSeconds).map((p, i) => (i < 5 ? p : { ...p, totalSeconds: i === 5 ? 140 : 9 + i * 7 }));
      const topics = [...TOPICS, ...["Hiring plan", "Budget reforecast", "Incident review: Tuesday's outage and what we owe the customers", "AOB"]
        .map((title, i) => ({ id: `t${6 + i}`, title, budgetSeconds: 180, owner: P.tom.id }))];
      return view({ phase: "active", topics, people: rows, topicIndex: 3, elapsed: 130 + t, t });
    }
    case "gathering":
      return view({ phase: "gathering", topics: TOPICS, people: talk(0, { vitaly: P.vitaly, ana: P.ana, marc: P.marc }, 0).map((p) => ({ ...p, totalSeconds: 0, speaking: false })),
        topicIndex: 0, elapsed: 0, t, missing: ["Priya", "Tom"] });
    case "idle":
      return view({ phase: "idle", topics: TOPICS, people: [], topicIndex: 0, elapsed: 0, t });
    case "finished":
      return view({ phase: "finished", topics: TOPICS, people: talk(400, P, POLICY.floorWindowSeconds).map((p) => ({ ...p, speaking: false })), topicIndex: 4, elapsed: 0, t: 400 });
    case "open":
      return view({ phase: "active", topics: [], people: talk(t, P, POLICY.floorWindowSeconds), topicIndex: 0, elapsed: 0, t });
    case "untimed":
      return view({ phase: "active", topics: TOPICS, people: talk(t, P, POLICY.floorWindowSeconds), topicIndex: 1, elapsed: 400 + t, t, timed: false });
    default:
      // Topic 2 of 5, 7:35 into an 8:00 budget: it runs over 25 s into the demo.
      return view({ phase: "active", topics: TOPICS, people: talk(t, P, POLICY.floorWindowSeconds), topicIndex: 1, elapsed: 455 + t, t });
  }
}

/**
 * Drives a Link the way the SSE client would, from the fixture.
 * @param {import("./board.js").Link} link
 * @param {URLSearchParams} params
 * @param {() => number} now
 */
export function runDemo(link, params, now = Date.now) {
  const scene = params.get("scene") ?? "meeting";
  const offset = Number(params.get("t") ?? 0) || 0;
  const down = params.get("link") === "down";
  // `owners=0` shows the shape brain publishes today (no topic owners), `owners=some` a mix.
  const owners = params.get("owners");
  const started = now();
  const tick = () => {
    const t = offset + (now() - started) / 1000;
    const s = demoState(scene, Math.floor(t));
    if (owners === "0" || owners === "some") {
      s.topics = (s.topics ?? []).map((tp, i) => (owners === "some" && i % 2 ? tp : { ...tp, owner: undefined }));
    }
    link.state = s;
    link.receivedAt = down ? started - 41_000 : now();
    link.connected = !down;
    link.brainOk = !down;
  };
  tick();
  return setInterval(tick, 1000);
}
