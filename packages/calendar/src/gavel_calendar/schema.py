"""The contract agenda, docs/CONTRACT.md §1 — this package's output shape.

Kept as a standalone pydantic model rather than importing `ears`: the two
packages meet only at the contract, never at each other's code (see the
mission's own rule — read `ears`, never import it).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

# docs/CONTRACT.md §1 — the policy defaults, tunable on stage without a redeploy.
DEFAULT_POLICY: dict[str, float] = {
    "floorShareThreshold": 0.6,
    "floorWindowSeconds": 120,
    "floorMinSpeakingSeconds": 45,
    "topicOverrunFactor": 1.2,
    "silenceSeconds": 15,
    "minSecondsBetweenInterventions": 45,
}


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
    policy: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_POLICY))
