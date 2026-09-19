FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.16 /uv /uvx /bin/

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates ffmpeg git libopus0 \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY packages/ears-discord/pyproject.toml packages/ears-discord/uv.lock packages/ears-discord/README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY packages/ears-discord/src ./src
COPY packages/ears-discord/alembic ./alembic
COPY packages/ears-discord/alembic.ini ./alembic.ini
RUN uv sync --frozen --no-dev

CMD ["python", "-m", "ears"]
