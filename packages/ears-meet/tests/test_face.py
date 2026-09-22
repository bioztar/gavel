"""The camera still: what gets built, and what happens when it cannot be."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from ears_meet.face import build_script
from ears_meet.settings import Settings

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")


def _png(path, size=(1024, 1024)):
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=red:s={size[0]}x{size[1]}",
            "-frames:v",
            "1",
            str(path),
        ],
        check=True,
    )
    return path


@pytest.mark.asyncio
async def test_build_script_inlines_a_letterboxed_still(tmp_path):
    src = _png(tmp_path / "karen.png")
    script = await build_script(
        Settings(
            meet_face_image=str(src),
            meet_face_width=320,
            meet_face_height=240,
            meet_face_fps=5,
            meet_bot_name='Karen "the chair"',
        )
    )
    assert script is not None
    assert "data:image/jpeg;base64," in script
    assert "gavel-face-still" in script
    # The name is a setting, so it has to land as a JavaScript string literal whatever is in it.
    assert json.dumps('Karen "the chair"') in script
    # No placeholder survives substitution.
    assert "__" + "FACE__" not in script and "__" + "W__" not in script


@pytest.mark.asyncio
async def test_no_image_means_no_camera(tmp_path):
    assert await build_script(Settings(meet_face_image="")) is None
    assert await build_script(Settings(meet_face_image=str(tmp_path / "nope.png"))) is None
