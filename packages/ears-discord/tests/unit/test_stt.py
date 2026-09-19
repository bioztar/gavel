from __future__ import annotations

import httpx
import pytest
from pytest_httpx import HTTPXMock

from ears.settings import Settings
from ears.stt import SlngStt, SttError

URL = "https://eu-west.api.slng.ai/v1/stt/deepgram/nova:3"


def settings() -> Settings:
    return Settings(_env_file=None, slng_api_key="k")  # type: ignore[call-arg]


async def test_transcribe_parses_deepgram_shape(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=URL,
        json={
            "results": {
                "channels": [{"alternatives": [{"transcript": " hi Ana ", "confidence": 0.9}]}]
            }
        },
    )
    async with httpx.AsyncClient() as client:
        result = await SlngStt(settings(), client).transcribe(b"\x00\x00" * 1600, keyterms=["Ana"])
    assert (result.text, result.confidence) == ("hi Ana", 0.9)
    request = httpx_mock.get_request()
    assert request is not None
    assert request.headers["authorization"] == "Bearer k"
    body = request.read()
    assert b'name="keyterm"' in body and b"Ana" in body and b'name="audio"' in body


async def test_http_error_raises(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=URL, status_code=400, text="bad")
    async with httpx.AsyncClient() as client:
        with pytest.raises(SttError, match="HTTP 400"):
            await SlngStt(settings(), client).transcribe(b"\x00\x00")
