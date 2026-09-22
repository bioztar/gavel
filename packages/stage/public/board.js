// @ts-check
/**
 * Brain state → what the screen shows. Pure: no DOM, no clock of its own.
 *
 * Input is the JSON of brain's GET /state (engine.view() in packages/brain/src/engine.ts),
 * plus the moment it was received and the moment it is being drawn, so clocks keep running
 * between updates. Output is a fixed-shape view model that the renderer paints one to one.
 *
 * Every list is capped here, not in CSS, so the caps are testable: the board is a video of
 * a page and can never scroll or push anything off screen.
 */

export const LIMITS = Object.freeze({
  /** Rows on the talk-time board. The speaker is always one of them. */
  people: 8,
  /** Rows on the agenda. The live topic is always one of them. */
  topics: 7,
  /** Items per notes column (decisions, open items, parking lot). */
  notes: 4,
  /** Characters of a person's name before an ellipsis. */
  name: 18,
  /** Characters of a topic title. */
  topic: 44,
  /** Characters of one note. */
  note: 72,
  /** Characters of Karen's line — brain caps its own at 320. */
  line: 200,
  /** Characters of the meeting title. */
  title: 60,
});

/**
 * @typedef {object} BrainTopic
 * @property {string} id
 * @property {string} title
 * @property {number} budgetSeconds
 * @property {string=} type
 * @property {boolean} done
 * @property {boolean=} discussed
 * @property {(string|null)=} owner   discordId — not in brain's view today; shown when it is
 * @property {(string|null)=} ownerName
 */
/**
 * @typedef {object} BrainPerson
 * @property {string} id
 * @property {string} name
 * @property {string=} role
 * @property {number} totalSeconds
 * @property {number=} topicSeconds
 * @property {number=} windowSeconds
 * @property {boolean} speaking
 * @property {boolean=} muted
 */
/**
 * @typedef {object} BrainState
 * @property {(string|null)=} sessionId
 * @property {(string|null)=} title
 * @property {string=} purpose
 * @property {string=} chairName
 * @property {"idle"|"gathering"|"active"|"finished"} phase
 * @property {boolean=} readyToStart
 * @property {boolean=} requireStart
 * @property {boolean=} timed
 * @property {string[]=} missingAttendees
 * @property {boolean=} agendaFinished
 * @property {({index:number,id:string,title:string,budgetSeconds:number,elapsedSeconds:number}|null)=} topic
 * @property {BrainTopic[]=} topics
 * @property {BrainPerson[]=} people
 * @property {{id?:string,displayName?:string}=} persona
 * @property {Array<{name:string,summary:string}>=} parked
 * @property {{facts?:string[],decisions?:string[],openItems?:string[],later?:string[]}=} understanding
 * @property {{decisions?:string[],openItems?:string[],parked?:Array<{name:string,summary:string}>}=} digest
 * @property {Array<{at:number,kind:string,line?:string,source?:string}>=} interventions
 * @property {{floorShareThreshold?:number,floorWindowSeconds?:number,timed?:boolean}=} policy
 */

/**
 * @typedef {object} Link
 * @property {BrainState|null} state      last state received, or null before the first one
 * @property {number} receivedAt          Date.now() when `state` arrived
 * @property {boolean} connected          the SSE stream is open
 * @property {boolean} brainOk            the server could reach brain on its last poll
 */

/**
 * @typedef {object} PersonRow
 * @property {string} id
 * @property {string} name
 * @property {number} seconds
 * @property {number} share           0..1 of all talk this meeting
 * @property {number} windowShare     0..1 of talk in the policy's floor window
 * @property {boolean} speaking
 * @property {boolean} hog            over the policy's share threshold
 * @property {boolean} muted
 */
/**
 * @typedef {object} TopicRow
 * @property {string} id
 * @property {number} n                1-based position on the agenda
 * @property {string} title
 * @property {string} owner
 * @property {number} budgetSeconds
 * @property {"done"|"live"|"next"} status
 * @property {number|null} elapsedSeconds   live topic only
 * @property {boolean} over                  live topic, past its budget
 * @property {boolean} presentation
 */
