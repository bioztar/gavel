"""Meetings set up in the console, and the agenda they carry.

The agenda is the contract's agenda (docs/CONTRACT.md §1) minus `sessionId`,
which ears fills in when a session starts. ears never interprets it — it stores
it and hands it to the brain in `session.started`.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, Literal

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
    # "presentation": one person has the floor by design, so the chair never hands it on.
    type: Literal["discussion", "presentation"] = "discussion"


DEFAULT_POLICY: dict[str, float | bool | str] = {
    "floorShareThreshold": 0.6,
    "floorWindowSeconds": 120,
    # Speaking time in the window that earns a floor handover: soft at the talker's next
    # pause, hard (0: never) cutting in at once as priority speaker.
    "softHandoverSeconds": 45,
    "hardHandoverSeconds": 90,
    "topicOverrunFactor": 1.2,
    "silenceSeconds": 15,
    "minSecondsBetweenInterventions": 45,
    # The chair's moderation (brain): how long someone may drift off the agenda before
    # it parks the point and steers back, and whether it may escalate to a short mute.
    "offAgendaGraceSeconds": 20,
    "allowMute": False,
    "escalateAfterSeconds": 10,
    "muteSeconds": 15,
    # False (the default): the chair opens the meeting herself once every expected
    # attendee is in the call. Either way "Karen, let's start the meeting" opens it at
    # once, however few people are there. True: only that instruction ever opens it.
    "requireStart": False,
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


# --- who in the call is who on the roster -------------------------------------------------
#
# An invitation has names and emails; a voice channel has snowflakes. `packages/calendar`
# falls back to the email as the `discordId` when no operator mapped one, so the only thing
# the two ever share is the person's name. Matching on it is what makes someone who joins
# the call the expected attendee rather than a stranger — see `Meeting.agenda_for`. The
# brain does the same for people who arrive after the session started (its `bindByName`).

_WORDS = re.compile(r"[a-z0-9]+")


def _tokens(name: str) -> tuple[str, ...]:
    return tuple(_WORDS.findall(name.casefold()))


def _match_score(expected: str, present: str) -> int:
    """How strongly a roster name and a Discord display name read as one person.

    3: the same name. 2: one name inside the other ("Vitaly" / "Vitaly P"). 1: the same
    first name, or a run-together handle that starts with it ("Artem" / "artemshambalev").
    0: no reason to think they are the same person — never guess past this.
    """
    a, b = _tokens(expected), _tokens(present)
    if not a or not b:
        return 0
    if a == b:
        return 3
    if set(a) <= set(b) or set(b) <= set(a):
        return 2
    if a[0] == b[0]:
        return 1
    if len(a) == 1 or len(b) == 1:
        short, long = sorted((a[0], b[0]), key=len)
        # Three characters: "Jo" must not claim "Joanna" and "Jonas" both.
        if len(short) >= 3 and long.startswith(short):
            return 1
    return 0


def bind_attendees(
    attendees: Sequence[Attendee], participants: Sequence[Participant]
) -> dict[str, Participant]:
    """Which expected attendee is which person in the call, keyed by the attendee's id.

    An attendee whose id is already a real Discord id binds to themselves. The rest are
    matched by name, strongest first and one speaker each, so "Vitaly" and "Vitaly P"
    cannot both be bound to the one Vitaly who actually joined.
    """
    present = {p.discord_id: p for p in participants}
    bound: dict[str, Participant] = {}
    claimed: set[str] = set()
    for attendee in attendees:
        person = present.get(attendee.discord_id)
        if person is not None:
            bound[attendee.discord_id] = person
            claimed.add(person.discord_id)
    candidates = [
        (_match_score(attendee.name, person.name), i, j)
        for i, attendee in enumerate(attendees)
        if attendee.discord_id not in bound
        for j, person in enumerate(participants)
        if person.discord_id not in claimed
    ]
    for _score, i, j in sorted(
        (c for c in candidates if c[0] > 0), key=lambda c: (-c[0], c[1], c[2])
    ):
        attendee, person = attendees[i], participants[j]
        if attendee.discord_id in bound or person.discord_id in claimed:
            continue
        bound[attendee.discord_id] = person
        claimed.add(person.discord_id)
    return bound


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
        """Build this run's agenda from the saved roster and whoever is in the channel.

        A saved roster is an invitation list — only `packages/calendar` ever writes one
        (the console saves `attendees: []`), and it is the whole point of an invited
        meeting: the chair waits for those people and the room page marks who is not here
        yet. So it survives the start, rather than being replaced by whoever happens to be
        in voice at that second — a session started from a calendar invite normally starts
        with nobody in the channel at all.

        The one thing an invitation cannot carry is a Discord snowflake: it has an email,
        which `calendar` falls back to as the `discordId` when no operator mapped it. So a
        saved attendee is matched to a present speaker **by name** (`_match_score`) and
        takes that speaker's id, which is what makes them recognized as expected instead of
        joining as a fourth stranger. Whoever is present and matches nobody is appended;
        whoever is expected and absent is kept, unmatched, as someone still to arrive.

        With no saved roster this is exactly what it always was: the present people are the
        roster, and the first of them is the host.
        """
        saved = list(self.agenda.attendees)
        if not saved:
            attendees = [
                {"discordId": p.discord_id, "name": p.name, "role": "attendee"}
                for p in participants
            ]
            # The old "from voice" button made the first person the host. Preserve that
            # useful default without making operators manage the roster themselves.
            if attendees:
                attendees[0]["role"] = "host"
            return self._agenda_with(session_id, attendees, {})

        bound = bind_attendees(saved, participants)
        attendees = []
        for attendee in saved:
            person = bound.get(attendee.discord_id)
            attendees.append(
                {
                    # The name follows the speaker once they are in the room: their Discord
                    # profile is what the rest of the call sees them called.
                    "discordId": person.discord_id if person else attendee.discord_id,
                    "name": person.name if person else attendee.name,
                    "role": attendee.role,
                }
            )
        claimed = {p.discord_id for p in bound.values()}
        for person in participants:
            if person.discord_id not in claimed:
                attendees.append(
                    {"discordId": person.discord_id, "name": person.name, "role": "attendee"}
                )
        return self._agenda_with(
            session_id,
            attendees,
            {old: person.discord_id for old, person in bound.items() if old != person.discord_id},
        )

    def _agenda_with(
        self, session_id: str, attendees: list[dict[str, str]], rebound: dict[str, str]
    ) -> dict[str, Any]:
        """The saved agenda with this run's roster — and every `owner` / `mustHear` that
        named a rebound attendee following them to their Discord id, or the brain would
        chase an owner who, as far as it can see, is not in the call."""
        agenda = {
            "sessionId": session_id,
            **self.agenda.model_dump(by_alias=True, exclude={"attendees"}),
            "attendees": attendees,
        }
        if rebound:
            for topic in agenda["topics"]:
                topic["owner"] = rebound.get(topic["owner"], topic["owner"])
                topic["mustHear"] = [rebound.get(i, i) for i in topic["mustHear"]]
        return agenda
