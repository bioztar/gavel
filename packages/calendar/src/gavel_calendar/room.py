"""`GET /m/{id}` — the meeting room: one link, before, during and after.

The invite email already points everyone here ("Agenda and live status"), so
this page is the meeting's whole public face. It has three states and one URL:

    before   the agenda, who is expected, and the Join button
    live     Karen's face, the topic clock, the floor, and every call she makes
    after    the report: what was decided, what is open, who held the floor

What it is *not* is the ears console. The console is an operator's instrument —
raw frames, debug events, latencies. This page is for the people in the meeting:
full sentences, no ids, nothing that needs explaining.

`live` is also the answer to "a Discord bot cannot publish video": the page
embeds the chair-video stage, so one participant opens this link and shares the
tab. The room sees Karen while the room reads what she is doing.

The state comes from the brain's `/state` (`packages/brain/src/engine.ts`,
`view()`), fetched server-side — the browser never needs the brain's address,
and the console's HTTP auth stays where it is. The brain holds one live session
at a time and keeps nothing once the next one starts, so every live poll also
banks the snapshot on the invite record: that banked copy *is* the report.
"""

from __future__ import annotations

import html
import json
from datetime import UTC, datetime
from typing import Any

from .agenda import attendee_name
from .compose import _STYLE
from .store import InviteRecord

# How often the page asks for fresh state. Two seconds is under the brain's own
# tick budget for a spoken line, so a call Karen makes is on the page before she
# has finished saying it — and it is one small JSON, not a socket to keep alive.
POLL_SECONDS = 2

# The brain names an intervention for itself (`kind`), in its own vocabulary.
# Nobody in the meeting knows what `floorHog` is; everybody knows what happened.
KIND_LABELS: dict[str, str] = {
    "startMeeting": "Opened the meeting",
    "waitingForPeople": "Waiting for people",
    "addressed": "Answered the room",
    "nextTopic": "Moved to the next topic",
    "topicOverrun": "Topic was over its budget",
    "wrapUp": "Wrapped up",
    "floorHog": "Balanced the floor",
    "offAgenda": "Parked a tangent",
    "groupOffAgenda": "Parked a tangent",
    "otherTopic": "Held a later topic back",
    "groupOtherTopic": "Held a later topic back",
    "escalateFirm": "Repeated the redirect",
    "escalateMute": "Enforced the redirect",
    "newcomer": "Welcomed someone",
    "silence": "Brought someone in",
    "roundRobin": "Went round the room",
    "parked": "Parked a point",
}

PHASE_LABELS: dict[str, str] = {
    "idle": "Not started",
    "gathering": "Gathering",
    "active": "In progress",
    "finished": "Finished",
}


def _label(kind: str) -> str:
    return KIND_LABELS.get(kind, kind[:1].upper() + kind[1:])


def _headlines(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Karen's own log, newest first: what she did, and the words she used."""
    out = []
    for item in reversed(state.get("interventions") or []):
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "at": item.get("at"),
                "kind": item.get("kind", ""),
                "label": _label(str(item.get("kind", ""))),
                "line": item.get("line", ""),
            }
        )
    return out


