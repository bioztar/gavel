"""Sign the bot's Google account into MEET_PROFILE_DIR — once, by hand, on a machine with a
screen. This is how the preferred authentication path gets its profile.

    MEET_PROFILE_DIR=~/gavel-meet-profile uv run python scripts/login.py

Opens a visible Chromium on that profile at the Google sign-in page. Sign in as the bot
account (complete any 2-step prompt), then press Enter here. The script confirms the
account is signed in by loading meet.google.com and checking for the account menu, and
closes the browser. Copy the directory to the machine that runs ears-meet (or mount it
into the container at /profile).

Nothing about the account is read or printed; the profile directory is the credential —
keep it out of git (it is .gitignored here) and out of any image.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

from ears_meet import selectors as sel
from ears_meet.settings import MissingSetting, get_settings


def profile_dir() -> Path:
    settings = get_settings()
    if not settings.has_profile:
        raise MissingSetting("MEET_PROFILE_DIR is not set; it names the directory to sign in to")
    profile = Path(settings.meet_profile_dir).expanduser()
    profile.mkdir(parents=True, exist_ok=True)
    return profile


async def main(profile: Path) -> int:
    settings = get_settings()
    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            str(profile),
            headless=False,
            executable_path=settings.meet_chromium_path or None,
            args=["--disable-blink-features=AutomationControlled", "--no-first-run"],
            ignore_default_args=["--enable-automation"],
            viewport={"width": settings.window_width, "height": settings.window_height},
            locale="en-US",
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(
            "https://accounts.google.com/ServiceLogin?continue=https://meet.google.com/"
        )
        print(f"Chromium is open on profile {profile}.")
        print("Sign in as the bot account in that window, then press Enter here.")
        await asyncio.get_running_loop().run_in_executor(None, sys.stdin.readline)

        await page.goto("https://meet.google.com/", wait_until="domcontentloaded")
        signed_in = False
        for candidate in sel.ACCOUNT_MENU.candidates:
            if await page.locator(candidate).first.is_visible():
                signed_in = True
                break
        await context.close()

    if signed_in:
        print("Signed in. The profile is ready: set MEET_PROFILE_DIR to it where ears-meet runs.")
        return 0
    print("Could not confirm a signed-in session on meet.google.com — try again.")
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main(profile_dir())))
    except MissingSetting as exc:
        print(str(exc))
        raise SystemExit(2) from None
