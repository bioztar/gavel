"""The browser participant: Xvfb, a headful Chromium, and the Meet page, via Playwright.

Everything Playwright- and Meet-page-specific lives here (as py-cord lives in
ears-discord's voice.py). app.py sees a handful of methods and one stream of raw
observer events; nothing else in the package imports playwright.

Why headful on Xvfb and not `--headless`: WebRTC media capture and `getDisplayMedia`
(the stage share) are unreliable or plain unavailable in headless Chromium, and Meet
treats a headless UA as a bot. A real window on a virtual display behaves like a laptop.

Authentication — what is implemented: **a persisted, pre-authenticated Chromium profile**
(`MEET_PROFILE_DIR`). Sign in once by hand, hand the directory to the container, and the
bot is a signed-in account from the first page load — no login form is scripted against
in the normal path. The scripted `MEET_BOT_EMAIL` / `MEET_BOT_PASSWORD` sign-in exists as
a best-effort fallback when Meet bounces to accounts.google.com; Google routinely blocks
it with a challenge, so treat it as "may work once to seed the profile". Neither value is
ever logged; errors name the SETTING.

Audio devices: none are chosen here. Chromium follows PulseAudio's defaults, which
pulse.py has set to `gavel_out` (speaker) and `gavel_in.monitor` (microphone) before
launch. `--use-fake-ui-for-media-stream` only auto-accepts the permission prompt; the
devices are real (to Chromium) PulseAudio ones.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from playwright.async_api import (
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)
from playwright.async_api import Error as PlaywrightError

from . import selectors as sel
from .logging import get_logger
from .settings import MissingSetting, Settings

logger = get_logger("ears_meet.browser")

OBSERVER_JS = (Path(__file__).parent / "observer.js").read_text(encoding="utf-8")
ObserverSink = Callable[[dict[str, Any]], None]


class JoinError(RuntimeError):
    pass


class Xvfb:
    def __init__(self, display: str, size: str, manage: bool) -> None:
        self.display, self.size, self.manage = display, size, manage
        self._proc: asyncio.subprocess.Process | None = None

    async def start(self) -> None:
        os.environ["DISPLAY"] = self.display
        if not self.manage:
            return
        if shutil.which("Xvfb") is None:
            raise JoinError("Xvfb is not installed (apt install xvfb), or set XVFB_MANAGE=false")
        if self._socket_exists():
            logger.info("xvfb.reusing", display=self.display)
            return
        self._proc = await asyncio.create_subprocess_exec(
            "Xvfb",
            self.display,
            "-screen",
            "0",
            self.size,
            "-nolisten",
            "tcp",
            "-ac",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        for _ in range(40):
            if self._socket_exists():
                logger.info("xvfb.started", display=self.display, size=self.size)
                return
            await asyncio.sleep(0.1)
        raise JoinError(f"Xvfb did not come up on {self.display}")

    def _socket_exists(self) -> bool:
        num = self.display.lstrip(":").split(".")[0]
        return Path(f"/tmp/.X11-unix/X{num}").exists()

    async def stop(self) -> None:
        if self._proc is not None and self._proc.returncode is None:
            self._proc.terminate()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._proc.wait(), 3)


class Browser:
    def __init__(self, settings: Settings, on_event: ObserverSink) -> None:
        self.settings = settings
        self.on_event = on_event
        self._pw: Playwright | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.stage_page: Page | None = None
        self.presenting = False
        self.joined_at: float | None = None

    # --- lifecycle ---------------------------------------------------------------------

    def _profile_dir(self) -> Path:
        s = self.settings
        # No profile: a throwaway one under the working directory (.gitignored).
        profile = (
            Path(s.meet_profile_dir).expanduser()
            if s.has_profile
            else Path(".chromium-profile").resolve()
        )
        profile.mkdir(parents=True, exist_ok=True)
        return profile

    async def launch(self) -> None:
        s = self.settings
        profile = self._profile_dir()
        self._pw = await async_playwright().start()
        args = [
            f"--window-size={s.window_width},{s.window_height}",
            "--window-position=0,0",
            "--use-fake-ui-for-media-stream",  # auto-accept the mic/camera prompt
            "--autoplay-policy=no-user-gesture-required",
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-infobars",
            "--disable-session-crashed-bubble",
            "--hide-crash-restore-bubble",
            "--lang=en-US",
            # The stage share: pick the TAB by title, no picker dialog. Tab capture is the
            # only share that starts on a virtual display — measured 2026-09 under Xvfb:
            # getDisplayMedia({video:{displaySurface:'browser'}}) with this flag gives a
            # web-contents track of the gavel-stage tab; entire-screen capture
            # (--auto-select-desktop-capture-source) fails with NotReadableError every
            # time, so that flag is deliberately absent — it is not a fallback here.
            f"--auto-select-tab-capture-source-by-title={s.stage_tab_title}",
        ]
        self.context = await self._pw.chromium.launch_persistent_context(
            str(profile),
            headless=False,
            executable_path=s.meet_chromium_path or None,
            args=args,
            ignore_default_args=["--enable-automation", "--mute-audio"],
            viewport={"width": s.window_width, "height": s.window_height},
            locale="en-US",
            permissions=["microphone", "camera"],
            no_viewport=False,
        )
        await self.context.grant_permissions(
            ["microphone", "camera"], origin="https://meet.google.com"
        )
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        await self.page.expose_binding("__gavelPost", self._on_post)
        self.page.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        logger.info(
            "browser.launched",
            profile=str(profile),
            chromium=s.meet_chromium_path or "playwright",
            display=os.environ.get("DISPLAY"),
        )

    async def close(self) -> None:
        with contextlib.suppress(PlaywrightError):
            if self.context is not None:
                await self.context.close()
        if self._pw is not None:
            await self._pw.stop()
        self.context = self.page = self.stage_page = None

    async def _on_post(self, _source: Any, event: dict[str, Any]) -> None:
        self.on_event(event)

    # --- joining -----------------------------------------------------------------------

    async def join(self) -> None:
        """Open MEET_URL, get through the lobby, wait to be admitted."""
        page = self._page()
        s = self.settings
        await page.goto(s.meet_url, wait_until="domcontentloaded")
        await self._maybe_sign_in()
        await self._lobby()
        await self._wait_admitted()
        self.joined_at = time.time()
        logger.info("meet.joined")
        await self.install_observer()

    async def _maybe_sign_in(self) -> None:
        page = self._page()
        await asyncio.sleep(1.0)
        if "accounts.google.com" not in page.url:
            return
        s = self.settings
        if not s.has_password_login:
            raise MissingSetting(
                "Meet asked for a Google sign-in: the profile in MEET_PROFILE_DIR is not signed "
                "in, and MEET_BOT_EMAIL / MEET_BOT_PASSWORD are not set"
            )
        logger.warning("meet.signing_in", how="password (fallback)")
        email = await self._first(sel.SIGNIN_EMAIL, wait_ms=10_000)
        if email is None:
            raise JoinError("sign-in page without an email box — check selectors.SIGNIN_EMAIL")
        await email.fill(s.meet_bot_email.get_secret_value())
        await self._click(sel.SIGNIN_NEXT)
        password = await self._first(sel.SIGNIN_PASSWORD, wait_ms=15_000)
        if password is None:
            raise JoinError(
                "sign-in stopped before the password step (challenge or captcha?) — sign in by "
                "hand once and point MEET_PROFILE_DIR at that profile"
            )
        await password.fill(s.meet_bot_password.get_secret_value())
        await self._click(sel.SIGNIN_NEXT)
        with contextlib.suppress(PlaywrightError):
            await page.wait_for_url("**meet.google.com/**", timeout=30_000)
        if "accounts.google.com" in page.url:
            raise JoinError(
                "Google did not accept the scripted sign-in (challenge shown). Sign in by hand "
                "once and point MEET_PROFILE_DIR at that profile"
            )

    async def _lobby(self) -> None:
        page = self._page()
        s = self.settings
        join = await self._first(sel.LOBBY_JOIN_BUTTON, wait_ms=30_000)
        if join is None:
            raise JoinError(
                f"no join button on the lobby page — selector {sel.LOBBY_JOIN_BUTTON.name} "
                f"(url: {page.url.split('?')[0]})"
            )
        name_box = await self._first(sel.LOBBY_NAME_INPUT, wait_ms=500)
        if name_box is not None:
            await name_box.fill(s.meet_bot_name)
        # Camera off (no face), microphone ON — the chair has to be heard.
        await self._set_toggle(sel.CAMERA_TOGGLE, muted=True)
        await self._set_toggle(sel.MIC_TOGGLE, muted=False)
        await join.click()
        logger.info("meet.join_clicked")

    async def _wait_admitted(self) -> None:
        page = self._page()
        deadline = time.time() + self.settings.meet_admit_timeout_s
        waiting_logged = False
        while time.time() < deadline:
            if await self._visible(sel.LEAVE_BUTTON):
                return
            if await self._visible(sel.LOBBY_DENIED_TEXT):
                raise JoinError("Meet refused the join (denied, or nobody admitted the bot)")
            if not waiting_logged and await self._visible(sel.LOBBY_WAITING_TEXT):
                waiting_logged = True
                logger.info("meet.waiting_for_host")
            await page.wait_for_timeout(1000)
        raise JoinError(
            f"not admitted within MEET_ADMIT_TIMEOUT_S={self.settings.meet_admit_timeout_s:g}s"
        )

    async def ensure_unmuted(self) -> bool:
        """The chair must be audible. Returns whether the mic reads unmuted afterwards."""
        return await self._set_toggle(sel.MIC_TOGGLE, muted=False)

    async def _set_toggle(self, which: sel.Selector, *, muted: bool) -> bool:
        el = await self._first(which, wait_ms=3000)
        if el is None:
            return False
        for _ in range(3):
            state = await el.get_attribute("data-is-muted")
            if state is None:
                return False  # fallback candidate without state: cannot know
            if (state == "true") == muted:
                return True
            await el.click()
            await self._page().wait_for_timeout(300)
        return False

    async def is_in_call(self) -> bool:
        if self.page is None or self.page.is_closed():
            return False
        if await self._visible(sel.CALL_ENDED_TEXT):
            return False
        return await self._visible(sel.LEAVE_BUTTON)

    async def leave(self) -> None:
        with contextlib.suppress(PlaywrightError, JoinError):
            if self.presenting:
                await self._click(sel.STOP_PRESENTING_BUTTON)
            await self._click(sel.LEAVE_BUTTON)
        logger.info("meet.left")

    # --- the observer -------------------------------------------------------------------

    async def install_observer(self) -> None:
        page = self._page()
        await page.evaluate(OBSERVER_JS, sel.observer_config())
        logger.info("observer.installed")

    async def observer_alive(self) -> bool:
        page = self._page()
        try:
            return bool(await page.evaluate("() => !!window.__gavelObserver"))
        except PlaywrightError:
            return False

    async def snapshot(self) -> dict[str, Any]:
        page = self._page()
        try:
            out = await page.evaluate(
                "() => window.__gavelObserver && window.__gavelObserver.snapshot()"
            )
        except PlaywrightError:
            return {}
        return out or {}

    async def self_check(self) -> sel.SelfCheckResult:
        """Are the selectors the package relies on present in this call? Names what is not."""
        result = sel.SelfCheckResult()
        for selector in sel.ALL:
            if selector.where == "lobby" or selector is sel.PRESENT_TAB_MENU_ITEM:
                continue
            hit = await self._match(selector)
            if hit is not None:
                result.matched[selector.name] = hit
            elif selector in sel.IN_CALL_REQUIRED:
                result.missing_required.append(selector.name)
            else:
                result.missing_optional.append(selector.name)
        # The indicator is per tile; the observer knows whether it found one on any tile.
        snap = await self.snapshot()
        if snap.get("indicatorFound"):
            result.matched.setdefault(sel.SPEAKING_INDICATOR.name, "observer")
            if sel.SPEAKING_INDICATOR.name in result.missing_required:
                result.missing_required.remove(sel.SPEAKING_INDICATOR.name)
        if self.settings.stage_url:
            await self._check_present_menu(result)
        return result

    async def _check_present_menu(self, result: sel.SelfCheckResult) -> None:
        """The "A tab" item exists only while the Present menu is open, so the check opens
        the menu, looks, and closes it again. With a stage configured it is required: the
        item is what makes Meet ask Chromium for a tab, and a tab is the only capture that
        starts on a virtual display (see `launch`)."""
        page = self._page()
        name = sel.PRESENT_TAB_MENU_ITEM.name
        if sel.PRESENT_BUTTON.name not in result.matched:
            result.missing_required.append(name)
            return
        if not await self._click(sel.PRESENT_BUTTON, wait_ms=3000):
            result.missing_required.append(name)
            return
        hit = await self._first_candidate(sel.PRESENT_TAB_MENU_ITEM, wait_ms=3000)
        await page.keyboard.press("Escape")
        if hit is None:
            result.missing_required.append(name)
        else:
            result.matched[name] = hit

    async def _match(self, selector: sel.Selector) -> str | None:
        page = self._page()
        for candidate in selector.candidates:
            try:
                if await page.locator(candidate).count() > 0:
                    return candidate
            except PlaywrightError:
                continue
        return None

    # --- captions ------------------------------------------------------------------------

    async def enable_captions(self) -> bool:
        button = await self._first(sel.CAPTIONS_BUTTON, wait_ms=3000)
        if button is None:
            logger.warning("captions.no_button", selector=sel.CAPTIONS_BUTTON.name)
            return False
        label = (await button.get_attribute("aria-label")) or ""
        if "off" in label.lower():
            return True  # already on: the button offers to turn them off
        await button.click()
        await self._page().wait_for_timeout(1000)
        on = await self._visible(sel.CAPTIONS_REGION)
        logger.info("captions.enabled" if on else "captions.region_not_found")
        return on

    # --- the stage share -----------------------------------------------------------------

    async def present_stage(self) -> bool:
        """Open STAGE_URL in a second tab and present it. False, never an exception, when
        the stage is unreachable or Meet's present menu is not where we expect it."""
        s = self.settings
        if not s.stage_url or self.context is None:
            return False
        page = self._page()
        try:
            stage = await self.context.new_page()
            await stage.goto(
                s.stage_url, wait_until="domcontentloaded", timeout=int(s.stage_timeout_s * 1000)
            )
            try:
                await stage.wait_for_function(
                    "title => document.title === title",
                    arg=s.stage_tab_title,
                    timeout=int(s.stage_timeout_s * 1000),
                )
            except PlaywrightError:
                logger.warning(
                    "stage.title_mismatch", expected=s.stage_tab_title, got=await stage.title()
                )
                await stage.close()
                return False
            self.stage_page = stage
            await page.bring_to_front()
            if not await self._click(sel.PRESENT_BUTTON, wait_ms=5000):
                logger.warning("stage.no_present_button", selector=sel.PRESENT_BUTTON.name)
                return False
            if not await self._click(sel.PRESENT_TAB_MENU_ITEM, wait_ms=5000):
                logger.error(
                    "stage.no_tab_item",
                    selector=sel.PRESENT_TAB_MENU_ITEM.name,
                    hint=sel.TAB_CAPTURE_ONLY,
                )
                await page.keyboard.press("Escape")
                return False
            # Chromium auto-selects the tab by title (launch flag); Meet then shows Stop.
            stop = await self._first(sel.STOP_PRESENTING_BUTTON, wait_ms=10_000)
            self.presenting = stop is not None
            await page.bring_to_front()
            logger.info("stage.presenting" if self.presenting else "stage.present_unconfirmed")
            return self.presenting
        except PlaywrightError as exc:
            logger.warning("stage.unreachable", error=str(exc).splitlines()[0][:200])
            if self.stage_page is not None and not self.stage_page.is_closed():
                await self.stage_page.close()
            self.stage_page = None
            return False

    # --- helpers -------------------------------------------------------------------------

    def _page(self) -> Page:
        if self.page is None:
            raise JoinError("browser not launched")
        return self.page

    async def _first(self, selector: sel.Selector, *, wait_ms: int) -> Any | None:
        """The first visible element for `selector`, trying each candidate for `wait_ms`
        in total (each candidate gets a share)."""
        found = await self._first_with_candidate(selector, wait_ms=wait_ms)
        return None if found is None else found[1]

    async def _first_candidate(self, selector: sel.Selector, *, wait_ms: int) -> str | None:
        """Which candidate of `selector` is visible, or None."""
        found = await self._first_with_candidate(selector, wait_ms=wait_ms)
        return None if found is None else found[0]

    async def _first_with_candidate(
        self, selector: sel.Selector, *, wait_ms: int
    ) -> tuple[str, Any] | None:
        page = self._page()
        per = max(100, wait_ms // max(1, len(selector.candidates)))
        for candidate in selector.candidates:
            try:
                loc = page.locator(candidate).first
                await loc.wait_for(state="visible", timeout=per)
                return candidate, loc
            except PlaywrightError:
                continue
        return None

    async def _visible(self, selector: sel.Selector) -> bool:
        page = self._page()
        for candidate in selector.candidates:
            try:
                if await page.locator(candidate).first.is_visible():
                    return True
            except PlaywrightError:
                continue
        return False

    async def _click(self, selector: sel.Selector, *, wait_ms: int = 3000) -> bool:
        el = await self._first(selector, wait_ms=wait_ms)
        if el is None:
            return False
        await el.click()
        return True
