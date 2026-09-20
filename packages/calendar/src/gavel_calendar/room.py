"""`GET /m/{id}` — the meeting room: one link, before, during and after.

The invite email already points everyone here ("Agenda and live status"), so
this page is the meeting's whole public face. It has three states and one URL:

    before   the agenda, who is expected, and the Join button
    live     Karen's face, the topic clock, the floor, and every call she makes
    after    the report: what was decided, what is open, who held the floor

**It is built to be screen-shared.** The organizer opens this link and shares
the tab, and that is also the answer to "a Discord bot cannot publish video":
the page embeds the chair-video stage, so the room sees Karen's face on the
shared screen while it reads what she is doing.

That is why the default view is a dark, single-screen board — no scrolling, type
in `vh` so it scales to whatever it is shared on, and nothing on it that has to
be read twice. The document version of the same state, for somebody reading on
their own laptop, is one button away (`Detail`, remembered per browser).

What it is *not* is the ears console. The console is an operator's instrument —
raw frames, debug events, latencies. This page is for the people in the meeting:
full sentences, no ids, nothing that needs explaining.

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
    "lobbyGreeting": "Welcomed someone in",
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
        f'<span class="mins">{int(t.get("budgetSeconds") or 0) // 60} min</span></li>'
        for t in record.agenda.get("topics", [])
    )
    # Getting into the voice channel is the one thing anyone arriving at this
    # link may need to *do*, at any point in the meeting — including ten minutes
    # late. It lives in the menu rather than on the board: the board is on a
    # screen the whole room is looking at, and a button nobody in the room can
    # click is just something in the way.
    call = (
        f'<a class="item" href="{e(discord_url)}" target="_blank" rel="noreferrer">'
        f"Join the call</a>"
        if discord_url
        else ""
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
<body class="room share" data-phase="before">

<header class="topbar">
  <p class="brand">{e(record.title)}</p>
  <p class="state"><span class="dot" id="dot"></span><span id="phase">Connecting&hellip;</span>
     <span class="count" id="topic-count"></span></p>
  <span class="spacer"></span>
</header>

<div class="menu">
  <button type="button" class="dots" id="dots" aria-haspopup="true" aria-expanded="false"
          aria-label="Menu" title="Menu">&#8943;</button>
  <div class="sheet" id="sheet" hidden>
    {call}
    <button type="button" class="item" id="copy">Copy this link</button>
    <button type="button" class="item" id="mode">Detail view</button>
    <form method="post" action="/m/{e(record.session_id)}/join" id="join-form">
      <button type="submit" class="item">Start the meeting now</button>
    </form>
  </div>
</div>

<main class="board">
  <section class="video">
    <iframe id="stage" class="stage" src="{e(stage_url)}" title="Karen"
            allow="autoplay; fullscreen" referrerpolicy="no-referrer"></iframe>
    <div class="block agenda-block">
      <p class="kicker">Agenda</p>
      <ol class="agenda" id="agenda">{agenda_rows}</ol>
    </div>
  </section>

  <aside class="side">
    <div class="block now">
      <p class="kicker" id="now-kicker">On now</p>
      <p class="now-topic" id="now-topic">&mdash;</p>
      <div class="bar"><span id="topic-bar"></span></div>
      <p class="now-clock" id="now-clock">&nbsp;</p>
      <p class="speaking" id="speaking"></p>
    </div>
    <div class="block summary-block">
      <p class="kicker" id="summary-kicker">So far on this</p>
      <ul class="summary" id="summary"></ul>
    </div>
  </aside>
</main>

<section class="caption detail-only"><p id="now-say">
  {e(record.agenda.get("purpose", ""))}</p></section>

<footer class="record">
  <div><p class="kicker">Decided</p><ul class="notes" id="decisions"></ul></div>
  <div><p class="kicker">Still open</p><ul class="notes" id="open"></ul></div>
  <div><p class="kicker">Parking lot</p><ul class="notes" id="parked"></ul></div>
</footer>

<div class="detail-only">
  <section class="floor-block"><h2 id="floor-kicker">The floor</h2>
    <ul class="floor" id="floor"><li class="empty">Nobody has spoken yet.</li></ul></section>
  <section><h2>What Karen has done</h2>
    <ol class="feed" id="feed"><li class="empty">Nothing yet.</li></ol></section>
  <section id="facts-block"><h2>Noted</h2><ul class="notes" id="facts"></ul></section>
</div>

<script>const BOOT = {boot};{_SCRIPT}</script>
</body></html>"""


