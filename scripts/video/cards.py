"""The opening and closing cards. The opening one leaves a right-hand column empty so
Karen's portrait can sit in it while she speaks the first line."""
from __future__ import annotations
import pathlib
from playwright.sync_api import sync_playwright

OUT = pathlib.Path("/Users/alex/DEV/_assets/gavel-video/shots")
EXE = ("/Users/alex/Library/Caches/ms-playwright/chromium-1217/chrome-mac-arm64/"
       "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing")
HTML = """<div style="width:1920px;height:1080px;background:#fafafb;display:flex;
 flex-direction:column;justify-content:center;padding:0 880px 0 150px;box-sizing:border-box;
 font-family:-apple-system,system-ui,sans-serif">
<div style="font-size:15px;letter-spacing:.14em;text-transform:uppercase;color:#8a8f98;
 margin-bottom:26px" id="kicker">HackBarna AI Summit 26 · Norrsken House Barcelona</div>
<div style="font-size:88px;font-weight:700;letter-spacing:-.03em;color:#0b0c0e;line-height:1.02"
 id="title">gavel</div>
<div style="font-size:34px;color:#3d434d;margin-top:20px;line-height:1.3" id="sub">An AI chair
 for meetings.</div>
<div style="margin-top:40px;border-left:3px solid #0b62f5;padding-left:20px;font-size:25px;
 color:#3d434d" id="quote">She never writes your agenda. She refuses to work without one —
 and then she holds you to it.</div></div>"""

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE)
    pg = b.new_page(viewport={"width": 1920, "height": 1080})
    pg.set_content(HTML); pg.wait_for_timeout(350)
    pg.screenshot(path=str(OUT / "card-title.png")); print("card-title")
    pg.evaluate("""() => {
      document.getElementById('kicker').textContent = 'gavel · bioztar/gavel · gavel.pro7ocol.com';
      document.getElementById('title').textContent = 'It held me to it.';
      document.getElementById('sub').textContent =
        'Agenda gate · structured invite · drift catch · floor handover';
      document.getElementById('quote').textContent = 'Time governance for meetings.';
      document.querySelector('div').style.padding = '0 200px';
    }"""); pg.wait_for_timeout(300)
    pg.screenshot(path=str(OUT / "card-end.png")); print("card-end")
    b.close()
