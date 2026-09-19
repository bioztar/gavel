"""fixtures/demo.ics -> build_agenda -> exactly the docs/CONTRACT.md §1 shape."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from gavel_calendar.agenda import build_agenda
from gavel_calendar.ics_parser import parse_ics
from gavel_calendar.schema import EARS_DEFAULT_POLICY, ContractAgenda

FIXTURE = Path(__file__).parent.parent / "fixtures" / "demo.ics"
EARS_MEETINGS = (
    Path(__file__).parent.parent.parent / "ears-discord" / "src" / "ears" / "meetings.py"
)


def test_demo_ics_parses() -> None:
    invite = parse_ics(FIXTURE.read_bytes())
    assert invite.title == "Launch readiness"
    assert invite.duration_seconds == 300  # seconds, not minutes
    assert {a.email for a in invite.attendees} == {
        "vitaly@example.invalid",
        "ana@example.invalid",
        "marc@example.invalid",
    }


def test_demo_agenda_matches_contract_shape() -> None:
    invite = parse_ics(FIXTURE.read_bytes())
    agenda = build_agenda(invite, session_id="hb26-demo-1", attendee_map={})

    # Validates cleanly against the contract's own schema (docs/CONTRACT.md §1).
    validated = ContractAgenda.model_validate(agenda)
    assert validated.session_id == "hb26-demo-1"

    # totalSeconds comes from the event's actual duration, not a sum of budgets.
    assert agenda["totalSeconds"] == 300
    assert agenda["totalSeconds"] == invite.duration_seconds

    assert agenda["purpose"] == "Decide the launch date and name an owner for each blocker"

    assert [t["title"] for t in agenda["topics"]] == [
        "Where we actually are",
        "The date",
        "Blocker owners",
    ]
    # Explicit "2m" / "(1 min)" in the invite, in seconds.
    assert [t["budgetSeconds"] for t in agenda["topics"]] == [120, 120, 60]
    assert sum(t["budgetSeconds"] for t in agenda["topics"]) == agenda["totalSeconds"]

    by_id = {a["discordId"]: a for a in agenda["attendees"]}
    assert by_id["vitaly@example.invalid"]["role"] == "host"
    assert by_id["ana@example.invalid"]["role"] == "attendee"

    assert agenda["topics"][0]["owner"] == "ana@example.invalid"
    assert agenda["topics"][1]["owner"] == "vitaly@example.invalid"
    assert agenda["topics"][2]["owner"] is None

    # "must hear: Marc" / "goal: ..." / "q: ..." from the fixture's description.
    assert agenda["topics"][0]["mustHear"] == ["marc@example.invalid"]
    assert agenda["topics"][0]["goal"] == "one clear picture everyone agrees on"
    assert agenda["topics"][1]["questions"] == ["what happens if launch slips a week?"]
    assert agenda["topics"][2]["mustHear"] == []
    assert agenda["topics"][2]["goal"] == ""
    assert agenda["topics"][2]["questions"] == []

    # No override was given — ears-discord's own defaults are left untouched.
    assert "policy" not in agenda


def test_policy_override_is_merged_onto_the_full_default_table() -> None:
    # ears's Agenda.policy does not deep-merge -- a partial dict would drop
    # the other nine keys for this session. A single-key override must still
    # produce all ten on the wire.
    invite = parse_ics(FIXTURE.read_bytes())
    agenda = build_agenda(
        invite,
        session_id="hb26-demo-1",
        attendee_map={},
        policy_overrides={"silenceSeconds": 20},
    )
    assert len(agenda["policy"]) == 10
    assert agenda["policy"] == {**EARS_DEFAULT_POLICY, "silenceSeconds": 20}
    assert agenda["policy"]["floorShareThreshold"] == EARS_DEFAULT_POLICY["floorShareThreshold"]
    ContractAgenda.model_validate(agenda)


def test_policy_defaults_match_ears_exactly() -> None:
    # Guards against drift: this package keeps its own copy of ears's
    # defaults (schema.py:EARS_DEFAULT_POLICY) solely to merge overrides
    # before sending. If ears's table ever changes, this test catches it.
    source = EARS_MEETINGS.read_text()
    match = re.search(r"DEFAULT_POLICY:.*?=\s*(\{.*?\n\})", source, re.DOTALL)
    assert match, "could not find DEFAULT_POLICY in ears-discord's meetings.py"
    ears_default_policy = ast.literal_eval(match.group(1))
    assert ears_default_policy == EARS_DEFAULT_POLICY


def test_attendee_map_overrides_email_fallback() -> None:
    invite = parse_ics(FIXTURE.read_bytes())
    agenda = build_agenda(
        invite,
        session_id="hb26-demo-1",
        attendee_map={"vitaly@example.invalid": "100000000000000001"},
    )
    by_email_fallback = {a["name"]: a["discordId"] for a in agenda["attendees"]}
    assert by_email_fallback["Vitaly"] == "100000000000000001"
    assert by_email_fallback["Ana"] == "ana@example.invalid"  # unmapped: email fallback
    # The owner reference follows the same mapped id.
    assert agenda["topics"][1]["owner"] == "100000000000000001"


def test_missing_topic_duration_splits_remaining_time_evenly() -> None:
    invite = parse_ics(FIXTURE.read_bytes())
    # Same fixture, but simulate a topic with no stated duration by re-parsing
    # a variant description through the same pipeline.
    from gavel_calendar.ics_parser import ParsedInvite, TopicDraft

    variant = ParsedInvite(
        title=invite.title,
        start=invite.start,
        end=invite.end,
        attendees=invite.attendees,
        topics=[
            TopicDraft(title="A", budget_seconds=100, owner_name=None),
            TopicDraft(title="B", budget_seconds=None, owner_name=None),
            TopicDraft(title="C", budget_seconds=None, owner_name=None),
        ],
        description="",
    )
    agenda = build_agenda(variant, session_id="s1", attendee_map={})
    budgets = [t["budgetSeconds"] for t in agenda["topics"]]
    assert budgets[0] == 100
    # 300 total - 100 known = 200 left, split across B and C.
    assert budgets[1] + budgets[2] == 200
    assert sum(budgets) == agenda["totalSeconds"]
