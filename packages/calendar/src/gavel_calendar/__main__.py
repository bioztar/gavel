from __future__ import annotations

import uvicorn

from .settings import get_settings

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "gavel_calendar.app:app",
        host=settings.calendar_host,
        port=settings.calendar_port,
        log_level=settings.log_level.lower(),
    )
