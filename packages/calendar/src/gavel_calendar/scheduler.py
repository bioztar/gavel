"""One asyncio task that wakes at the next event's start time and starts it.

Clicking Join calls `service.start` directly, early. This task calls the
same function when nobody clicked it — both paths end in the same call
(`service.start`), so there is exactly one way a session actually starts.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from . import service
from .ears_client import EarsClient
from .store import InviteStore

logger = logging.getLogger(__name__)


async def run(store: InviteStore, ears: EarsClient, poll_seconds: float) -> None:
    while True:
        now = datetime.now(UTC)
        due = [r for r in store.pending() if r.start <= now]
        for record in due:
            try:
                await service.start(store, ears, record.session_id)
                logger.info("scheduler.started session_id=%s", record.session_id)
            except Exception:
                logger.exception("scheduler.start_failed session_id=%s", record.session_id)

        upcoming = [r.start for r in store.pending()]
        sleep_for = poll_seconds
        if upcoming:
            delta = (min(upcoming) - datetime.now(UTC)).total_seconds()
            sleep_for = 0.1 if delta <= 0 else min(delta, poll_seconds)
        await asyncio.sleep(sleep_for)
