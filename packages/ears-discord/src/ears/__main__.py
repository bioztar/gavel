"""`python -m ears` — the wire, the clock and the Discord bot on one event loop."""

from __future__ import annotations

import asyncio
import contextlib
import signal
from collections.abc import Iterator

import httpx
import uvicorn

from .app import Ears
from .bus import Bus
from .db.store import Store
from .logging import get_logger, setup_logging
from .settings import get_settings
from .status_board import StatusBoard
from .stt import SlngStt
from .tts import SlngTts
from .wire import create_api

logger = get_logger("ears")


class _Server(uvicorn.Server):
    """uvicorn without its signal handling — main() owns Ctrl-C and shuts down in order."""

    @contextlib.contextmanager
    def capture_signals(self) -> Iterator[None]:
        yield


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_json)

    store = await Store.connect(settings.postgres_dsn)
    bus = await Bus.connect(settings.redis_dsn, settings.redis_prefix, settings.redis_stream_maxlen)

    async with httpx.AsyncClient() as http:
        stt = SlngStt(settings, http) if settings.stt_enabled else None
        if stt is None:
            logger.warning("stt.disabled", reason="SLNG_API_KEY unset")
        # `ears` owns the selected voice; the say-box reads it per line through
        # this getter, so a console change reaches the next line, not the next
        # restart. The cycle is deliberate: `ears` is built with the TTS, and
        # the TTS asks `ears` for the voice when it needs it.
        ears_ref: list[Ears] = []
        tts = (
            SlngTts(settings, http, voice=lambda: ears_ref[0].tts_voice)
            if settings.stt_enabled
            else None
        )
        ears = Ears(settings, store, bus, stt, tts)
        ears_ref.append(ears)
        ears.status_configs = await store.discord_status()
        # A voice picked in the console before the last restart is still the
        # voice; the environment's is only the fallback.
        stored_voice = await store.get_setting("tts_voice")
        if stored_voice:
            ears.tts_voice = stored_voice
            logger.info("tts.voice_restored", voice=stored_voice)
        bus.start(ears.command)

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
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: setattr(server, "should_exit", True))

        background = [loop.create_task(ears.run_clock())]
        voice = None
        if settings.discord_ears_token:
            from .voice import Voice  # the only discord import in the process

            voice = Voice(settings, ears, await store.discord_channels())
            ears.voice = voice
            background.append(loop.create_task(_supervise("voice", voice.run())))
            if settings.discord_status_enabled:
                board = StatusBoard(settings, http, voice, ears.status_config, ears.debug)
                background.append(loop.create_task(_supervise("status", board.run())))
        else:
            logger.warning("voice.disabled", reason="DISCORD_EARS_TOKEN unset — wire only")

        logger.info(
            "ears.started",
            wire=f"ws://{settings.wire_host}:{settings.wire_port}",
            console=f"http://{settings.wire_host}:{settings.wire_port}/console",
        )
        try:
            await server.serve()
        finally:
            logger.info("ears.stopping")
            await ears.shutdown()
            if voice is not None:
                with contextlib.suppress(Exception):
                    await voice.close()
            for task in background:
                task.cancel()
            await bus.close()
            await store.close()


async def _supervise(name: str, coro: object) -> None:
    try:
        await coro  # type: ignore[misc]
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception(f"{name}.crashed")


if __name__ == "__main__":
    asyncio.run(main())