/**
 * @typedef {object} Board
 * @property {"empty"|"idle"|"gathering"|"active"|"finished"} mode
 * @property {string} title
 * @property {string} subtitle
 * @property {string} chair
 * @property {string} banner        one legible sentence when there is nothing live to show
 * @property {{ text: string, kind: string } | null} line
 * @property {{ elapsedSeconds: number, budgetSeconds: number, over: boolean, timed: boolean } | null} topicClock
 * @property {{ remainingSeconds: number, totalSeconds: number, over: boolean } | null} meetingClock
 * @property {PersonRow[]} people
 * @property {{ count: number, share: number } | null} morePeople
 * @property {string | null} speaker
 * @property {TopicRow[]} topics
 * @property {{ done: number, next: number }} moreTopics
 * @property {number} threshold
 * @property {{ decisions: string[], open: string[], parked: string[] }} notes
 * @property {{ decisions: number, open: number, parked: number }} moreNotes
 * @property {{ connected: boolean, brainOk: boolean, staleSeconds: number, label: string | null }} link
 */

/**
 * @param {string | null | undefined} text
 * @param {number} max
 */
export function clip(text, max) {
  const s = String(text ?? "").replace(/\s+/g, " ").trim();
  if (s.length <= max) return s;
  // Cut at a word if one is close enough; never leave a dangling half-word.
  const head = s.slice(0, max - 1);
  const atWord = head.replace(/\s+\S*$/, "");
  return (atWord.length >= max * 0.6 ? atWord : head) + "…";
}

/**
 * Magnitude only — the screen never shows a signed duration. A counter that has gone past
 * zero says so in words ("7:57 over"), never with a minus the room has to reason about.
 * @param {number} seconds
 */
export function mmss(seconds) {
  const s = Math.max(0, Math.round(Math.abs(seconds)));
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
}

/**
 * @param {BrainPerson[]} people
 * @param {number} threshold
 * @returns {{ rows: PersonRow[], more: Board["morePeople"], speaker: string | null }}
 */
export function reducePeople(people, threshold) {
  const total = people.reduce((a, p) => a + Math.max(0, p.totalSeconds || 0), 0);
  const windowTotal = people.reduce((a, p) => a + Math.max(0, p.windowSeconds || 0), 0);
  /** @type {PersonRow[]} */
  const rows = people
    .map((p) => {
      const seconds = Math.max(0, p.totalSeconds || 0);
      const share = total > 0 ? seconds / total : 0;
      const windowShare = windowTotal > 0 ? Math.max(0, p.windowSeconds || 0) / windowTotal : 0;
      return {
        id: p.id,
        name: clip(p.name, LIMITS.name) || "—",
        seconds,
        share,
        windowShare,
        speaking: !!p.speaking,
        // The policy's own test is the window; whole-meeting share is the room's intuition.
        // Either one past the threshold reads as hogging.
        hog: threshold > 0 && (windowShare >= threshold || share >= threshold),
        muted: !!p.muted,
      };
    })
    .sort((a, b) => b.seconds - a.seconds || Number(b.speaking) - Number(a.speaking) || a.name.localeCompare(b.name));
  const speaker = rows.find((r) => r.speaking)?.name ?? null;
  if (rows.length <= LIMITS.people) return { rows, more: null, speaker };
  // Keep the top rows; the speaker is promoted into the last visible slot if it fell below.
  const visible = rows.slice(0, LIMITS.people);
  const rest = rows.slice(LIMITS.people);
  const speakingIdx = rest.findIndex((r) => r.speaking);
  if (speakingIdx >= 0 && !visible.some((r) => r.speaking)) {
    const bumped = /** @type {PersonRow} */ (visible.pop());
    rest.splice(speakingIdx, 1);
    visible.push(/** @type {PersonRow} */ (rows.find((r) => r.speaking)));
    rest.unshift(bumped);
  }
  return {
    rows: visible,
    more: { count: rest.length, share: rest.reduce((a, r) => a + r.share, 0) },
    speaker,
  };
}

/**
 * @param {BrainState} state
 * @returns {boolean}
 */
