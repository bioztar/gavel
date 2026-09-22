"""The contract agenda (docs/CONTRACT.md §1) for this run, from AGENDA_FILE and the room.

A saved agenda names attendees by whatever id its author had — an email from
packages/calendar, a placeholder typed by hand. Meet knows people by display name, so an
attendee is matched to a present participant **by name** and takes that participant's
Meet id; every `owner` / `mustHear` that named the old id follows. Whoever is present and
matches nobody is appended; whoever is expected and absent stays, unmatched, as someone
still to arrive. With no saved attendees, the present people are the roster and the first
of them is the host. This is ears-discord's `Meeting.agenda_for`, without Postgres.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .frames import Participant


def load_agenda(path: str) -> dict[str, Any] | None:
    if not path:
        return None
    raw = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return raw


def _norm(name: str) -> str:
    return " ".join(name.casefold().split())


def _match(attendee_name: str, participants: list[Participant]) -> Participant | None:
    want = _norm(attendee_name)
    if not want:
        return None
    for p in participants:
        if _norm(p.name) == want:
            return p
    for p in participants:
        have = _norm(p.name)
        if have.startswith(want) or want.startswith(have) or want.split()[0] == have.split()[0]:
            return p
    return None


def agenda_for(
    saved: dict[str, Any] | None, session_id: str, participants: list[Participant]
) -> dict[str, Any] | None:
    if saved is None:
        return None
    agenda = copy.deepcopy(saved)
    agenda["sessionId"] = session_id
    attendees: list[dict[str, Any]] = list(agenda.get("attendees") or [])
    if not attendees:
        out = [
            {"discordId": p.discord_id, "name": p.name, "role": "attendee"} for p in participants
        ]
        if out:
            out[0]["role"] = "host"
        agenda["attendees"] = out
        return agenda

    rebound: dict[str, str] = {}
    claimed: set[str] = set()
    result: list[dict[str, Any]] = []
    for att in attendees:
        person = _match(
            str(att.get("name", "")), [p for p in participants if p.discord_id not in claimed]
        )
        if person is not None:
            claimed.add(person.discord_id)
            old = str(att.get("discordId", ""))
            if old and old != person.discord_id:
                rebound[old] = person.discord_id
            result.append({**att, "discordId": person.discord_id, "name": person.name})
        else:
            result.append(dict(att))
    for p in participants:
        if p.discord_id not in claimed:
            result.append({"discordId": p.discord_id, "name": p.name, "role": "attendee"})
    agenda["attendees"] = result
    if rebound:
        for topic in agenda.get("topics") or []:
            if "owner" in topic:
                topic["owner"] = rebound.get(topic["owner"], topic["owner"])
            if "mustHear" in topic:
                topic["mustHear"] = [rebound.get(i, i) for i in topic["mustHear"]]
    return agenda
