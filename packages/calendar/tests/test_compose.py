from __future__ import annotations

import json

import pytest
from pytest_httpx import HTTPXMock
from starlette.datastructures import FormData

from gavel_calendar import compose
from gavel_calendar.settings import Settings
from gavel_calendar.store import InviteStore


def _settings(**overrides: str) -> Settings:
    """A `Settings` built entirely from explicit values — init kwargs win over
    any real `.env` on this machine (pydantic-settings source precedence), so
    these tests never depend on, or risk touching, real secrets.
    """
    defaults: dict[str, str] = {
        "nebius_api_key": "",
        "nebius_base_url": "https://fake.test/v1",
        "resend_api_key": "",
        "compose_from_email": "",
        "compose_default_attendees": "Vitaly <vitaly@test.dev>, Artem <artem@test.dev>",
        "discord_meeting_url": "https://discordapp.com/channels/1/2",
        "compose_timezone": "Europe/Madrid",
        "calendar_public_url": "http://localhost:8790",
    }
    defaults.update(overrides)
    return Settings.model_validate(defaults)


def _form(fields: dict[str, str]) -> FormData:
    return FormData(list(fields.items()))


# --- pure helpers --------------------------------------------------------------


def test_attendees_from_field_parses_name_and_bare_email() -> None:
    pairs = compose._attendees_from_field("Vitaly <vitaly@test.dev>, artem@test.dev")
    assert pairs[0] == ("Vitaly", "vitaly@test.dev")
    assert pairs[1] == ("Artem", "artem@test.dev")


def test_attendees_from_field_skips_blank() -> None:
    assert compose._attendees_from_field("") == []


@pytest.mark.parametrize(
    ("minutes", "total", "expected"),
    [
        ([None, None], 45, [22, 23]),
        ([10, None, None], 40, [10, 15, 15]),
        ([15, 15], 30, [15, 15]),
        ([None], 15, [15]),
    ],
)
def test_fill_topic_minutes_is_always_whole_minutes(
    minutes: list[int | None], total: int, expected: list[int]
) -> None:
    filled = compose._fill_topic_minutes(minutes, total)
    assert filled == expected
    assert sum(filled) == total


def test_render_brief_form_escapes_default_attendees() -> None:
    html_out = compose.render_brief_form("<script>alert(1)</script>")
    assert "<script>alert(1)</script>" not in html_out
    assert "&lt;script&gt;" in html_out


# --- render_confirm_form ---------------------------------------------------------


async def test_render_confirm_form_falls_back_when_llm_unconfigured() -> None:
    html_out = await compose.render_confirm_form(
        "set up a meeting", "Vitaly <vitaly@test.dev>", _settings()
    )
    assert "Could not parse" in html_out
    assert "set up a meeting" in html_out


async def test_render_confirm_form_uses_parsed_brief(httpx_mock: HTTPXMock) -> None:
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
    html_out = await compose.render_confirm_form(
        "meet in an hour about pricing",
        "Vitaly <vitaly@test.dev>",
        _settings(nebius_api_key="key123"),
    )
    assert "Pricing sync" in html_out
    assert 'value="Pricing"' in html_out


# --- handle_send ----------------------------------------------------------------


async def test_handle_send_creates_meeting_even_when_mail_is_dry_run() -> None:
    store = InviteStore()
    form = _form(
        {
            "title": "Pricing sync",
            "brief": "let's talk pricing",
            "attendees": "Vitaly <vitaly@test.dev>, Artem <artem@test.dev>",
            "start": "2026-09-20T15:00",
            "duration_minutes": "30",
            "topics_count": "1",
            "topic_title_0": "Pricing",
            "topic_minutes_0": "",
            "topic_owner_0": "Vitaly",
            "topic_must_hear_0": "Artem",
        }
    )
    html_out = await compose.handle_send(form, store, _settings())

    assert len(store._records) == 1
    record = next(iter(store._records.values()))
    assert record.title == "Pricing sync"
    assert record.agenda["topics"][0]["budgetSeconds"] == 1800
    assert "not sent" in html_out
    assert record.session_id in html_out


async def test_handle_send_survives_mailer_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    """The single most important behavior: a mailer bug must never cost the
    meeting or a 500 — the join link still has to work.
    """

    async def _boom(**_kwargs: object) -> None:
        raise RuntimeError("resend is on fire")

    monkeypatch.setattr(compose, "send_invite", _boom)

    store = InviteStore()
    form = _form(
        {
            "title": "Standup",
            "brief": "quick one",
            "attendees": "Vitaly <vitaly@test.dev>",
            "start": "2026-09-20T09:00",
            "duration_minutes": "15",
            "topics_count": "0",
        }
    )
    html_out = await compose.handle_send(form, store, _settings(resend_api_key="key123"))

    assert len(store._records) == 1
    record = next(iter(store._records.values()))
    assert record.title == "Standup"
    assert "not sent" in html_out
    assert record.session_id in html_out
