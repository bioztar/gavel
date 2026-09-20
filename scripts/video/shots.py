"""Capture real product screenshots for the video: compose, gate, confirm, arch slides, invite."""
from __future__ import annotations
import pathlib, sys
from playwright.sync_api import sync_playwright

OUT = pathlib.Path("/Users/alex/DEV/_assets/gavel-video/shots"); OUT.mkdir(parents=True, exist_ok=True)
BASE = "https://gavel.pro7ocol.com"
THIN = "Karen, set up a meeting with Artem tomorrow at ten. Thirty minutes."
REAL = ("Karen, set up a meeting with Artem in fifteen minutes, fifteen minutes long, called "
        "gavel live demo. Three topics. One: solution and architecture, five minutes, I present it. "
        "Two: open discussion, six minutes - I want both Artem and me heard on it. "
        "Three: roadmap, four minutes, I present it.")
VP = {"width": 1920, "height": 1080}


def shoot(page, name):
    page.wait_for_timeout(900)
    page.screenshot(path=str(OUT / f"{name}.png"))
    print("shot", name, flush=True)


with sync_playwright() as p:
    exe = "/Users/alex/Library/Caches/ms-playwright/chromium-1217/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
    b = p.chromium.launch(executable_path=exe)
    page = b.new_page(viewport=VP, device_scale_factor=1)

    page.goto(f"{BASE}/architecture", wait_until="networkidle")
    shoot(page, "arch1")
    page.keyboard.press("ArrowRight"); page.wait_for_timeout(700); shoot(page, "arch2")
    page.keyboard.press("ArrowRight"); page.wait_for_timeout(700); shoot(page, "arch3")

    page.goto(f"{BASE}/compose", wait_until="networkidle")
    shoot(page, "compose-empty")
    page.fill("#brief", THIN); shoot(page, "compose")
    page.keyboard.press("Enter") if False else page.click("button[type=submit]")
    page.wait_for_load_state("networkidle"); page.wait_for_timeout(2500)
    shoot(page, "gate")

    page.goto(f"{BASE}/compose", wait_until="networkidle")
    page.fill("#brief", REAL)
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle"); page.wait_for_timeout(4000)
    shoot(page, "confirm")
    try:
        page.get_by_text("High", exact=True).first.click(); page.wait_for_timeout(500)
        shoot(page, "confirm-high")
    except Exception as exc:
        print("no High control:", str(exc)[:100], flush=True)
    b.close()
