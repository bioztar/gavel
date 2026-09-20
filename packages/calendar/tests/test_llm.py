from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pytest_httpx import HTTPXMock

from gavel_calendar.llm import NebiusClient

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=ZoneInfo("Europe/Madrid"))


async def test_unconfigured_client_never_calls_out() -> None:
    client = NebiusClient(base_url="https://fake.test/v1", api_key="")
    assert client.configured is False
    result = await client.parse_brief(
        "meet in an hour", now=NOW, timezone="Europe/Madrid", attendees=["Vitaly"]
    )
    assert result is None


async def test_parse_brief_success(httpx_mock: HTTPXMock) -> None:
    payload = {
        "title": "Pricing sync",
        "start": "2026-09-19T13:00:00+02:00",
        "duration_minutes": 15,
        "topics": [{"title": "Pricing", "minutes": None, "owner": "Vitaly", "must_hear": []}],
    }
    httpx_mock.add_response(
        url="https://fake.test/v1/chat/completions",
        method="POST",
        json={"choices": [{"message": {"content": json.dumps(payload)}}]},
    )
    client = NebiusClient(base_url="https://fake.test/v1", api_key="key123")
    result = await client.parse_brief(
        "meet in an hour about pricing", now=NOW, timezone="Europe/Madrid", attendees=["Vitaly"]
    )
    assert result is not None
    assert result.title == "Pricing sync"
    assert result.duration_minutes == 15
    assert result.topics[0].title == "Pricing"
    request = httpx_mock.get_request()
    assert request is not None
    system = json.loads(request.content)["messages"][0]["content"]
    # Recommended by Norma — fixed with GPT-5 via Codex
    assert "2026-09-19T12:00+02:00" in system
    assert "Europe/Madrid" in system
    assert "Known attendees: Vitaly" in system
    assert "__NOW__" not in system and "_SYSTEM_PROMPT" not in system


async def test_parse_brief_strips_markdown_fences(httpx_mock: HTTPXMock) -> None:
    payload = {
        "title": "Standup",
        "start": "2026-09-19T13:00:00+02:00",
        "duration_minutes": 10,
        "topics": [],
    }
    fenced = f"```json\n{json.dumps(payload)}\n```"
    httpx_mock.add_response(
        url="https://fake.test/v1/chat/completions",
        method="POST",
        json={"choices": [{"message": {"content": fenced}}]},
    )
    client = NebiusClient(base_url="https://fake.test/v1", api_key="key123")
    result = await client.parse_brief("standup", now=NOW, timezone="Europe/Madrid", attendees=[])
    assert result is not None
    assert result.title == "Standup"


async def test_parse_brief_returns_none_on_malformed_json(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://fake.test/v1/chat/completions",
        method="POST",
        json={"choices": [{"message": {"content": "not json at all"}}]},
    )
    client = NebiusClient(base_url="https://fake.test/v1", api_key="key123")
    result = await client.parse_brief("brief", now=NOW, timezone="Europe/Madrid", attendees=[])
    assert result is None


async def test_parse_brief_returns_none_on_http_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://fake.test/v1/chat/completions", method="POST", status_code=500
    )
    client = NebiusClient(base_url="https://fake.test/v1", api_key="key123")
    result = await client.parse_brief("brief", now=NOW, timezone="Europe/Madrid", attendees=[])
    assert result is None


@pytest.mark.parametrize("field", ["title", "duration_minutes"])
async def test_parse_brief_returns_none_on_schema_mismatch(
    httpx_mock: HTTPXMock, field: str
) -> None:
    payload = {
        "title": "Standup",
        "start": "2026-09-19T13:00:00+02:00",
        "duration_minutes": 10,
        "topics": [],
    }
    del payload[field]
    httpx_mock.add_response(
        url="https://fake.test/v1/chat/completions",
        method="POST",
        json={"choices": [{"message": {"content": json.dumps(payload)}}]},
    )
    client = NebiusClient(base_url="https://fake.test/v1", api_key="key123")
    result = await client.parse_brief("brief", now=NOW, timezone="Europe/Madrid", attendees=[])
    assert result is None
