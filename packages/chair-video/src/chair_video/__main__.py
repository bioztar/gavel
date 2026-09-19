from __future__ import annotations

import uvicorn

from chair_video.settings import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run("chair_video.app:app", host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
