"""Who gets invited, with the LLM mocked at the HTTP edge (`pytest_httpx`).

The one rule under test: an address reaches the invite only if the host typed
it. The model may read the guest list off the brief; it may not add to it.
"""

from __future__ import annotations

import json

import pytest
from pytest_httpx import HTTPXMock
from starlette.datastructures import FormData

from gavel_calendar import compose, invitees
from gavel_calendar.llm import BriefInvitee, ParsedBrief
from gavel_calendar.settings import Settings

NEBIUS = "https://fake.test/v1/chat/completions"


def _settings(**overrides: str) -> Settings:
    defaults: dict[str, str] = {
        "nebius_api_key": "key123",
        "nebius_base_url": "https://fake.test/v1",
        "resend_api_key": "",
        "compose_from_email": "",
        "compose_host": "",
        "compose_timezone": "Europe/Madrid",
        "calendar_public_url": "http://localhost:8790",
    }
    defaults.update(overrides)
    return Settings.model_validate(defaults)


def _mock_llm(httpx_mock: HTTPXMock, invitee_list: list[dict[str, str]]) -> None:
    payload = {
        "title": "Pricing sync",
        "purpose": "Land the price.",
        "start": "2026-09-19T13:00:00+02:00",
        "duration_minutes": 30,
        "invitees": invitee_list,
        "topics": [{"title": "Pricing", "minutes": 30, "owner": "Artem", "must_hear": []}],
    }
    httpx_mock.add_response(
        url=NEBIUS, method="POST", json={"choices": [{"message": {"content": json.dumps(payload)}}]}
    )


# --- the schema --------------------------------------------------------------------


def test_parsed_brief_accepts_invitees_and_defaults_to_none() -> None:
    parsed = ParsedBrief.model_validate(
        {
            "title": "t",
            "start": "2026-09-19T13:00:00+02:00",
            "duration_minutes": 30,
            "invitees": [{"name": "Artem", "email": "artem@test.dev"}],
        }
    )
    assert parsed.invitees == [BriefInvitee(name="Artem", email="artem@test.dev")]
    bare = ParsedBrief.model_validate(
        {"title": "t", "start": "2026-09-19T13:00:00+02:00", "duration_minutes": 30}
    )
    assert bare.invitees == []


def test_a_malformed_invitee_costs_that_line_not_the_parse() -> None:
    parsed = ParsedBrief.model_validate(
        {
            "title": "t",
            "start": "2026-09-19T13:00:00+02:00",
            "duration_minutes": 30,
            "invitees": [{"name": "Artem"}, {"email": "not an address"}],
            "topics": [{"title": "Pricing"}],
        }
    )
    assert [t.title for t in parsed.topics] == ["Pricing"]
    resolved = invitees.resolve(parsed.invitees, source="anything", explicit=[])
    assert resolved.invitees == []
    assert resolved.stripped == ["not an address"]


# --- resolve: the no-hallucination rule ------------------------------------------------


def test_resolve_keeps_only_addresses_the_host_typed() -> None:
    brief = "Karen, thirty minutes with Artem <artem@test.dev> and Ana (ana@test.dev) on pricing."
    inferred = [
        BriefInvitee(name="Artem", email="artem@test.dev"),
        BriefInvitee(name="Ana", email="ANA@test.dev"),  # case differs; same mailbox
        BriefInvitee(name="Marc", email="marc@test.dev"),  # never mentioned
        BriefInvitee(name="Artem", email="artem@example.com"),  # completed into a guess
    ]
    resolved = invitees.resolve(inferred, source=brief, explicit=[])
    assert [(i.name, i.email) for i in resolved.invitees] == [
        ("Artem", "artem@test.dev"),
        ("Ana", "ana@test.dev"),
    ]
    assert resolved.stripped == ["artem@example.com", "marc@test.dev"]


def test_resolve_orders_host_then_explicit_then_inferred_and_dedupes() -> None:
    host = invitees.Invitee(name="Host", email="host@test.dev")
    explicit = invitees.from_field("Ana Typed <ana@test.dev>")
    inferred = [
        BriefInvitee(name="Ana", email="ana@test.dev"),  # typed spelling of the name wins
        BriefInvitee(name="", email="artem@test.dev"),  # no name: local part
        BriefInvitee(name="Host", email="host@test.dev"),
    ]
    resolved = invitees.resolve(
        inferred, source="pricing with artem@test.dev", explicit=explicit, host=host
    )
    assert [(i.name, i.email) for i in resolved.invitees] == [
        ("Host", "host@test.dev"),
        ("Ana Typed", "ana@test.dev"),
        ("Artem", "artem@test.dev"),
    ]
    assert resolved.stripped == []


