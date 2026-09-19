"""Redis: every frame out, `speak`/`stop` in.

Out, per frame:
  XADD    {prefix}:events  MAXLEN ~N  type <type> frame <json>   durable, replayable (XREAD / XRANGE)
  PUBLISH {prefix}:events  <json>                                 live fan-out

In:
  SUBSCRIBE {prefix}:commands   — the same `speak` / `stop` JSON the WebSocket accepts.

Redis is a second door, not a dependency: the WebSocket wire works without it, and
a Redis outage costs frames on Redis only.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Callable
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from .logging import get_logger

logger = get_logger(__name__)

QUEUE_LIMIT = 10_000


class Bus:
    def __init__(self, redis: Redis | None, prefix: str, maxlen: int) -> None:
        self._redis = redis
        self.events_key = f"{prefix}:events"
        self.commands_key = f"{prefix}:commands"
        self._maxlen = maxlen
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(QUEUE_LIMIT)
        self._tasks: list[asyncio.Task[None]] = []
        self._healthy = True

    @classmethod
    async def connect(cls, dsn: str, prefix: str, maxlen: int) -> Bus:
        redis = Redis.from_url(dsn, decode_responses=True, socket_connect_timeout=2)
        try:
            await redis.ping()
        except (RedisError, OSError) as exc:
            logger.warning("bus.disabled", reason=str(exc)[:200])
            await redis.aclose()
            return cls(None, prefix, maxlen)
        logger.info("bus.connected", events=f"{prefix}:events", commands=f"{prefix}:commands")
        return cls(redis, prefix, maxlen)

    @property
    def enabled(self) -> bool:
        return self._redis is not None

    def start(self, on_command: Callable[[str], None]) -> None:
        if self._redis is None:
            return
        loop = asyncio.get_running_loop()
        self._tasks = [
            loop.create_task(self._publish_loop()),
            loop.create_task(self._command_loop(on_command)),
        ]

    def publish(self, frame: dict[str, Any]) -> None:
        if self._redis is None:
            return
        with contextlib.suppress(asyncio.QueueFull):
            self._queue.put_nowait(frame)

    async def _publish_loop(self) -> None:
        assert self._redis is not None
        while True:
            frame = await self._queue.get()
            body = json.dumps(frame, separators=(",", ":"))
            try:
                async with self._redis.pipeline(transaction=False) as pipe:
                    pipe.xadd(
                        self.events_key,
                        {"type": frame["type"], "frame": body},
                        maxlen=self._maxlen,
                        approximate=True,
                    )
                    pipe.publish(self.events_key, body)
                    await pipe.execute()
                self._set_healthy(True)
            except (RedisError, OSError) as exc:
                self._set_healthy(False, str(exc))

    async def _command_loop(self, on_command: Callable[[str], None]) -> None:
        assert self._redis is not None
        while True:
            try:
                async with self._redis.pubsub() as pubsub:
                    await pubsub.subscribe(self.commands_key)
                    async for message in pubsub.listen():
                        if message.get("type") == "message":
                            on_command(message["data"])
            except (RedisError, OSError) as exc:
                self._set_healthy(False, str(exc))
                await asyncio.sleep(2)

    def _set_healthy(self, ok: bool, error: str = "") -> None:
        if ok != self._healthy:
            self._healthy = ok
            if ok:
                logger.info("bus.recovered")
            else:
                logger.warning("bus.unhealthy", error=error[:200])

    async def close(self) -> None:
        for task in self._tasks:
            task.cancel()
        if self._redis is not None:
            await self._redis.aclose()
