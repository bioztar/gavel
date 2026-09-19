"""Meetings set up in the console, and the agenda they carry.

The agenda is the contract's agenda (docs/CONTRACT.md §1) minus `sessionId`,
which ears fills in when a session starts. ears never interprets it — it stores
it and hands it to the brain in `session.started`.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from .frames import Frame, Participant


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


DEFAULT_POLICY: dict[str, float | bool] = {
    "floorShareThreshold": 0.6,
    "floorWindowSeconds": 120,
    "floorMinSpeakingSeconds": 45,
    "topicOverrunFactor": 1.2,
    "silenceSeconds": 15,
    "minSecondsBetweenInterventions": 45,
    # The chair's moderation (brain): how long someone may drift off the agenda before
    # it parks the point and steers back, and whether it may escalate to a short mute.
    "offAgendaGraceSeconds": 20,
    "allowMute": False,
    "escalateAfterSeconds": 10,
    "muteSeconds": 15,
    # False: the chair opens the meeting herself once everyone is in the call, instead of
    # waiting for "Karen, let's start the meeting".
    "requireStart": True,
    # False: no time budgets and no set order — topics are taken as the room gets to them,
    # and neither a topic nor the meeting runs over.
    "timed": True,
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
        # An untimed meeting has no length at all.
        if self.policy.get("timed") is False:
            object.__setattr__(self, "total_seconds", 0)
        elif not self.total_seconds:
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

    def agenda_for(
        self, session_id: str, participants: list[Participant]
    ) -> dict[str, Any]:
        """Build a session agenda using whoever is currently in the voice channel.

        Meetings are reusable templates, so their saved attendee list must not decide who
        attends a particular run. Keep a saved role when it matches a present Discord user
        (useful for imported agendas); otherwise every present person is an attendee.
        """
        saved = {attendee.discord_id: attendee for attendee in self.agenda.attendees}
        attendees: list[dict[str, str]] = []
        for person in participants:
            previous = saved.get(person.discord_id)
            attendees.append(
                {
                    "discordId": person.discord_id,
                    "name": person.name,
                    "role": previous.role if previous else "attendee",
                }
            )
        # The old "from voice" button made the first person the host. Preserve that
        # useful default without making operators manage the roster themselves.
        matched_saved_attendee = any(
            person.discord_id in saved for person in participants
        )
        if (
            attendees
            and not matched_saved_attendee
            and not any(person["role"] == "host" for person in attendees)
        ):
            attendees[0]["role"] = "host"
        return {
            "sessionId": session_id,
            **self.agenda.model_dump(by_alias=True, exclude={"attendees"}),
            "attendees": attendees,
        }
