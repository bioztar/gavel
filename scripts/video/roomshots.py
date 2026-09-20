"""Shots of the meeting room (`/m/<id>`), rendered locally with a stubbed brain state.

The room shipped in 2a508ac/2940614 and is not on the box yet, so the page is rendered
straight from `render_room_page` and the `/state` poll it makes is intercepted with a
state built by `room_state` itself — the real shape, not a hand-written guess.
"""
from __future__ import annotations
import datetime as dt, json, pathlib, sys
sys.path.insert(0, "/Users/alex/DEV/gavel/packages/calendar/src")
from gavel_calendar import room  # noqa: E402
from gavel_calendar.store import InviteRecord  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

OUT = pathlib.Path("/Users/alex/DEV/_assets/gavel-video/shots")
EXE = ("/Users/alex/Library/Caches/ms-playwright/chromium-1217/chrome-mac-arm64/"
       "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing")
START = dt.datetime(2026, 9, 20, 10, 21, tzinfo=dt.UTC)

AGENDA = {
    "purpose": "Walk Artem through the gavel solution and architecture, discuss it openly, "
               "and align on the roadmap.",
    "attendees": [{"discordId": "vitaly", "name": "Vitaly", "role": "host"},
                  {"discordId": "artem", "name": "Artem", "role": "attendee"}],
    "topics": [
        {"id": "t1", "title": "Solution and architecture", "budgetSeconds": 300,
         "owner": "vitaly", "mustHear": ["vitaly"], "type": "presentation"},
        {"id": "t2", "title": "Open discussion", "budgetSeconds": 360,
         "owner": "vitaly", "mustHear": ["vitaly", "artem"], "type": "discussion"},
        {"id": "t3", "title": "Roadmap", "budgetSeconds": 240,
         "owner": "vitaly", "mustHear": ["vitaly"], "type": "presentation"},
    ],
}
RECORD = InviteRecord(session_id="demo", title="Gavel Live Demo", start=START,
                      end=START + dt.timedelta(minutes=15), agenda=AGENDA,
                      started=True, ears_session_id="s1")

# Mid-meeting: topic 2, Artem has held the floor, Karen has already parked one tangent.
BRAIN = {
    "sessionId": "s1", "phase": "chairing", "chairName": "Karen", "chairBusy": False,
    "topic": {"title": "Open discussion", "budgetSeconds": 360, "elapsedSeconds": 214,
              "index": 1},
    "topics": [
        {"title": "Solution and architecture", "budgetSeconds": 300, "type": "presentation",
         "done": True, "discussed": True},
        {"title": "Open discussion", "budgetSeconds": 360, "type": "discussion",
         "done": False, "discussed": True},
        {"title": "Roadmap", "budgetSeconds": 240, "type": "presentation",
         "done": False, "discussed": False},
    ],
    "people": [{"name": "Artem", "role": "attendee", "totalSeconds": 74, "speaking": True},
               {"name": "Vitaly", "role": "host", "totalSeconds": 268, "speaking": False,
                "offAgenda": False}],
    "interventions": [
        {"at": START.isoformat(), "kind": "open",
         "line": "Gavel live demo, fifteen minutes, three topics. Vitaly, the floor is yours."},
        {"at": START.isoformat(), "kind": "redirect",
         "line": "Vitaly, parked for later: cloud pricing. Back to solution and architecture."},
        {"at": START.isoformat(), "kind": "handover",
         "line": "Artem, you are named must-be-heard on this topic and have not spoken yet."},
    ],
    "digest": {
        "facts": ["The interrupt decision is plain code on a 250 ms tick, not a model call.",
                  "Six containers behind Traefik; one of them knows what Discord is."],
        "decisions": ["Teams is the wedge, not Meet or Zoom.",
                      "Discord stays the demo surface for the hackathon."],
        "openItems": ["Per-speaker VAD at the edge before thirty attendees.",
                      "Carry floor state across a voice-websocket reconnect."],
        "parked": [{"name": "Cloud pricing", "summary": "Reserved vs spot across three providers."}],
    },
}

STATE = room.room_state(RECORD, BRAIN)
PAGE = room.render_room_page(RECORD, stage_url="about:blank",
                             discord_url="https://discord.gg/gavel")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE)
    page = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    # served from a real origin, or the page's own relative fetch to /state never routes
    def handler(route, request):
        if request.url.rstrip("/").endswith("/state"):
            route.fulfill(status=200, content_type="application/json", body=json.dumps(STATE))
        else:
            route.fulfill(status=200, content_type="text/html; charset=utf-8", body=PAGE)
    page.route("**/*", handler)
    page.goto("http://gavel.local/m/demo", wait_until="load")
    page.wait_for_timeout(2500)
    # the stage iframe is Karen's video; bake the still in, and hand assemble.py the
    # panel's rectangle so a lip-synced clip can be dropped into the same place
    import base64
    still = base64.b64encode(
        pathlib.Path("/Users/alex/DEV/gavel/packages/chair-video/avatars/karen-formal.png")
        .read_bytes()).decode()
    box = page.locator("#stage").bounding_box()
    (OUT / "room-stage.json").write_text(json.dumps(
        {k: int(round(v)) for k, v in box.items()}, indent=2))
    page.evaluate("""(src) => {
        const f = document.getElementById('stage');
        const img = document.createElement('img');
        img.src = src;
        img.style.cssText = getComputedStyle(f).cssText;
        img.className = f.className;
        img.style.objectFit = 'cover';
        img.style.width = f.getBoundingClientRect().width + 'px';
        img.style.height = f.getBoundingClientRect().height + 'px';
        f.replaceWith(img);
    }""", f"data:image/png;base64,{still}")
    page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / "room-live.png")); print("shot room-live", box)
    page.evaluate("document.getElementById('sheet') && (document.getElementById('sheet').hidden = false)")
    page.wait_for_timeout(400)
    page.screenshot(path=str(OUT / "room-links.png")); print("shot room-links")
    b.close()