def _people(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Everyone by talk-time, longest first, each with their share of the floor.

    The share is of *spoken* time, not of the meeting: a quiet meeting should
    still show who did the talking in it.
    """
    people = [p for p in (state.get("people") or []) if isinstance(p, dict)]
    spoken = sum(max(0, int(p.get("totalSeconds") or 0)) for p in people)
    out = []
    for p in people:
        seconds = max(0, int(p.get("totalSeconds") or 0))
        out.append(
            {
                "name": p.get("name") or "—",
                "role": p.get("role") or "",
                "seconds": seconds,
                "share": round(seconds / spoken, 3) if spoken else 0.0,
                "speaking": bool(p.get("speaking")),
                "muted": bool(p.get("muted")),
                "offAgenda": p.get("offAgenda"),
            }
        )
    out.sort(key=lambda p: -p["seconds"])
    return out


def _notes(state: dict[str, Any]) -> dict[str, Any]:
    """Prefer the merged digest — it is the same text the Discord board shows,
    deduplicated by the model — and fall back to the raw understanding."""
    digest = state.get("digest") if isinstance(state.get("digest"), dict) else {}
    understanding = (
        state.get("understanding") if isinstance(state.get("understanding"), dict) else {}
    )
    source = digest or understanding or {}
    parked = []
    for p in source.get("parked") or []:
        if isinstance(p, dict):
            parked.append({"name": p.get("name") or "", "summary": p.get("summary") or ""})
        elif isinstance(p, str):
            parked.append({"name": "", "summary": p})
    return {
        "facts": [str(x) for x in (source.get("facts") or [])],
        "decisions": [str(x) for x in (source.get("decisions") or [])],
        "openItems": [str(x) for x in (source.get("openItems") or [])],
        "parked": parked,
    }


def is_live(record: InviteRecord, brain: dict[str, Any] | None) -> bool:
    """This meeting is what the brain is chairing right now.

    One brain, one session: a state whose `sessionId` is somebody else's meeting
    must never be shown under this link, or two meetings on the same afternoon
    each show the other's talk-time.
    """
    if brain is None or not record.started or record.ears_session_id is None:
        return False
    return brain.get("sessionId") == record.ears_session_id


def room_state(
    record: InviteRecord,
    brain: dict[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """What the page renders — live from the brain, or banked from the last poll."""
    now = now or datetime.now(UTC)
    live = is_live(record, brain)
    state: dict[str, Any] = (brain or {}) if live else (record.last_state or {})

    topics = []
    for t in state.get("topics") or []:
        if isinstance(t, dict):
            topics.append(
                {
                    "title": t.get("title") or "",
                    "budgetSeconds": int(t.get("budgetSeconds") or 0),
                    "type": t.get("type") or "discussion",
                    "done": bool(t.get("done")),
                    "discussed": bool(t.get("discussed")),
                }
            )
    if not topics:  # before the first poll the agenda is still the invite's own
        topics = [
            {
                "title": t.get("title", ""),
                "budgetSeconds": int(t.get("budgetSeconds") or 0),
                "type": t.get("type") or "discussion",
                "done": False,
                "discussed": False,
                "owner": attendee_name(record.agenda, t.get("owner")),
            }
            for t in record.agenda.get("topics", [])
        ]

    if live:
        phase = "live"
    elif state:
        phase = "after"
    else:
        phase = "before"

    topic = state.get("topic") if isinstance(state.get("topic"), dict) else None
    return {
        "phase": phase,
        "chairPhase": state.get("phase") or ("idle" if phase == "before" else "finished"),
        "chairPhaseLabel": PHASE_LABELS.get(str(state.get("phase")), "Not started"),
        "title": record.title,
        "purpose": record.agenda.get("purpose", ""),
        "startsAt": record.start.isoformat(),
        "endsAt": record.end.isoformat(),
        "started": record.started,
        "chairName": state.get("chairName") or "Karen",
        "chairSpeaking": bool(state.get("chairBusy")),
        "missingAttendees": [str(x) for x in (state.get("missingAttendees") or [])],
        "agendaFinished": bool(state.get("agendaFinished")),
        "topic": topic
        and {
            "title": topic.get("title") or "",
            "budgetSeconds": int(topic.get("budgetSeconds") or 0),
            "elapsedSeconds": int(topic.get("elapsedSeconds") or 0),
            "index": int(topic.get("index") or 0),
        },
        "topics": topics,
        "expected": [
            {"name": a.get("name", ""), "role": a.get("role", "")}
            for a in record.agenda.get("attendees", [])
        ],
        "people": _people(state),
        "headlines": _headlines(state),
        "notes": _notes(state),
        "silenceSeconds": int(state.get("silenceSeconds") or 0),
        "updatedAt": now.isoformat(),
    }


def render_room_page(record: InviteRecord, *, stage_url: str, discord_url: str = "") -> str:
    """The shell.

    The agenda is server-rendered into it, so the link is worth opening before
    anything is live and before a byte of JS has run; from the first poll on,
    `_SCRIPT` redraws it and everything else from the JSON.
    """
    e = html.escape
    agenda_rows = "".join(
        f"<li><span>{e(t.get('title', ''))}</span>"
        f"<span class=\"mins\">{int(t.get('budgetSeconds') or 0) // 60} min</span></li>"
        for t in record.agenda.get("topics", [])
    )
    call = (
        f'<a class="button ghost" href="{e(discord_url)}">Join the call</a>' if discord_url else ""
    )
    boot = json.dumps(
        {
            "sessionId": record.session_id,
            "pollSeconds": POLL_SECONDS,
            "stageUrl": stage_url,
        }
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(record.title)} — gavel</title>
<style>{_STYLE}{_ROOM_STYLE}</style></head>
<body class="room"><div class="wide">

<header class="head">
  <p class="eyebrow">gavel &middot; the meeting room</p>
  <h1>{e(record.title)}</h1>
  <p class="lede" id="purpose">{e(record.agenda.get("purpose", ""))}</p>
  <p class="status"><span class="dot" id="dot"></span><span id="phase">Connecting…</span></p>
</header>

<section class="stage-row">
  <div class="stage-box">
    <iframe id="stage" class="stage" src="{e(stage_url)}" title="Karen"
            allow="autoplay; fullscreen" referrerpolicy="no-referrer"></iframe>
    <p class="hint">Share this tab in the call and the room sees her.
       <a href="{e(stage_url)}" target="_blank" rel="noreferrer">Open the face alone</a></p>
  </div>
  <div class="now card">
    <p class="kicker">On now</p>
    <p class="now-topic" id="now-topic">—</p>
    <div class="bar"><span id="topic-bar"></span></div>
    <p class="now-clock" id="now-clock">&nbsp;</p>
    <p class="now-say" id="now-say"></p>
  </div>
</section>

<section class="cols">
  <div>
    <h2>What Karen has done</h2>
    <ol class="feed" id="feed"><li class="empty">Nothing yet.</li></ol>
  </div>
  <div>
    <h2>The floor</h2>
    <ul class="floor" id="floor"><li class="empty">Nobody has spoken yet.</li></ul>
    <h2>Agenda</h2>
    <ol class="agenda" id="agenda">{agenda_rows}</ol>
  </div>
</section>

<section class="cols record-cols">
  <div><h2>Decided</h2><ul class="notes" id="decisions"></ul></div>
  <div><h2>Still open</h2><ul class="notes" id="open"></ul></div>
  <div><h2>Parking lot</h2><ul class="notes" id="parked"></ul></div>
</section>

<section id="facts-block"><h2>Noted</h2><ul class="notes" id="facts"></ul></section>

<div class="actions" id="join-form">
  {call}
  <form method="post" action="/m/{e(record.session_id)}/join">
    <button type="submit" class="ghost">Start the meeting now</button>
  </form>
</div>

<p class="quiet">This page updates itself. Keep it open — after the meeting it becomes
the report.</p>
</div>
<script>const BOOT = {boot};{_SCRIPT}</script>
</body></html>"""


_ROOM_STYLE = """
body.room { padding: 56px 24px 96px; }
.wide { max-width: 1080px; margin: 0 auto; }
.head h1 { font-size: 38px; }
.status { margin: 14px 0 0; font-size: 14px; color: var(--dim); }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
       background: var(--line); margin-right: 8px; vertical-align: middle; }
.dot.on { background: var(--good); box-shadow: 0 0 0 4px rgba(8,116,67,.14); }
.dot.done { background: var(--dim); }
.card { background: var(--surface); border: 1px solid var(--hair); border-radius: 16px;
        padding: 20px 22px; }
.kicker { margin: 0 0 8px; font-size: 11px; font-weight: 590; letter-spacing: .09em;
          text-transform: uppercase; color: var(--dim); }
.stage-row { display: grid; grid-template-columns: 1.35fr 1fr; gap: 20px; margin-top: 34px;
             align-items: start; }
.stage-box { margin: 0; }
.stage { width: 100%; aspect-ratio: 16 / 9; border: 0; border-radius: 16px; background: #000;
         display: block; }
.stage-box .hint { margin-top: 10px; }
.now-topic { margin: 0; font-size: 23px; line-height: 1.25; letter-spacing: -.015em;
             font-weight: 590; }
.bar { height: 5px; border-radius: 3px; background: var(--hair); margin: 14px 0 10px;
       overflow: hidden; }
.bar span { display: block; height: 100%; width: 0; background: var(--accent);
            border-radius: 3px; transition: width .4s ease; }
.bar span.over { background: var(--warn); }
.now-clock { margin: 0; font-size: 14px; color: var(--dim); }
.now-say { margin: 14px 0 0; font-size: 16px; line-height: 1.45; color: var(--ink); }
.now-say:empty { display: none; }
.cols { display: grid; grid-template-columns: 1.35fr 1fr; gap: 20px 34px; }
.record-cols { grid-template-columns: repeat(3, 1fr); }
.feed, .floor, .agenda, .notes { list-style: none; margin: 0; padding: 0; }
.feed li { padding: 14px 0; border-bottom: 1px solid var(--hair); }
.feed .what { font-size: 12px; font-weight: 590; letter-spacing: .06em;
              text-transform: uppercase; color: var(--dim); }
.feed .when { float: right; font-size: 12px; color: var(--dim); font-weight: 400;
              letter-spacing: 0; text-transform: none; }
.feed .line { margin: 6px 0 0; font-size: 17px; line-height: 1.45; }
.floor li { padding: 11px 0; border-bottom: 1px solid var(--hair); }
.floor .who { display: flex; justify-content: space-between; font-size: 15px; }
.floor .who b { font-weight: 500; }
.floor .who span { color: var(--dim); font-size: 13.5px; }
.floor .bar { margin: 8px 0 0; }
.floor .tag { font-size: 12px; color: var(--warn); }
.agenda li { padding: 9px 0; border-bottom: 1px solid var(--hair); font-size: 15.5px;
             display: flex; justify-content: space-between; gap: 12px; }
.agenda li.now { font-weight: 590; }
.agenda li.done { color: var(--dim); text-decoration: line-through; }
.agenda .mins { color: var(--dim); font-size: 13.5px; white-space: nowrap; }
.notes li { padding: 9px 0; border-bottom: 1px solid var(--hair); font-size: 15.5px;
            line-height: 1.45; }
.notes .who { color: var(--dim); font-size: 13px; display: block; }
.empty { color: var(--dim); font-size: 15px; padding: 10px 0; }
.actions { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; }
.actions form { margin: 0; }
.button.ghost, button.ghost { background: var(--surface); color: var(--accent);
                              border: 1px solid var(--line); }
.button.ghost:hover, button.ghost:hover { background: #f2f8ff; }
#join-form[hidden], #facts-block[hidden] { display: none; }
@media (max-width: 860px) {
  .stage-row, .cols, .record-cols { grid-template-columns: 1fr; }
  .head h1 { font-size: 30px; }
}
"""


# No framework and no build step: this file is the whole client. Every value from
# the server goes in through textContent, never innerHTML — a topic title or a
# parked point is someone's typing, and it renders as text or not at all.
_SCRIPT = r"""
const $ = (id) => document.getElementById(id);
const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;

function li(cls) { const n = document.createElement("li"); if (cls) n.className = cls; return n; }
function fill(node, items, make) {
  node.replaceChildren();
  if (!items.length) { const n = li("empty"); n.textContent = "—"; node.append(n); return; }
  for (const item of items) node.append(make(item));
}
function clock(at) {
  if (!at) return "";
  const d = new Date(at);
  return isNaN(d) ? "" : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function render(s) {
  const live = s.phase === "live";
  $("dot").className = "dot" + (live ? " on" : s.phase === "after" ? " done" : "");
  $("phase").textContent = live
    ? (s.chairSpeaking ? `${s.chairName} is speaking` : `Live · ${s.chairPhaseLabel}`)
    : s.phase === "after"
      ? "Finished — this is the report"
      : "Not started yet";
  if (s.purpose) $("purpose").textContent = s.purpose;
  $("join-form").hidden = s.phase !== "before";
  document.querySelector(".stage-row").hidden = s.phase === "before";

  const t = s.topic;
  $("now-topic").textContent = t ? t.title : (s.phase === "after" ? "Meeting over" : "Waiting to start");
  const bar = $("topic-bar");
  if (t && t.budgetSeconds) {
    const ratio = t.elapsedSeconds / t.budgetSeconds;
    bar.style.width = `${Math.min(100, ratio * 100)}%`;
    bar.className = ratio > 1 ? "over" : "";
    $("now-clock").textContent =
      `${mmss(t.elapsedSeconds)} of ${mmss(t.budgetSeconds)}` + (ratio > 1 ? " — over budget" : "");
  } else {
    bar.style.width = "0";
    $("now-clock").textContent = s.missingAttendees.length
      ? `Waiting for ${s.missingAttendees.join(", ")}`
      : "";
  }
  const last = s.headlines[0];
  $("now-say").textContent = live && last ? `“${last.line}”` : "";

  fill($("feed"), s.headlines, (h) => {
    const n = li();
    const head = document.createElement("p");
    head.className = "what";
    const when = document.createElement("span");
    when.className = "when";
    when.textContent = clock(h.at);
    head.textContent = h.label;
    head.append(when);
    const line = document.createElement("p");
    line.className = "line";
    line.textContent = `“${h.line}”`;
    n.append(head, line);
    return n;
  });

  fill($("floor"), s.people, (p) => {
    const n = li();
    const who = document.createElement("p");
    who.className = "who";
    const name = document.createElement("b");
    name.textContent = p.name + (p.speaking ? " · speaking" : "");
    const share = document.createElement("span");
    share.textContent = `${Math.round(p.share * 100)}% · ${mmss(p.seconds)}`;
    who.append(name, share);
    const bar = document.createElement("div");
    bar.className = "bar";
    const fillBar = document.createElement("span");
    fillBar.style.width = `${Math.round(p.share * 100)}%`;
    if (p.share > 0.5) fillBar.className = "over";
    bar.append(fillBar);
    n.append(who, bar);
    if (p.offAgenda) {
      const tag = document.createElement("p");
      tag.className = "tag";
      tag.textContent = `off the agenda: ${p.offAgenda}`;
      n.append(tag);
    }
    return n;
  });

  fill($("agenda"), s.topics, (t) => {
    const current = s.topic && t.title === s.topic.title;
    const n = li(current ? "now" : t.done ? "done" : "");
    const title = document.createElement("span");
    title.textContent = t.title;
    const mins = document.createElement("span");
    mins.className = "mins";
    mins.textContent = `${Math.round(t.budgetSeconds / 60)} min`;
    n.append(title, mins);
    return n;
  });

  const text = (v) => { const n = li(); n.textContent = v; return n; };
  fill($("decisions"), s.notes.decisions, text);
  fill($("open"), s.notes.openItems, text);
  fill($("parked"), s.notes.parked, (p) => {
    const n = li();
    n.textContent = p.summary;
    if (p.name) {
      const who = document.createElement("span");
      who.className = "who";
      who.textContent = `raised by ${p.name}`;
      n.append(who);
    }
    return n;
  });
  fill($("facts"), s.notes.facts, text);
  $("facts-block").hidden = !s.notes.facts.length;
}

async function poll() {
  try {
    const res = await fetch(`/m/${BOOT.sessionId}/state`, { cache: "no-store" });
    if (res.ok) render(await res.json());
  } catch (err) {
    // A dropped poll is a dropped poll: the page keeps the last good view and
    // tries again. Never blank the room because one fetch failed.
  }
  setTimeout(poll, BOOT.pollSeconds * 1000);
}
poll();
"""
