FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.16 /uv /uvx /bin/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY packages/chair-video/pyproject.toml packages/chair-video/uv.lock packages/chair-video/README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY packages/chair-video/src ./src
COPY packages/chair-video/avatars ./avatars
RUN uv sync --frozen --no-dev

CMD ["python", "-m", "chair_video"]
