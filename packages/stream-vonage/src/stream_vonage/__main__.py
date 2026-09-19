from __future__ import annotations

import uvicorn

from stream_vonage.settings import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run("stream_vonage.app:app", host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
