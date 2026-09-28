"""The seam secret rides on every call into ears, and only when configured."""

from __future__ import annotations

from pytest_httpx import HTTPXMock

from gavel_calendar.ears_client import EarsClient

AGENDA = {"sessionId": "s1", "purpose": "p", "totalSeconds": 60, "attendees": [], "topics": []}


async def test_seam_secret_is_sent_on_both_calls(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://ears.test/api/meetings", json={"id": "m1"})
    httpx_mock.add_response(url="http://ears.test/api/sessions", json={"sessionId": "e1"})
    ears = EarsClient("http://ears.test", seam_secret="seam-test-secret")
    assert await ears.create_meeting("t", "c", AGENDA) == "m1"
    assert await ears.start_session("m1") == "e1"
    for req in httpx_mock.get_requests():
        assert req.headers["x-seam-secret"] == "seam-test-secret"


async def test_no_secret_means_no_header(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://ears.test/api/meetings", json={"id": "m1"})
    await EarsClient("http://ears.test").create_meeting("t", "c", AGENDA)
    assert "x-seam-secret" not in httpx_mock.get_requests()[0].headers