# Two views of one DOM. `share` is the default and the point of the page: one
# screen, no scrollbar, every size in vh so it holds up whether it is shared at
# 720p into a call or thrown on a projector. `detail` is the same state as a
# document, for whoever wants to read it afterwards.
#
# Both are light. A dark board looks better on a laptop and worse everywhere this
# page is actually used: a projector has no black, only "no light", so dark ink
# on white is the only thing that survives a bright room — and a mostly-white
# screen is also what a compressed screen-share keeps sharpest.
_ROOM_STYLE = """
body.room { margin: 0; padding: 0; }
.kicker { margin: 0 0 6px; font-size: 11px; font-weight: 640; letter-spacing: .1em;
          text-transform: uppercase; color: var(--dim); }
.feed, .floor, .agenda, .notes, .summary { list-style: none; margin: 0; padding: 0; }
.bar { height: 6px; border-radius: 4px; background: var(--hair); overflow: hidden; }
.bar span { display: block; height: 100%; width: 0; background: var(--accent);
            border-radius: 3px; transition: width .5s ease; }
.bar span.over { background: var(--warn); }
.spacer { flex: 1; }

/* The menu: everything clickable lives here, out of the room's way. */
.menu { position: fixed; top: 12px; right: 14px; z-index: 10; }
.dots { margin: 0; width: 38px; height: 38px; padding: 0; border-radius: 50%;
        background: transparent; color: var(--dim); border: 1px solid var(--line);
        font-size: 20px; line-height: 1; cursor: pointer; }
.dots:hover, .dots[aria-expanded="true"] { background: var(--surface); color: var(--ink); }
.sheet { position: absolute; top: 46px; right: 0; min-width: 232px; padding: 7px;
         background: #fff; border: 1px solid var(--line); border-radius: 14px;
         box-shadow: 0 14px 40px rgba(0,0,0,.14); display: flex; flex-direction: column; }
.sheet[hidden] { display: none; }
.sheet form { margin: 0; }
.item { display: block; width: 100%; margin: 0; padding: 11px 14px; border: 0;
        border-radius: 9px; background: transparent; color: var(--ink);
        font: inherit; font-size: 15px; text-align: left; text-decoration: none;
        cursor: pointer; }
.item:hover { background: var(--hair); color: var(--ink); text-decoration: none; }
#join-form[hidden], #facts-block[hidden] { display: none; }
.empty { color: var(--dim); }

/* ---- the shared screen ------------------------------------------------- */
body.share {
  /* Whiter and a touch harder than the document palette: a projector eats
     low-contrast greys, and a call's video codec eats fine ones. The "dim"
     grey is darker than the document's for the same reason — at the back of a
     room it is either readable or it is decoration. */
  --bg: #ffffff; --surface: #f4f4f7; --ink: #111116; --dim: #4e4e58;
  --line: #bcbcc6; --hair: #dcdce4;
  /* Everything is sized against the viewport height: this board is read from
     the back of a room, or through a call's video compression, and in both the
     only thing that matters is how big the type is relative to the screen. */
  font-variant-numeric: tabular-nums;
  height: 100vh; overflow: hidden;
  /* Three bands — who/what, the meeting, the record — spread to the edges of
     whatever screen this lands on, rather than one band stretched and a hole
     underneath. */
  display: grid; grid-template-rows: auto auto auto; align-content: space-between;
  gap: 1.6vh; padding: 2.2vh 2.4vw;
}
body.share .detail-only, body.share h1, body.share .lede { display: none; }
body.share .topbar { display: flex; align-items: center; gap: 1.6vw; margin: 0;
                     padding-right: 56px; }
body.share .kicker { font-size: clamp(11px, 1.7vh, 19px); letter-spacing: .12em;
                     margin-bottom: .8vh; }
/* Thick enough to read as a meter from the back of the room, not as a hairline. */
body.share .bar { height: clamp(6px, 1.25vh, 16px); }
body.share .brand { margin: 0; font-size: clamp(19px, 3.2vh, 42px); font-weight: 640;
                    letter-spacing: -.022em; }
body.share .state { margin: 0; font-size: clamp(13px, 2.2vh, 27px); color: var(--dim); }
body.share .count { margin-left: 1.2vw; }
body.detail .count { margin-left: 14px; }
body.share .board { display: grid; grid-template-columns: 0.82fr 2fr; gap: 1.8vw;
                    min-height: 0; }
body.share .video { min-height: 0; display: grid;
                    grid-template-rows: auto minmax(0, 1fr); gap: 1.8vh; }
body.share .stage { width: 100%; aspect-ratio: 16 / 9; height: auto;
                    border: 1px solid var(--hair); border-radius: 14px; background: #000;
                    display: block; }
body.share .side { display: grid; grid-template-rows: auto minmax(0, 1fr);
                   gap: 1.6vh; min-height: 0; }
body.share .block { min-height: 0; }
body.share .now-topic { margin: 0 0 1.4vh; font-size: clamp(26px, 6.4vh, 80px);
                        line-height: 1.04; letter-spacing: -.028em; font-weight: 640; }
body.share .now-clock { margin: 1.1vh 0 0; font-size: clamp(14px, 2.6vh, 32px);
                        color: var(--dim); font-weight: 500; }
/* One line for who has the floor — the meter itself is a thing to study, and
   this board is a thing to glance at. It lives in the detail view. */
body.share .speaking { margin: .9vh 0 0; font-size: clamp(15px, 2.8vh, 34px);
                       font-weight: 590; letter-spacing: -.018em; }
body.share .speaking:empty { display: none; }
body.share .speaking .drift { display: block; margin-top: .4vh; font-size: .68em;
                              font-weight: 500; color: var(--warn); }
/* What the chair has understood about the topic in front of the room. Parked
   points are somebody else's topic by definition and stay out of it. */
body.share .summary-block { display: flex; flex-direction: column; min-height: 0; }
body.share .summary { flex: 1; min-height: 0; overflow: hidden; }
body.share .summary li { padding: .55vh 0; font-size: clamp(15px, 3vh, 38px); line-height: 1.24;
                         letter-spacing: -.016em; display: flex; gap: .7vw; }
body.share .summary li::before { content: "·"; color: var(--dim); }
body.share .summary li.empty { color: var(--dim); font-weight: 400; }
body.share .summary li.empty::before { content: ""; }
/* Nothing the chair says goes on the board. The room can hear her; printed
   next to a live meeting her lines are one more thing pulling eyes off
   whoever is talking. Her log is in the detail view, where it is a record. */
body.share .agenda-block { min-height: 0; overflow: hidden; }
body.share .agenda li { padding: .9vh 0; font-size: clamp(14px, 2.6vh, 32px);
                        line-height: 1.3; display: flex; justify-content: space-between;
                        gap: .8vw; color: var(--dim);
                        border-bottom: 1px solid var(--hair); }
body.share .agenda li.now { color: var(--ink); font-weight: 590; }
body.share .agenda li.done { color: #a0a0aa; text-decoration: line-through; }
body.share .agenda .mins { white-space: nowrap; font-size: .85em; }
/* The record grows all meeting and is what people photograph at the end, so
   it gets whatever the board does not need. */
body.share .record { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.6vw;
                     align-content: start; padding-top: .8vh;
                     border-top: 1px solid var(--hair); overflow: hidden; }
body.share .record .notes li { font-size: clamp(14px, 2.7vh, 34px); line-height: 1.3;
                               padding: .6vh 0; border: 0; letter-spacing: -.012em; }
body.share .record .notes .who { display: block; color: var(--dim); font-size: .7em;
                                 letter-spacing: 0; }
/* After the meeting the picture is dead air — give the record the whole screen. */
body.share[data-phase="after"] .board { grid-template-columns: 1fr; }
body.share[data-phase="after"] .video { display: none; }
body.share[data-phase="after"] .record .notes li { font-size: clamp(13px, 2.2vh, 26px); }

/* ---- the same state as a document -------------------------------------- */
body.detail { padding: 56px 24px 96px; max-width: 1080px; margin: 0 auto; }
body.detail .stage { width: 100%; aspect-ratio: 16 / 9; border: 0; border-radius: 16px;
                     background: #000; display: block; }
body.detail .trail-block { display: none; }
body.detail .board { display: grid; grid-template-columns: 1.35fr 1fr; gap: 24px;
                     margin: 28px 0; align-items: start; }
body.detail .topbar { display: flex; align-items: center; gap: 16px; }
body.detail .brand { margin: 0; font-size: 34px; font-weight: 600; letter-spacing: -.022em; }
body.detail .state { margin: 0; font-size: 14px; color: var(--dim); }
body.detail .block { margin-bottom: 24px; }
body.detail .now-topic { margin: 0 0 12px; font-size: 23px; font-weight: 590;
                         letter-spacing: -.015em; }
body.detail .now-clock { margin: 10px 0 0; font-size: 14px; color: var(--dim); }
body.detail .speaking { margin: 10px 0 0; font-size: 16px; font-weight: 590; }
body.detail .speaking .drift { display: block; margin-top: 3px; font-size: 13px;
                               font-weight: 400; color: var(--warn); }
body.detail .summary li { padding: 10px 0; border-bottom: 1px solid var(--hair);
                          font-size: 15.5px; line-height: 1.45; }
body.detail .floor li, body.detail .agenda li, body.detail .notes li,
body.detail .feed li { padding: 10px 0; border-bottom: 1px solid var(--hair); }
body.detail .floor .who { display: flex; justify-content: space-between; font-size: 15px;
                          margin: 0 0 8px; }
body.detail .floor .who span { color: var(--dim); font-size: 13.5px; }
body.detail .floor .tag { margin: 8px 0 0; font-size: 12.5px; color: var(--warn); }
body.detail .agenda li { display: flex; justify-content: space-between; gap: 12px;
                         font-size: 15.5px; }
body.detail .agenda li.now { font-weight: 590; }
body.detail .agenda li.done { color: var(--dim); text-decoration: line-through; }
body.detail .agenda .mins { color: var(--dim); font-size: 13.5px; white-space: nowrap; }
body.detail .caption p { margin: 0; font-size: 19px; line-height: 1.45; color: var(--dim); }
body.detail .record { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px;
                      margin: 36px 0; }
body.detail .notes li { font-size: 15.5px; line-height: 1.45; }
body.detail .notes .who { display: block; color: var(--dim); font-size: 13px; }
body.detail .feed .what { margin: 0; font-size: 12px; font-weight: 590; letter-spacing: .06em;
                          text-transform: uppercase; color: var(--dim); }
body.detail .feed .when { float: right; font-size: 12px; font-weight: 400; letter-spacing: 0;
                          text-transform: none; }
body.detail .feed .line { margin: 6px 0 0; font-size: 17px; line-height: 1.45; }

.dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%;
       background: var(--line); margin-right: 8px; vertical-align: middle; }
.dot.on { background: var(--good); box-shadow: 0 0 0 4px rgba(51,209,127,.18); }
.dot.done { background: var(--dim); }

/* A phone is not what this is for, but the organizer will open it on one. */
@media (max-width: 760px) {
  body.share { height: auto; overflow: auto; }
  body.share .board, body.share .record { grid-template-columns: 1fr; }
  body.share .stage { aspect-ratio: 16 / 9; height: auto; }
  body.detail .board, body.detail .record { grid-template-columns: 1fr; }
}
"""


