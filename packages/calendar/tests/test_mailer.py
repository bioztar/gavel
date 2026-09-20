from __future__ import annotations

import httpx
from pytest_httpx import HTTPXMock

from gavel_calendar.mailer import send_invite


async def test_dry_run_when_no_api_key() -> None:
    result = await send_invite(
        api_key="",
        from_email="from@test.dev",
        to=["to@test.dev"],
        subject="hi",
        text_body="body",
        ics_bytes=b"BEGIN:VCALENDAR\nEND:VCALENDAR\n",
    )
    assert result.sent is False
    assert result.reason is not None


async def test_dry_run_when_no_from_email() -> None:
    result = await send_invite(
        api_key="key123",
        from_email="",
        to=["to@test.dev"],
        subject="hi",
        text_body="body",
        ics_bytes=b"BEGIN:VCALENDAR\nEND:VCALENDAR\n",
    )
    assert result.sent is False
    assert result.reason is not None


async def test_send_succeeds(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://api.resend.com/emails", method="POST", json={"id": "abc"})
    result = await send_invite(
        api_key="key123",
        from_email="from@test.dev",
        to=["to@test.dev"],
        subject="hi",
        text_body="body",
        ics_bytes=b"BEGIN:VCALENDAR\nEND:VCALENDAR\n",
    )
    assert result.sent is True
    assert result.reason is None


async def test_send_failure_never_raises_on_bad_status(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://api.resend.com/emails", method="POST", status_code=422)
    result = await send_invite(
        api_key="key123",
        from_email="from@test.dev",
        to=["to@test.dev"],
        subject="hi",
        text_body="body",
        ics_bytes=b"BEGIN:VCALENDAR\nEND:VCALENDAR\n",
    )
    assert result.sent is False
    assert "422" in (result.reason or "")


async def test_send_failure_never_raises_on_network_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(httpx.ConnectError("boom"))
    result = await send_invite(
        api_key="key123",
        from_email="from@test.dev",
        to=["to@test.dev"],
        subject="hi",
        text_body="body",
        ics_bytes=b"BEGIN:VCALENDAR\nEND:VCALENDAR\n",
    )
    assert result.sent is False
    assert result.reason is not None
