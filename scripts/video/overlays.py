"""Render one transparent 1920x1080 label overlay per segment (this ffmpeg has no drawtext)."""
from __future__ import annotations
import json, pathlib
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path("/Users/alex/DEV/_assets/gavel-video")
OUT = ROOT / "overlays"; OUT.mkdir(parents=True, exist_ok=True)
SCRIPT = json.loads(pathlib.Path(__file__).with_name("script.json").read_text())
import importlib.util as _il
_spec = _il.spec_from_file_location("asm", pathlib.Path(__file__).with_name("assemble.py"))
_asm = _il.module_from_spec(_spec); _spec.loader.exec_module(_asm)
EXE = ("/Users/alex/Library/Caches/ms-playwright/chromium-1217/chrome-mac-arm64/"
       "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing")
LABEL = {"vitaly": "VITALY", "artem": "ARTEM", "karen": "KAREN &nbsp;·&nbsp; the chair"}

TPL = """<div style="width:1920px;height:1080px;position:relative;font-family:-apple-system,system-ui,sans-serif">
{badge}
<div style="position:absolute;left:0;right:0;{edge}:0;height:104px;background:linear-gradient({a},rgba(8,9,12,.82) {stop})"></div>
<div style="position:absolute;left:72px;{edge}:30px;color:#fff;font-size:30px;font-weight:700;letter-spacing:.09em">{label}</div>
<div style="position:absolute;right:72px;{edge}:34px;color:rgba(255,255,255,.58);font-size:22px">synthetic voice — first pass</div>
</div>"""
ROOM_TPL = """<div style="width:1920px;height:1080px;position:relative;font-family:-apple-system,system-ui,sans-serif">
<div style="position:absolute;left:46px;top:712px;display:inline-flex;align-items:center;gap:14px;
 background:rgba(8,9,12,.88);color:#fff;padding:12px 22px;border-radius:999px;font-size:26px;
 font-weight:700;letter-spacing:.08em">{label}
 <span style="font-weight:400;letter-spacing:0;font-size:20px;color:rgba(255,255,255,.55)">synthetic voice</span>
</div></div>"""

BADGE = ("""<div style="position:absolute;right:72px;top:56px;background:#c4531b;color:#fff;"""
         """padding:11px 20px;border-radius:7px;font-size:23px;font-weight:700;letter-spacing:.05em">"""
         """PLACEHOLDER SHOT — {what}</div>""")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE)
    page = b.new_page(viewport={"width": 1920, "height": 1080})
    for seg in SCRIPT["segments"]:
        shot_file, _, placeholder = _asm.SHOTS_BY_NAME[seg["shot"]]
        badge = BADGE.format(what=placeholder.upper()) if placeholder else ""
        # the meeting room fills its own bottom edge, so its label goes to the top
        top = shot_file == "room-live"
        if top:
            # the room uses all four edges; the label goes in the empty column under the agenda
            page.set_content(ROOM_TPL.format(label=LABEL[seg["speaker"]]))
        else:
            page.set_content(TPL.format(
                label=LABEL[seg["speaker"]], badge=badge,
                edge="bottom", a="transparent", stop="38%"))
        page.wait_for_timeout(120)
        page.screenshot(path=str(OUT / f"{seg['id']}.png"), omit_background=True)
    print("overlays", len(SCRIPT["segments"]))
    b.close()
