"""Element-level focus shots — the dial, the agenda table, the gate box, the invite table.

Whole-page screenshots make the thing being narrated a small patch of a 1920px frame.
These crop to the element itself so the cut can hold still on exactly what is being said.
"""
from __future__ import annotations
import datetime as dt, pathlib, sys
sys.path.insert(0, "/Users/alex/DEV/gavel/packages/calendar/src")
from playwright.sync_api import sync_playwright

OUT = pathlib.Path("/Users/alex/DEV/_assets/gavel-video/shots")
BASE = "https://gavel.pro7ocol.com"
REAL = ("Karen, set up a meeting with Artem in fifteen minutes, fifteen minutes long, called "
        "gavel live demo. Three topics. One: solution and architecture, five minutes, I present it. "
        "Two: open discussion, six minutes - I want both Artem and me heard on it. "
        "Three: roadmap, four minutes, I present it.")
THIN = "Karen, set up a meeting with Artem tomorrow at ten. Thirty minutes."
EXE = ("/Users/alex/Library/Caches/ms-playwright/chromium-1217/chrome-mac-arm64/"
       "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing")
PAD = 34


def shoot(page, selector: str, name: str, nth: int = 0) -> None:
    box = page.locator(selector).nth(nth).bounding_box()
    if box is None:
        print("MISSING", name, selector); return
    page.screenshot(path=str(OUT / f"{name}.png"), clip={
        "x": max(box["x"] - PAD, 0), "y": max(box["y"] - PAD, 0),
        "width": box["width"] + PAD * 2, "height": box["height"] + PAD * 2})
    print("shot", name, f'{int(box["width"])}x{int(box["height"])}')


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE)
    page = b.new_page(viewport={"width": 1600, "height": 1200}, device_scale_factor=2)

    page.goto(f"{BASE}/compose", wait_until="networkidle")
    page.fill("#brief", THIN); page.click("button[type=submit]")
    page.wait_for_load_state("networkidle"); page.wait_for_timeout(2500)
    shoot(page, "h1", "focus-gate-headline")
    shoot(page, ".page", "focus-gate")

    page.goto(f"{BASE}/compose", wait_until="networkidle")
    page.fill("#brief", REAL); page.click("button[type=submit]")
    page.wait_for_load_state("networkidle"); page.wait_for_timeout(4000)
    shoot(page, "table", "focus-agenda")
    page.locator("label[for=enf_high]").click(); page.wait_for_timeout(400)
    shoot(page, ".seg", "focus-gauge")
    b.close()

# The host-is-not-exempt wording ships in this repo but is not on the box yet, so the
# gauge shot is taken from the live page's own HTML with that one line swapped.
OLD_HINT = "You are the host, so she will never mute you."
NEW_HINT = ("Nobody is exempt, including you. If the host is the one running over, "
            "the host is the one who gets chaired.")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE)
    page = b.new_page(viewport={"width": 1600, "height": 1200}, device_scale_factor=2)
    page.goto(f"{BASE}/compose", wait_until="networkidle")
    page.fill("#brief", REAL); page.click("button[type=submit]")
    page.wait_for_load_state("networkidle"); page.wait_for_timeout(4000)
    page.locator("label[for=enf_high]").click(); page.wait_for_timeout(300)
    html = page.content()
    assert OLD_HINT in html, "hint text moved - check compose.py"
    page.set_content(html.replace(OLD_HINT, NEW_HINT), wait_until="load")
    # set_content re-renders from source, so the High selection has to be made again
    page.locator("label[for=enf_high]").click()
    page.wait_for_timeout(400)
    # the dial and the sentence under it are separate elements; the shot needs both
    seg = page.locator(".seg").bounding_box()
    head = page.locator("h2", has_text="How hard she chairs").bounding_box()
    hint = page.locator(".seg ~ p.hint").first.bounding_box()
    top, bottom = head["y"] - PAD, hint["y"] + hint["height"] + PAD
    page.screenshot(path=str(OUT / "focus-gauge.png"), clip={
        "x": max(seg["x"] - PAD, 0), "y": max(top, 0),
        "width": seg["width"] + PAD * 2, "height": bottom - top})
    print("shot focus-gauge (dial + the sentence under it)")
    b.close()
