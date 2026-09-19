FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.16 /uv /uvx /bin/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY packages/stream-vonage/pyproject.toml packages/stream-vonage/uv.lock packages/stream-vonage/README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY packages/stream-vonage/src ./src
RUN uv sync --frozen --no-dev

CMD ["python", "-m", "stream_vonage"]
