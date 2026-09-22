# ears-meet: a real Chromium on a virtual display, with PulseAudio for the audio in and out.
# Build from the repo root:  docker build -f packages/ears-meet/Dockerfile -t gavel-ears-meet:local .
#
# Playwright's image carries Chromium and every library it needs; keep the tag in step with
# the `playwright` version pinned in uv.lock (the Python package downloads a matching browser
# at `playwright install`, so a mismatch costs a second download, not a failure).
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble

COPY --from=ghcr.io/astral-sh/uv:0.12.16 /uv /uvx /bin/

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        ca-certificates ffmpeg xvfb pulseaudio pulseaudio-utils dbus-x11 \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    # Chromium and PulseAudio both refuse (or need --no-sandbox / --system) to run as root.
    HOME=/home/pwuser \
    PULSE_MANAGE=true \
    XVFB_MANAGE=true \
    DISPLAY=:99

WORKDIR /app

COPY packages/ears-meet/pyproject.toml packages/ears-meet/uv.lock packages/ears-meet/README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY packages/ears-meet/src ./src
COPY packages/ears-meet/scripts ./scripts
RUN uv sync --frozen --no-dev \
    && playwright install chromium \
    && mkdir -p /profile /recordings \
    && chown -R pwuser:pwuser /app /profile /recordings /home/pwuser

# The signed-in Chromium profile is mounted here (MEET_PROFILE_DIR=/profile); it is
# never part of the image.
VOLUME ["/profile", "/recordings"]
USER pwuser

CMD ["python", "-m", "ears_meet"]