def test_an_explicitly_typed_address_counts_as_typed() -> None:
    explicit = invitees.from_field("marc@test.dev")
    resolved = invitees.resolve(
        [BriefInvitee(name="Marc", email="marc@test.dev")], source="no addresses", explicit=explicit
    )
    assert [i.email for i in resolved.invitees] == ["marc@test.dev"]
    assert resolved.stripped == []


def test_addresses_in_finds_them_inside_prose_and_brackets() -> None:
    text = "Ping Ana<ana@test.dev>, artem.k@sub.test.dev; and (marc+x@test.dev)."
    assert invitees.addresses_in(text) == {
        "ana@test.dev",
        "artem.k@sub.test.dev",
        "marc+x@test.dev",
    }
    assert invitees.addresses_in("nobody here @ all") == set()


def test_from_form_reads_rows_and_drops_blanks_and_non_addresses() -> None:
    form = FormData(
        [
            ("invitees_count", "4"),
            ("invitee_name_0", "Ana"),
            ("invitee_email_0", " Ana@test.dev "),
            ("invitee_name_1", ""),
            ("invitee_email_1", ""),
            ("invitee_name_2", "Broken"),
            ("invitee_email_2", "not-an-address"),
            ("invitee_name_3", ""),
            ("invitee_email_3", "artem@test.dev"),
        ]
    )
    assert [(i.name, i.email) for i in invitees.from_form(form)] == [
        ("Ana", "ana@test.dev"),
        ("Artem", "artem@test.dev"),
    ]
    assert invitees.from_form(FormData([])) == []


# --- through the confirm page, LLM mocked ------------------------------------------------


async def test_confirm_page_shows_inferred_invitees_and_names_the_stripped_ones(
    httpx_mock: HTTPXMock,
) -> None:
    _mock_llm(
        httpx_mock,
        [
            {"name": "Artem", "email": "artem@test.dev"},
            {"name": "Marc", "email": "marc@test.dev"},  # hallucinated
        ],
    )
    html_out = await compose.render_confirm_form(
        "Karen, thirty minutes with Artem <artem@test.dev> tomorrow at ten on pricing.",
        "",
        _settings(compose_host="Host <host@test.dev>"),
    )
    assert 'value="host@test.dev"' in html_out
    assert 'value="artem@test.dev"' in html_out
    assert 'value="marc@test.dev"' not in html_out
    assert "Left out" in html_out and "marc@test.dev" in html_out
    assert 'name="confirm" value="yes" required' in html_out
    assert 'action="/compose/send"' in html_out


async def test_confirm_page_has_no_standing_room(httpx_mock: HTTPXMock) -> None:
    """With no host configured and nobody typed, the guest list is exactly what the
    brief said — and if the brief named nobody with an address, it is empty."""
    _mock_llm(httpx_mock, [])
    html_out = await compose.render_confirm_form("Karen, pricing tomorrow at ten.", "", _settings())
    body = html_out.split("<body>")[1]
    assert 'invitees_count" value="1"' in body  # just the spare row
    assert "@" not in body.replace("&mdash;", "")


async def test_llm_that_returns_no_invitees_key_still_renders(httpx_mock: HTTPXMock) -> None:
    payload = {
        "title": "Pricing sync",
        "start": "2026-09-19T13:00:00+02:00",
        "duration_minutes": 30,
        "topics": [{"title": "Pricing"}],
    }
    httpx_mock.add_response(
        url=NEBIUS, method="POST", json={"choices": [{"message": {"content": json.dumps(payload)}}]}
    )
    html_out = await compose.render_confirm_form(
        "pricing", "Ana <ana@test.dev>", _settings(compose_host="Host <host@test.dev>")
    )
    assert 'value="host@test.dev"' in html_out and 'value="ana@test.dev"' in html_out


@pytest.mark.parametrize("compose_host", ["", "Host <host@test.dev>"])
async def test_prompt_lists_the_host_first_and_never_an_inferred_address(
    httpx_mock: HTTPXMock, compose_host: str
) -> None:
    _mock_llm(httpx_mock, [{"name": "Artem", "email": "artem@test.dev"}])
    await compose.render_confirm_form(
        "pricing with Artem <artem@test.dev>",
        "Ana <ana@test.dev>",
        _settings(compose_host=compose_host),
    )
    request = httpx_mock.get_requests()[0]
    system = json.loads(request.content)["messages"][0]["content"]
    expected = "Known attendees: Host, Ana." if compose_host else "Known attendees: Ana."
    assert expected in system
    assert "@" not in system.split("Known attendees:")[1].split(".")[0]