export function isTimed(state) {
  return (state.timed ?? state.policy?.timed) !== false;
}

/**
 * @param {BrainState} state
 * @returns {BrainState["phase"]}
 */
export function phaseOf(state) {
  return state.phase ?? "idle";
}

/**
 * @param {BrainState} state
 * @param {Map<string,string>} names  discordId → display name
 * @param {number} liveElapsed
 * @returns {{ rows: TopicRow[], more: Board["moreTopics"] }}
 */
export function reduceTopics(state, names, liveElapsed) {
  const timed = isTimed(state);
  const phase = phaseOf(state);
  const liveIndex = phase === "active" && state.topic ? state.topic.index : -1;
  /** @type {TopicRow[]} */
  const all = (state.topics ?? []).map((t, i) => {
    const live = i === liveIndex;
    const owner = t.ownerName ?? (t.owner ? (names.get(t.owner) ?? "") : "");
    return {
      id: t.id,
      n: i + 1,
      title: clip(t.title, LIMITS.topic) || `Topic ${i + 1}`,
      owner: clip(owner, LIMITS.name),
      budgetSeconds: t.budgetSeconds || 0,
      status: t.done || (phase === "finished" && state.agendaFinished) ? "done" : live ? "live" : "next",
      elapsedSeconds: live ? liveElapsed : null,
      over: live && timed && t.budgetSeconds > 0 && liveElapsed > t.budgetSeconds,
      presentation: t.type === "presentation",
    };
  });
  if (all.length <= LIMITS.topics) return { rows: all, more: { done: 0, next: 0 } };
  // A window of LIMITS.topics rows around the live topic: the live row, then as many
  // upcoming as fit, then whatever is left for the recently finished ones. Anything
  // outside the window is counted, not listed.
  const anchor = liveIndex >= 0 ? liveIndex : all.findIndex((t) => t.status !== "done");
  const centre = anchor >= 0 ? anchor : all.length - 1;
  const after = all.length - centre - 1;
  const wantAfter = Math.min(after, Math.ceil((LIMITS.topics - 1) * 0.6));
  const before = Math.min(centre, LIMITS.topics - 1 - wantAfter);
  const nextCount = Math.min(after, LIMITS.topics - 1 - before);
  const start = centre - before;
  const end = centre + nextCount + 1;
  return {
    rows: all.slice(start, end),
    more: { done: start, next: all.length - end },
  };
}

/**
 * @param {string[] | undefined} items
 * @returns {{ rows: string[], more: number }}
 */
function reduceNotes(items) {
  const list = (items ?? []).map((x) => clip(x, LIMITS.note)).filter(Boolean);
  // Newest last in brain; the screen shows the most recent ones, newest first, so a column
  // that runs out of room loses the oldest into its `+N more` row.
  const rows = list.slice(-LIMITS.notes).reverse();
  return { rows, more: list.length - rows.length };
}

/**
 * @param {BrainState} state
 * @returns {Board["line"]}
 */
export function lastLine(state) {
  const spoken = (state.interventions ?? []).filter((iv) => iv.line && iv.line.trim());
  const last = spoken[spoken.length - 1];
  if (!last) return null;
  return { text: clip(last.line, LIMITS.line), kind: last.kind };
}

/**
 * @param {Link} link
 * @param {number} now   Date.now() at draw time
 * @returns {Board}
 */
