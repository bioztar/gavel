"""Scrolled confirm states + the invite email, rendered locally (never sent)."""
from __future__ import annotations
import pathlib, sys
sys.path.insert(0, "/Users/alex/DEV/gavel/packages/calendar/src")
from playwright.sync_api import sync_playwright

OUT = pathlib.Path("/Users/alex/DEV/_assets/gavel-video/shots")
BASE = "https://gavel.pro7ocol.com"
REAL = ("Karen, set up a meeting with Artem in fifteen minutes, fifteen minutes long, called "
        "gavel live demo. Three topics. One: solution and architecture, five minutes, I present it. "
        "Two: open discussion, six minutes - I want both Artem and me heard on it. "
        "Three: roadmap, four minutes, I present it.")
EXE = ("/Users/alex/Library/Caches/ms-playwright/chromium-1217/chrome-mac-arm64/"
       "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE)
    page = b.new_page(viewport={"width": 1920, "height": 1080})
    page.goto(f"{BASE}/compose", wait_until="networkidle")
    page.fill("#brief", REAL)
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle"); page.wait_for_timeout(4000)
    page.evaluate("window.scrollTo(0, 820)"); page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / "confirm-table.png")); print("shot confirm-table")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)"); page.wait_for_timeout(600)
    page.screenshot(path=str(OUT / "confirm-gauge.png")); print("shot confirm-gauge")
    try:
        page.get_by_text("High", exact=True).first.click(); page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "confirm-high.png")); print("shot confirm-high")
    except Exception as e:
        print("high:", str(e)[:80])
    b.close()
