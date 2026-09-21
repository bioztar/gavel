"""`python -m ears_meet` — the wire, the clock, PulseAudio, Xvfb and the browser on one loop.

Startup order matters: the sinks and their defaults exist before Chromium launches (it
reads PulseAudio's defaults once), the wire is up before the join (a brain may connect
while the bot waits in the lobby), and the self-check runs the moment we are in the call
— failing loudly, by selector name, if Meet's DOM has moved from under us.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
import signal
from collections.abc import Callable, Iterator

import httpx
import uvicorn

from .agenda import load_agenda
from .app import Ears
from .browser import Browser, JoinError, Xvfb
from .logging import get_logger, setup_logging
from .pulse import Pulse, PulseError, Recorder
from .settings import MissingSetting, Settings, get_settings
from .store import FrameLog
from .wire import create_api

logger = get_logger("ears_meet")

MEET_CODE = re.compile(r"meet\.google\.com/([a-z]{3}-[a-z]{4}-[a-z]{3})")


def meet_code(url: str) -> str:
    m = MEET_CODE.search(url)
    return m.group(1) if m else url.rstrip("/").rsplit("/", 1)[-1] or url


class _Server(uvicorn.Server):
    """uvicorn without its signal handling — main() owns Ctrl-C and shuts down in order."""

    @contextlib.contextmanager
    def capture_signals(self) -> Iterator[None]:
        yield


async def run(settings: Settings) -> None:
    settings.require_auth()  # names the missing setting; never a value
    saved_agenda = load_agenda(settings.agenda_file)

    pulse = Pulse(settings.pulse_sink_out, settings.pulse_sink_in, manage=settings.pulse_manage)
    await pulse.setup()
    xvfb = Xvfb(settings.display, settings.xvfb_size, settings.xvfb_manage)
    await xvfb.start()

    async with httpx.AsyncClient() as http:
        ears = Ears(
            settings,
            player=pulse.player(),
            verify_egress=True,
            http=http,
            frame_log=FrameLog(settings.frames_file),
        )
        ears.saved_agenda = saved_agenda
        browser = Browser(settings, ears.on_observer_event)
        ears.surface = browser
        if ears.stream is None:
            logger.warning(
                "stt.disabled",
                reason="SLNG_API_KEY unset"
                if not settings.stt_enabled
                else settings.transcript_source,
            )

        server = _Server(
            uvicorn.Config(
                create_api(ears),
                host=settings.wire_host,
                port=settings.wire_port,
                log_level="warning",
                lifespan="off",
            )
        )
        loop = asyncio.get_running_loop()

        def stop() -> None:
            server.should_exit = True

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop)

        async def leave_and_stop() -> None:
            stop()

        ears.on_leave = leave_and_stop
        background = [loop.create_task(ears.run_clock())]
        recorder = pulse.record(ears.on_pcm, settings.pulse_frame_ms)
        logger.info(
            "ears.started",
            wire=f"ws://{settings.wire_host}:{settings.wire_port}",
            meet=meet_code(settings.meet_url),
        )
        background.append(loop.create_task(_join(ears, browser, pulse, recorder, stop)))
        try:
            await server.serve()
        finally:
            logger.info("ears.stopping")
            for task in background:
                task.cancel()
            with contextlib.suppress(Exception):
                await browser.leave()
            await ears.shutdown()
            await recorder.stop()
            await browser.close()
            await xvfb.stop()
            await pulse.teardown()


async def _join(
    ears: Ears, browser: Browser, pulse: Pulse, recorder: Recorder, stop: Callable[[], None]
) -> None:
    """Launch, join, verify — then hand the call to the clock. Any failure stops the process
    with one clear log line: a bot that is not in the call has no reason to keep running."""
    settings = ears.settings
    try:
        await browser.launch()
        await browser.join()
        ears.on_joined(meet_code(settings.meet_url))
        await recorder.start()

        check = await browser.self_check()
        ears.self_check_result = check
        if not check.ok:
            # Loud, named, fatal: the floor policy is blind without these selectors.
            logger.error(
                "selfcheck.failed", missing=check.missing_required, message=check.message()
            )
            ears.debug("selfcheck.failed", missing=check.missing_required)
            raise JoinError(check.message())
        logger.info(
            "selfcheck.ok", matched=len(check.matched), optional_missing=check.missing_optional
        )

        unmuted = await browser.ensure_unmuted()
        egress = await pulse.egress_attached()
        logger.info("egress.check", unmuted=unmuted, mic_on_gavel_in=egress)
        if not egress:
            logger.error(
                "egress.not_attached",
                hint="Chromium is not recording from the gavel_in monitor: the chair will be "
                "silent. Check PulseAudio defaults were set before launch (PULSE_MANAGE).",
            )
            ears.debug("egress.not_attached")

        if settings.meet_captions and settings.transcript_source in ("auto", "captions"):
            await browser.enable_captions()
        if settings.stage_url:
            await ears.present_stage()
    except (JoinError, MissingSetting, PulseError) as exc:
        logger.error("join.failed", error=str(exc))
        stop()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("join.crashed")
        stop()


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_json)
    try:
        asyncio.run(run(settings))
    except MissingSetting as exc:
        logger.error("settings.missing", error=str(exc))
        raise SystemExit(2) from None
    except PulseError as exc:
        logger.error("pulse.failed", error=str(exc))
        raise SystemExit(3) from None


if __name__ == "__main__":
    main()
