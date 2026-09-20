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
REAL = ('Karen, set up a meeting with Artem in fifteen minutes, fifteen minutes long, called gavel live demo. Two topics. One: solution and architecture, six minutes, I present it. Two: roadmap, eight minutes, open discussion - I want both Artem and me heard on it.')
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
    # the form always keeps one blank row for adding a topic; it is noise in a still
    tbl = page.locator("table").bounding_box()
    blank = page.locator("tbody tr").last.bounding_box()
    page.screenshot(path=str(OUT / "focus-agenda.png"), clip={
        "x": max(tbl["x"] - PAD, 0), "y": max(tbl["y"] - PAD, 0),
        "width": tbl["width"] + PAD * 2, "height": blank["y"] - tbl["y"] + PAD})
    print("shot focus-agenda (blank row trimmed)")
    page.locator("label[for=enf_high]").click(); page.wait_for_timeout(400)
    shoot(page, ".seg", "focus-gauge")
    b.close()

# The gauge shot needs High selected and the sentence under it, which is a separate element.
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE)
    page = b.new_page(viewport={"width": 1600, "height": 1200}, device_scale_factor=2)
    page.goto(f"{BASE}/compose", wait_until="networkidle")
    page.fill("#brief", REAL); page.click("button[type=submit]")
    page.wait_for_load_state("networkidle"); page.wait_for_timeout(4000)
    page.locator("label[for=enf_high]").click(); page.wait_for_timeout(400)
    seg = page.locator(".seg").bounding_box()
    head = page.locator("h2", has_text="How hard she chairs").bounding_box()
    hint = page.locator(".seg ~ p.hint").first.bounding_box()
    top, bottom = head["y"] - PAD, hint["y"] + hint["height"] + PAD
    page.screenshot(path=str(OUT / "focus-gauge.png"), clip={
        "x": max(seg["x"] - PAD, 0), "y": max(top, 0),
        "width": seg["width"] + PAD * 2, "height": bottom - top})
    print("shot focus-gauge (dial + the sentence under it)")
    b.close()