# No framework and no build step: this file is the whole client. Every value from
# the server goes in through textContent, never innerHTML — a topic title or a
# parked point is someone's typing, and it renders as text or not at all.
_SCRIPT = r"""
const $ = (id) => document.getElementById(id);
const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
const VIEW_KEY = "gavel.room.view";

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

// Share is the default: this page exists to be put on a screen the whole room
// can see. Detail is a deliberate, sticky choice by one reader on one laptop.
let view = "share";
try { view = localStorage.getItem(VIEW_KEY) === "detail" ? "detail" : "share"; } catch {}
function applyView() {
  document.body.className = `room ${view}`;
  $("mode").textContent = view === "share" ? "Detail view" : "Share view";
}
applyView();

// The menu. Nothing in it is needed by the room watching the screen — it is for
// whoever is driving: get into the call, hand the link on, read the detail, or
// start the meeting before its time.
const sheet = $("sheet");
const dots = $("dots");
function openMenu(open) {
  sheet.hidden = !open;
  dots.setAttribute("aria-expanded", String(open));
}
dots.addEventListener("click", (event) => {
  event.stopPropagation();
  openMenu(sheet.hidden);
});
document.addEventListener("click", (event) => {
  if (!sheet.hidden && !sheet.contains(event.target)) openMenu(false);
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") openMenu(false);
});
$("mode").addEventListener("click", () => {
  view = view === "share" ? "detail" : "share";
  try { localStorage.setItem(VIEW_KEY, view); } catch {}
  applyView();
  openMenu(false);
});
$("copy").addEventListener("click", async () => {
  const done = (ok) => {
    $("copy").textContent = ok ? "Copied" : location.href;
    setTimeout(() => ($("copy").textContent = "Copy this link"), 2500);
  };
  try {
    await navigator.clipboard.writeText(location.href);
    done(true);
  } catch {
    done(false);  // no clipboard permission: show the URL so it can be read off
  }
});

function render(s) {
  const live = s.phase === "live";
  document.body.dataset.phase = s.phase;
  // Starting a meeting that is already running, or is over, is not an offer.
  $("join-form").hidden = s.phase !== "before";
  $("dot").className = "dot" + (live ? " on" : s.phase === "after" ? " done" : "");
  $("phase").textContent = live
    ? (s.chairSpeaking ? `${s.chairName} is speaking` : `Live · ${s.chairPhaseLabel}`)
    : s.phase === "after"
      ? "Finished — this is the report"
      : "Not started yet";

  // "On now" is a lie in both directions once the meeting isn't running.
  $("now-kicker").textContent =
    live ? "On now" : s.phase === "after" ? "The meeting" : "Starting";
  $("floor-kicker").textContent =
    s.phase === "after" ? "Who held the floor" : s.people.length ? "The floor" : "Expected";
  $("summary-kicker").textContent =
    s.phase === "before" ? "Expected" : s.phase === "after" ? "What was established" : "So far on this";

  const t = s.topic;
  const at = t ? s.topics.findIndex((x) => x.title === t.title) : -1;
  $("topic-count").textContent =
    at >= 0 ? `Topic ${at + 1} of ${s.topics.length}` : `${s.topics.length} topics`;
  $("now-topic").textContent =
    t ? t.title : (s.phase === "after" ? "Meeting over" : "Waiting to start");
  const bar = $("topic-bar");
  // No topic, no meter: an empty track under "Meeting over" is furniture.
  bar.parentElement.hidden = !(t && t.budgetSeconds);
  if (t && t.budgetSeconds) {
    const ratio = t.elapsedSeconds / t.budgetSeconds;
    bar.style.width = `${Math.min(100, ratio * 100)}%`;
    bar.className = ratio > 1 ? "over" : "";
    $("now-clock").textContent =
      `${mmss(t.elapsedSeconds)} of ${mmss(t.budgetSeconds)}` + (ratio > 1 ? " — over budget" : "");
  } else {
    // Nothing is on: empty the meter rather than leaving the last topic's fill
    // sitting there under "Meeting over".
    bar.style.width = "0";
    bar.className = "";
    $("now-clock").textContent = s.missingAttendees.length
      ? `Waiting for ${s.missingAttendees.join(", ")}`
      : s.phase === "after"
        ? `${s.topics.length} topics · ${s.notes.decisions.length} decided · ` +
          `${s.notes.openItems.length} still open`
        : "";
  }

  // Who has the room, in one line. The share of the floor rides along because
  // it is the number the chair acts on — but it is a footnote here, not a chart.
  const holder = s.people.find((p) => p.speaking);
  const speaking = $("speaking");
  speaking.replaceChildren();
  if (live && s.chairSpeaking) {
    speaking.textContent = `${s.chairName} is speaking`;
  } else if (live && holder) {
    speaking.textContent = `${holder.name} is speaking · ${Math.round(holder.share * 100)}% of the floor`;
    if (holder.offAgenda) {
      const drift = document.createElement("span");
      drift.className = "drift";
      drift.textContent = `off the agenda: ${holder.offAgenda}`;
      speaking.append(drift);
    }
  } else if (live && s.silenceSeconds > 5) {
    speaking.textContent = `Quiet for ${s.silenceSeconds}s`;
  }

  // What the chair has understood while this topic has been running. Parked
  // points are, by definition, not this topic — they stay in the parking lot.
  // Facts, not decisions: decided and still-open have their own bands along the
  // bottom, and the same sentence twice on one screen is noise.
  const summary =
    s.phase === "before"
      ? s.expected.map((p) =>
          s.missingAttendees.includes(p.name) ? `${p.name} — not here yet` : p.name)
      : s.notes.facts;
  fill($("summary"), summary, (v) => { const n = li(); n.textContent = v; return n; });
  if (!summary.length) {
    const n = li("empty");
    n.textContent = live ? "Nothing captured yet." : "—";
    $("summary").replaceChildren(n);
  }

  // The detail view keeps the chair's own words; the board does not.
  const last = s.headlines[0];
  $("now-say").textContent = last ? `“${last.line}”` : s.purpose;

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

  // Before anyone has spoken the floor is the guest list — who the chair is
  // waiting for is the only thing anyone opening the link early wants to know.
  if (!s.people.length && s.phase !== "after") {
    fill($("floor"), s.expected, (p) => {
      const n = li();
      const who = document.createElement("p");
      who.className = "who";
      const name = document.createElement("b");
      name.textContent = p.name;
      const role = document.createElement("span");
      role.textContent = s.missingAttendees.includes(p.name) ? "not here yet" : p.role;
      who.append(name, role);
      n.append(who);
      return n;
    });
  } else fill($("floor"), s.people, (p) => {
    const n = li();
    const who = document.createElement("p");
    who.className = "who";
    const name = document.createElement("b");
    name.textContent = p.name + (p.speaking ? " · speaking" : "");
    const share = document.createElement("span");
    share.textContent = `${Math.round(p.share * 100)}% · ${mmss(p.seconds)}`;
    who.append(name, share);
    const track = document.createElement("div");
    track.className = "bar";
    const fillBar = document.createElement("span");
    fillBar.style.width = `${Math.round(p.share * 100)}%`;
    if (p.share > 0.5) fillBar.className = "over";
    track.append(fillBar);
    n.append(who, track);
    if (p.offAgenda) {
      const tag = document.createElement("p");
      tag.className = "tag";
      tag.textContent = `off the agenda: ${p.offAgenda}`;
      n.append(tag);
    }
    return n;
  });

  fill($("agenda"), s.topics, (t2) => {
    const current = s.topic && t2.title === s.topic.title;
    const n = li(current ? "now" : t2.done ? "done" : "");
    const title = document.createElement("span");
    title.textContent = t2.title;
    const mins = document.createElement("span");
    mins.className = "mins";
    mins.textContent = `${Math.round(t2.budgetSeconds / 60)} min`;
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
    // tries again. Never blank a screen the whole room is looking at.
  }
  setTimeout(poll, BOOT.pollSeconds * 1000);
}
poll();
"""
