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
    # (packages/ears-discord/src/ears/meetings.py) is the one source of truth for
    # defaults, and its pydantic model does not deep-merge a supplied dict — it
    # fully replaces its own. So this field is only ever set when an invite
    # genuinely overrides specific keys, and then it carries only those keys.
    policy: dict[str, float | bool] | None = None
