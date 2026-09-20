"""The contract agenda, docs/CONTRACT.md §1 — this package's output shape.

Kept as a standalone pydantic model rather than importing `ears`: the two
packages meet only at the contract, never at each other's code (see the
mission's own rule — read `ears`, never import it).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class Contract(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# Mirrors `ears-discord`'s own `DEFAULT_POLICY`
# (packages/ears-discord/src/ears/meetings.py) exactly. This is NOT a model
# default — `ContractAgenda.policy` below stays `None` unless an invite
# genuinely overrides something. It exists solely so `agenda.py` can merge a
# partial override onto a full table before sending: `ears`'s own
# `Agenda.policy` field does not deep-merge, so a dict with only the
# overridden keys would silently drop the other nine for that session.
# `tests/test_agenda_schema.py::test_policy_defaults_match_ears_exactly` reads
# `ears`'s source directly and fails if this drifts out of sync.
EARS_DEFAULT_POLICY: dict[str, float | bool | str] = {
    "floorShareThreshold": 0.6,
    "floorWindowSeconds": 120,
    "softHandoverSeconds": 45,
    "hardHandoverSeconds": 90,
    "topicOverrunFactor": 1.2,
    "silenceSeconds": 15,
    "minSecondsBetweenInterventions": 45,
    "offAgendaGraceSeconds": 20,
    "allowMute": False,
    "escalateAfterSeconds": 10,
    "muteSeconds": 15,
    # False: the chair opens the meeting herself once everyone is in the call,
    # instead of waiting for "Karen, let's start the meeting".
    "requireStart": True,
    # False: no time budgets and no set order — topics are taken as the room gets to them,
    # and neither a topic nor the meeting runs over.
    "timed": True,
}


# --- how hard the chair leans on the room -------------------------------------------
#
# The gauge the host sets on the confirm page. Each level is a partial override,
# merged over `EARS_DEFAULT_POLICY` the same way `CALENDAR_POLICY_OVERRIDES` is —
# see `compose.handle_send`, which merges the level *over* the environment's
# overrides on purpose: the env carries deployment facts (`requireStart: false`
# for the demo), the gauge carries this meeting's intent, and the gauge wins on
# the keys it names.
#
# "medium" deliberately restates the current demo tuning rather than leaving keys
# out, so picking Medium is an explicit choice and not "whatever the env said".
ENFORCEMENT_LEVELS: dict[str, dict[str, float | bool | str]] = {
    "low": {
        "offAgendaGraceSeconds": 45,
        "minSecondsBetweenInterventions": 90,
        "topicOverrunFactor": 1.5,
        "floorMinSpeakingSeconds": 90,
        "silenceSeconds": 25,
        "escalateAfterSeconds": 20,
        "handover": "soft",
        "allowMute": False,
    },
    "medium": {
        "offAgendaGraceSeconds": 8,
        "minSecondsBetweenInterventions": 45,
        "topicOverrunFactor": 1.2,
        "floorMinSpeakingSeconds": 45,
        "silenceSeconds": 15,
        "escalateAfterSeconds": 10,
        "handover": "soft",
        "allowMute": False,
    },
    # `handover: "hard"` is what the room actually sees: she cuts in as priority
    # speaker instead of waiting for a pause. `allowMute` is the long tail — it
    # only reaches a target through `escalate`, i.e. after an intervention that
    # was already ignored, and `policy.yaml` lists `host` in `neverMuteRoles`,
    # so the organizer is never a candidate whatever this says.
    "high": {
        "offAgendaGraceSeconds": 5,
        "minSecondsBetweenInterventions": 25,
        "topicOverrunFactor": 1.05,
        "floorMinSpeakingSeconds": 30,
        "silenceSeconds": 10,
        "escalateAfterSeconds": 6,
        "handover": "hard",
        "allowMute": True,
        "muteSeconds": 15,
    },
}

DEFAULT_ENFORCEMENT = "medium"


class Attendee(Contract):
    discord_id: str
    name: str
    role: str = "attendee"


class Topic(Contract):
    id: str
    title: str
    goal: str = ""
    budget_seconds: int = Field(ge=0)
    owner: str | None = None
    must_hear: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    # "presentation": one person has the floor by design, so the chair never hands it on.
    type: Literal["discussion", "presentation"] = "discussion"


class ContractAgenda(Contract):
    """The exact shape docs/CONTRACT.md §1 hands to the brain."""

    session_id: str
    purpose: str
    total_seconds: int = Field(ge=0)
    attendees: list[Attendee]
    topics: list[Topic]
    # No local default here on purpose: `ears-discord`'s own `Agenda.policy`
    # (packages/ears-discord/src/ears/meetings.py) is the one source of truth
    # for defaults, and its pydantic model does not deep-merge a supplied
    # dict — it fully replaces its own. So this field is only ever set when
    # an invite genuinely overrides specific keys — and `agenda.py` merges
    # that override onto `EARS_DEFAULT_POLICY` above before sending, so the
    # dict that goes out always carries every key, not just the override.
    policy: dict[str, float | bool | str] | None = None
