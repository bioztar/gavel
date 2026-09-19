"""Meetings set up in the console, and the agenda they carry.

The agenda is the contract's agenda (docs/CONTRACT.md §1) minus `sessionId`,
which ears fills in when a session starts. ears never interprets it — it stores
it and hands it to the brain in `session.started`.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from .frames import Frame


class Attendee(Frame):
    discord_id: str
    name: str
    role: str = "attendee"


class Topic(Frame):
    id: str
    title: str
    goal: str = ""
    budget_seconds: int = Field(ge=0)
    owner: str | None = None
    must_hear: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


DEFAULT_POLICY: dict[str, float] = {
    "floorShareThreshold": 0.6,
    "floorWindowSeconds": 120,
    "floorMinSpeakingSeconds": 45,
    "topicOverrunFactor": 1.2,
    "silenceSeconds": 15,
    "minSecondsBetweenInterventions": 45,
}


class Agenda(Frame):
    purpose: str = ""
    total_seconds: int = 0
    attendees: list[Attendee] = Field(default_factory=list)
    topics: list[Topic] = Field(default_factory=list)
    policy: dict[str, Any] = Field(default_factory=lambda: dict(DEFAULT_POLICY))

    @model_validator(mode="after")
    def _total(self) -> Agenda:
        # The contract says budgets "should sum to roughly" the total; default it to the sum.
        if not self.total_seconds:
            object.__setattr__(self, "total_seconds", sum(t.budget_seconds for t in self.topics))
        return self


class MeetingIn(Frame):
    title: str = Field(min_length=1, max_length=200)
    context: str = ""
    agenda: Agenda = Field(default_factory=Agenda)


class Meeting(MeetingIn):
    id: str
    created_at: str
    updated_at: str

    def agenda_for(self, session_id: str) -> dict[str, Any]:
        """The contract agenda, stamped with the session it runs in."""
        return {"sessionId": session_id, **self.agenda.model_dump(by_alias=True)}
