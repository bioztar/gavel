"""Build the contract agenda (docs/CONTRACT.md §1) from a `ParsedInvite`.

Pure and offline: no network, no store, no ears. `session_id` and the
attendee email→discordId map are supplied by the caller because neither
comes from the .ics itself.
"""

from __future__ import annotations

from .ics_parser import ParsedInvite, TopicDraft
from .schema import EARS_DEFAULT_POLICY, ContractAgenda


def _purpose(invite: ParsedInvite, description: str) -> str:
    for line in description.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # First bulleted/numbered line means the description moved into topics.
        if stripped[0] in "-*•" or (
            stripped[0].isdigit() and ("." in stripped[:3] or ")" in stripped[:3])
        ):
            break
        return stripped
    return invite.title


def _attendee_id(email: str, attendee_map: dict[str, str]) -> str:
    # Unmapped: the email is a stable, unique fallback id — it just will not
    # match a real Discord speaker until an operator maps it. See settings.py.
    return attendee_map.get(email.lower(), email)


def _budget_seconds(topics: list[TopicDraft], total_seconds: int) -> list[int]:
    """Explicit durations win; topics with none split what is left evenly."""
    known = [t.budget_seconds for t in topics if t.budget_seconds is not None]
    remaining = max(total_seconds - sum(known), 0)
    unknown_count = sum(1 for t in topics if t.budget_seconds is None)
    if unknown_count == 0:
        return [t.budget_seconds for t in topics]  # type: ignore[misc]

    share = remaining // unknown_count
    out: list[int] = []
    given = 0
    for t in topics:
        if t.budget_seconds is not None:
            out.append(t.budget_seconds)
            continue
        given += 1
        # last one absorbs the remainder so the split fully uses `remaining`
        out.append(remaining - share * (unknown_count - 1) if given == unknown_count else share)
    return out


def build_agenda(
    invite: ParsedInvite,
    session_id: str,
    attendee_map: dict[str, str] | None = None,
    policy_overrides: dict[str, float | bool] | None = None,
) -> dict:
    attendee_map = attendee_map or {}
    total_seconds = invite.duration_seconds

    attendees = [
        {
            "discordId": _attendee_id(a.email, attendee_map),
            "name": a.name,
            "role": "host" if a.is_organizer else "attendee",
        }
        for a in invite.attendees
    ]
    by_name = {
        a.name.strip().lower(): att["discordId"]
        for a, att in zip(invite.attendees, attendees, strict=True)
    }

    # Whoever called the meeting is the standing best guess for anything the
    # brief did not say. An agenda with no owner and nobody who must be heard
    # gives the chair nothing to chase — she can't ask "who owns this?" or
    # notice that the one person who had to speak never did. A guessed host is
    # wrong far less often than empty is useless, and the compose form shows
    # the guess so it can be corrected before the invite goes out.
    host_id = next(
        (a["discordId"] for a in attendees if a["role"] == "host"),
        attendees[0]["discordId"] if attendees else None,
    )

    budgets = _budget_seconds(invite.topics, total_seconds)
    topics = []
    for i, (draft, budget) in enumerate(zip(invite.topics, budgets, strict=True), start=1):
        owner_id = by_name.get(draft.owner_name.strip().lower()) if draft.owner_name else None
        if owner_id is None:
            owner_id = host_id
        # Unmatched names are dropped rather than passed through — the brain
        # resolves mustHear against discordIds, not free text.
        must_hear_ids = [
            by_name[name.strip().lower()]
            for name in draft.must_hear_names
            if name.strip().lower() in by_name
        ]
        if not must_hear_ids and owner_id is not None:
            # The owner of a topic is the one person who has to be heard on it.
            must_hear_ids = [owner_id]
        topics.append(
            {
                "id": f"t{i}",
                "title": draft.title,
                "goal": draft.goal,
                "budgetSeconds": budget,
                "owner": owner_id,
                "mustHear": must_hear_ids,
                "questions": list(draft.questions),
            }
        )

    agenda = {
        "sessionId": session_id,
        "purpose": _purpose(invite, invite.description),
        "totalSeconds": total_seconds,
        "attendees": attendees,
        "topics": topics,
    }
    # Only present when the invite genuinely overrides something — see
    # schema.py. `ears`'s Agenda.policy does not deep-merge a supplied dict,
    # so we merge the override onto its full default table ourselves: the
    # wire payload always carries all ten keys, only the overridden ones
    # changed, never a partial dict that would drop the rest for this session.
    if policy_overrides:
        agenda["policy"] = {**EARS_DEFAULT_POLICY, **policy_overrides}
    # Fails loudly, offline, before this ever reaches ears or the brain.
    ContractAgenda.model_validate(agenda)
    return agenda


def attendee_name(agenda: dict, discord_id: str | None) -> str:
    """The inverse of the `by_name` lookup above: a built agenda's `discordId`
    back to its display name, for anywhere an id must read as a human (a join
    page, an .ics `DESCRIPTION`). An unmapped id — the email fallback from
    `_attendee_id` — is returned as-is rather than blanked out.
    """
    if discord_id is None:
        return ""
    for a in agenda["attendees"]:
        if a["discordId"] == discord_id:
            return str(a["name"])
    return discord_id
