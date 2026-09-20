"""Render the real invite email HTML locally (never sent) and screenshot it."""
from __future__ import annotations
import datetime as dt, pathlib, sys
sys.path.insert(0, "/Users/alex/DEV/gavel/packages/calendar/src")
from gavel_calendar.invite_email import render_invite_html
from playwright.sync_api import sync_playwright

OUT = pathlib.Path("/Users/alex/DEV/_assets/gavel-video/shots")
EXE = ("/Users/alex/Library/Caches/ms-playwright/chromium-1217/chrome-mac-arm64/"
       "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing")

agenda = {
    "purpose": "Walk Artem through the solution and architecture, then decide together "
               "where the roadmap goes next.",
    "attendees": [
        {"discordId": "vitaly", "name": "Vitaly", "role": "host"},
        {"discordId": "artem", "name": "Artem", "role": "attendee"},
    ],
    "topics": [
        {"id": "t1", "title": "Solution and architecture", "budgetSeconds": 360,
         "owner": "vitaly", "mustHear": ["vitaly"], "type": "presentation"},
        {"id": "t2", "title": "Roadmap", "budgetSeconds": 480,
         "owner": "vitaly", "mustHear": ["vitaly", "artem"], "type": "discussion"},
    ],
}
start = dt.datetime(2026, 9, 20, 10, 21)
html = render_invite_html(agenda, title="Gavel Live Demo", start=start,
                          end=start + dt.timedelta(minutes=15),
                          join_url="https://gavel.pro7ocol.com/m/demo",
                          discord_url="https://discord.gg/gavel")
tmp = pathlib.Path("/tmp/claude-501/invite.html"); tmp.parent.mkdir(exist_ok=True, parents=True)
tmp.write_text(f"<div style='max-width:760px;margin:32px auto;font-family:-apple-system,system-ui,sans-serif'>{html}</div>")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE)
    page = b.new_page(viewport={"width": 1920, "height": 1080})
    page.goto(tmp.as_uri()); page.wait_for_timeout(700)
    page.screenshot(path=str(OUT / "invite.png")); print("shot invite")
    page.evaluate("window.scrollTo(0,520)"); page.wait_for_timeout(400)
    page.screenshot(path=str(OUT / "invite-agenda.png")); print("shot invite-agenda")
    b.close()