export function reduce(link, now) {
  const stale = link.state ? Math.max(0, Math.round((now - link.receivedAt) / 1000)) : 0;
  const linkLabel = !link.state
    ? null
    : !link.connected
      ? `reconnecting · last update ${mmss(stale)} ago`
      : !link.brainOk
        ? `brain unreachable · showing ${mmss(stale)} ago`
        : stale > 30 && phaseOf(link.state) === "active"
          ? `no update for ${mmss(stale)}`
          : null;
  const linkInfo = { connected: link.connected, brainOk: link.brainOk, staleSeconds: stale, label: linkLabel };

  /** @type {Board} */
  const empty = {
    mode: "empty",
    title: "gavel",
    subtitle: "",
    chair: "Karen",
    banner: link.connected ? "Karen is getting ready…" : "Connecting to the meeting…",
    line: null,
    topicClock: null,
    meetingClock: null,
    people: [],
    morePeople: null,
    speaker: null,
    topics: [],
    moreTopics: { done: 0, next: 0 },
    threshold: 0.6,
    notes: { decisions: [], open: [], parked: [] },
    moreNotes: { decisions: 0, open: 0, parked: 0 },
    link: linkInfo,
  };
  const state = link.state;
  if (!state) return empty;

  const timed = isTimed(state);
  const phase = phaseOf(state);
  const threshold = state.policy?.floorShareThreshold ?? 0.6;
  // Clocks keep running between updates; the live topic's elapsed time is what brain saw
  // plus the time since — but only while the meeting is live.
  const drift = phase === "active" ? Math.max(0, (now - link.receivedAt) / 1000) : 0;
  const people = state.people ?? [];
  const names = new Map(people.map((p) => [p.id, p.name]));
  const liveElapsed = state.topic ? Math.max(0, state.topic.elapsedSeconds + drift) : 0;

  const { rows: personRows, more: morePeople, speaker } = reducePeople(people, threshold);
  const { rows: topicRows, more: moreTopics } = reduceTopics(state, names, liveElapsed);

  const topics = state.topics ?? [];
  const total = topics.reduce((a, t) => a + (t.budgetSeconds || 0), 0);
  /** @type {Board["topicClock"]} */
  let topicClock = null;
  /** @type {Board["meetingClock"]} */
  let meetingClock = null;
  if (phase === "active" && state.topic) {
    const budget = timed ? state.topic.budgetSeconds : 0;
    topicClock = { elapsedSeconds: liveElapsed, budgetSeconds: budget, over: timed && budget > 0 && liveElapsed > budget, timed };
    if (timed && total > 0) {
      // Time left by the plan: what is left of this topic's budget plus the budgets of
      // everything not yet reached. Brain publishes no meeting start time, so this is
      // the honest number the screen can compute from the state alone.
      const ahead = topics.slice(state.topic.index + 1).reduce((a, t) => a + (t.budgetSeconds || 0), 0);
      const remaining = budget - liveElapsed + ahead;
      meetingClock = { remainingSeconds: remaining, totalSeconds: total, over: remaining < 0 };
    }
  }

  const decisions = reduceNotes(state.digest?.decisions ?? state.understanding?.decisions);
  const open = reduceNotes(state.digest?.openItems ?? state.understanding?.openItems);
  const parkedSource = state.digest?.parked ?? state.parked ?? [];
  const parked = reduceNotes(parkedSource.map((p) => (p.name ? `${p.name}: ${p.summary}` : p.summary)));

  const chair = state.persona?.displayName || state.chairName || "Karen";
  const title = clip(state.title || state.purpose || "Meeting", LIMITS.title);
  const subtitle = state.title && state.purpose ? clip(state.purpose, 90) : "";

  /** @type {Board["mode"]} */
  let mode = phase;
  let banner = "";
  if (phase === "idle") {
    banner = topics.length ? "No meeting running. The agenda is ready." : "No meeting running.";
  } else if (phase === "gathering") {
    const missing = state.missingAttendees ?? [];
    banner = missing.length
      ? `Waiting for ${clip(missing.join(", "), 80)}`
      : state.readyToStart
        ? state.requireStart === false
          ? `Everyone is here. ${chair} is opening the meeting…`
          : `Everyone is here. Say “${chair}, let's start the meeting.”`
        : "Gathering…";
  } else if (phase === "finished") {
    banner = "Agenda complete. Thank you.";
  } else if (phase === "active" && !topics.length) {
    banner = "Open discussion — no agenda.";
  }

  return {
    mode,
    title,
    subtitle,
    chair,
    banner,
    line: lastLine(state),
    topicClock,
    meetingClock,
    people: personRows,
    morePeople,
    speaker,
    topics: topicRows,
    moreTopics,
    threshold,
    notes: { decisions: decisions.rows, open: open.rows, parked: parked.rows },
    moreNotes: { decisions: decisions.more, open: open.more, parked: parked.more },
    link: linkInfo,
  };
}
