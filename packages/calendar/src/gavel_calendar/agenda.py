"""Build the contract agenda (docs/CONTRACT.md §1) from a `ParsedInvite`.

Pure and offline: no network, no store, no ears. `session_id` and the
attendee email→discordId map are supplied by the caller because neither
comes from the .ics itself.
"""

from __future__ import annotations

from .ics_parser import ParsedInvite, TopicDraft
from .schema import DEFAULT_POLICY, ContractAgenda


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

    budgets = _budget_seconds(invite.topics, total_seconds)
    topics = []
    for i, (draft, budget) in enumerate(zip(invite.topics, budgets, strict=True), start=1):
        owner_id = by_name.get(draft.owner_name.strip().lower()) if draft.owner_name else None
        topics.append(
            {
                "id": f"t{i}",
                "title": draft.title,
                "goal": "",
                "budgetSeconds": budget,
                "owner": owner_id,
                "mustHear": [],
                "questions": [],
            }
        )

    agenda = {
        "sessionId": session_id,
        "purpose": _purpose(invite, invite.description),
        "totalSeconds": total_seconds,
        "attendees": attendees,
        "topics": topics,
        "policy": dict(DEFAULT_POLICY),
    }
    # Fails loudly, offline, before this ever reaches ears or the brain.
    ContractAgenda.model_validate(agenda)
    return agenda
