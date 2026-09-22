"""Karen's camera tile: a persona still, letterboxed by ffmpeg and published as a video track.

`face.js` does the publishing inside the page (see the comment at the top of it for why
Chromium's own fake-camera flags are not usable here). This module's job is to turn the
configured image into something that script can draw: one JPEG at exactly the camera size,
aspect preserved and padded rather than squashed, inlined as a `data:` URL.

Nothing here generates video. If the image is missing or ffmpeg is not installed we log the
SETTING name and return `None`; the bot then joins with its camera off, exactly as before.
"""

from __future__ import annotations

import asyncio
import base64
import json
import shutil
from pathlib import Path

from .logging import get_logger
from .settings import Settings

logger = get_logger("ears_meet.face")

FACE_JS = (Path(__file__).parent / "face.js").read_text(encoding="utf-8")


async def _letterbox_jpeg(src: Path, width: int, height: int) -> bytes | None:
    """The still at exactly `width` x `height`: scaled down to fit, then padded to fill."""
    if shutil.which("ffmpeg") is None:
        logger.warning("face.no_ffmpeg", detail="ffmpeg is not installed; joining without a camera")
        return None
    video_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x1b1b1f"
    )
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(src),
        "-vf",
        video_filter,
        "-frames:v",
        "1",
        "-q:v",
        "4",
        "-f",
        "image2",
        "-vcodec",
        "mjpeg",
        "pipe:1",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0 or not out:
        logger.warning("face.ffmpeg_failed", detail=err.decode("utf-8", "replace").strip()[:200])
        return None
    return out


def _resolve(image: str) -> Path | None:
    """The configured still, if it is there. Blocking, so it runs off the event loop."""
    src = Path(image).expanduser()
    return src if src.is_file() else None


async def build_script(settings: Settings) -> str | None:
    """The init script that publishes the face, or `None` to join with the camera off."""
    if not settings.meet_face_image:
        return None
    src = await asyncio.to_thread(_resolve, settings.meet_face_image)
    if src is None:
        logger.warning(
            "face.image_missing", setting="MEET_FACE_IMAGE", path=settings.meet_face_image
        )
        return None
    jpeg = await _letterbox_jpeg(src, settings.meet_face_width, settings.meet_face_height)
    if jpeg is None:
        return None
    data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
    logger.info(
        "face.ready",
        path=str(src),
        size=f"{settings.meet_face_width}x{settings.meet_face_height}",
        kb=round(len(jpeg) / 1024),
    )
    # json.dumps, not bare interpolation: the label comes from a setting and has to land in
    # the script as a JavaScript string literal whatever is in it.
    return (
        FACE_JS.replace("__FACE__", json.dumps(data_url))
        .replace("__LABEL__", json.dumps(settings.meet_bot_name))
        .replace("__W__", str(settings.meet_face_width))
        .replace("__H__", str(settings.meet_face_height))
        .replace("__FPS__", str(settings.meet_face_fps))
    )
