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


def test_render_brief_form_prefills_no_addresses() -> None:
    """Page one is a box and a button. Who to invite is optional there and is
    resolved on the confirm page, so no address is on screen before the brief
    has even been dictated."""
    html_out = compose.render_brief_form()
    assert "@" not in html_out.split("<body>")[1].replace("&lt;email&gt;", "")
    assert 'name="attendees"' in html_out
    assert "required" in html_out  # the brief still is


# --- render_confirm_form ---------------------------------------------------------


async def test_render_confirm_form_falls_back_when_llm_unconfigured() -> None:
    html_out = await compose.render_confirm_form(
        "set up a meeting", "Vitaly <vitaly@test.dev>", _settings()
    )
    assert "no agenda in" in html_out.lower()
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


# --- invitees + the invite email -------------------------------------------------


def test_resolve_invitees_always_includes_the_standing_room() -> None:
    """The brief can add people; it can never silently drop one."""
    pairs = compose._resolve_invitees("New Person <new@test.dev>", _settings())
    emails = [email for _, email in pairs]
    assert "new@test.dev" in emails
    for _, email in compose._attendees_from_field(_settings().compose_default_attendees):
        assert email in emails
    assert len(emails) == len(set(emails))  # typed duplicate of a default collapses


def test_invite_email_carries_the_agenda_not_the_brief() -> None:
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    from gavel_calendar.invite_email import render_invite_html, render_invite_text

    agenda = {
        "purpose": "Decide the launch date.",
        "attendees": [
            {"discordId": "u1", "name": "Vitaly"},
            {"discordId": "u2", "name": "Artem"},
        ],
        "topics": [
            {
                "title": "Pricing",
                "budgetSeconds": 600,
                "owner": "u1",
                "mustHear": ["u1", "u2"],
                "type": "discussion",
            },
            {
                "title": "Demo walkthrough",
                "budgetSeconds": 300,
                "owner": "u2",
                "mustHear": ["u2"],
                "type": "presentation",
            },
        ],
    }
    start = datetime(2026, 9, 20, 10, 0, tzinfo=ZoneInfo("Europe/Madrid"))
    kw = {
        "title": "Launch call",
        "start": start,
        "end": start + timedelta(minutes=15),
        "join_url": "https://cal.test/m/abc",
        "discord_url": "https://discord.test/x",
    }
    for body in (render_invite_html(agenda, **kw), render_invite_text(agenda, **kw)):
        assert "Decide the launch date." in body
        assert "Pricing" in body and "Demo walkthrough" in body
        assert "10 min" in body and "5 min" in body
        assert "Artem" in body and "Vitaly" in body
        assert "presentation" in body.lower()


def test_invite_email_does_not_repeat_the_owner_as_must_be_heard():
    """A presentation arrives with its presenter as the only must-hear (compose's
    fallback). Saying it twice on one row is noise, not information."""
    from datetime import datetime, timedelta

    from gavel_calendar.invite_email import render_invite_text

    agenda = {
        "purpose": "Decide the cut.",
        "attendees": [
            {"discordId": "vitaly", "name": "Vitaly"},
            {"discordId": "artem", "name": "Artem"},
        ],
        "topics": [
            {"title": "Architecture", "budgetSeconds": 300, "type": "presentation",
             "owner": "vitaly", "mustHear": ["vitaly"]},
            {"title": "Open discussion", "budgetSeconds": 360, "type": "discussion",
             "owner": "vitaly", "mustHear": ["vitaly", "artem"]},
        ],
    }
    start = datetime(2026, 9, 20, 10, 0)
    body = render_invite_text(
        agenda, title="demo", start=start, end=start + timedelta(minutes=15),
        join_url="https://x/j", discord_url="https://d/x",
    )
    arch, disc = body.split("2. Open discussion")
    assert "must be heard: —" in arch
    assert "must be heard: Vitaly, Artem" in disc
