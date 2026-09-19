"""The contract agenda, docs/CONTRACT.md §1 — this package's output shape.

Kept as a standalone pydantic model rather than importing `ears`: the two
packages meet only at the contract, never at each other's code (see the
mission's own rule — read `ears`, never import it).
"""

from __future__ import annotations

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
EARS_DEFAULT_POLICY: dict[str, float | bool] = {
    "floorShareThreshold": 0.6,
    "floorWindowSeconds": 120,
    "floorMinSpeakingSeconds": 45,
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
}


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
    # dict that goes out always carries all eleven keys, not just the override.
    policy: dict[str, float | bool] | None = None
