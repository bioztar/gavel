"""structlog setup, stdlib logging (py-cord, uvicorn) routed to the same sink."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

_configured = False


def setup_logging(level: str = "INFO", json_logs: bool = False) -> None:
    global _configured
    if _configured:
        return
    renderer: Any = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="%H:%M:%S.%f", utc=False),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(
        format="%(levelname)s [%(name)s] %(message)s", stream=sys.stdout, level=level.upper()
    )
    # py-cord's voice internals are chatty at INFO.
    logging.getLogger("discord").setLevel(logging.WARNING)
    _configured = True


def get_logger(name: str) -> Any:
    return structlog.get_logger(name)
