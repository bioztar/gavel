"""Who ends up on a composed invite, and the one rule that governs it: an
address reaches the invite only if the host wrote it. The model reads the
guest list off the brief (`llm.BriefInvitee`), but a model can also complete
`artem@` into someone's real mailbox, so every address it returns is checked
against the text the host actually typed — brief, agenda box, attendees field —
and anything not found there is stripped and shown as such on the confirm page.
Nothing in this module talks to the network or the store.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from email.utils import getaddresses
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.datastructures import FormData

    from .llm import BriefInvitee

_EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+\-']+@[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}"
)


@dataclass(frozen=True)
class Invitee:
    name: str
    email: str


@dataclass
class Resolution:
    invitees: list[Invitee]
    # Addresses the model returned that the host never typed. Kept for the
    # confirm page, so a dropped guest is a visible line, never a silent one.
    stripped: list[str] = field(default_factory=list)


def display_name(email: str) -> str:
    """Local part as a name, same convention as `ics_parser._attendee_name`."""
    return email.split("@")[0].replace(".", " ").replace("_", " ").title()


def is_address(value: str) -> bool:
    return _EMAIL_RE.fullmatch(value.strip()) is not None


def addresses_in(text: str) -> set[str]:
    """Every address literally present in what the host typed, lowercased."""
    return {m.group(0).lower() for m in _EMAIL_RE.finditer(text)}


def from_field(raw: str) -> list[Invitee]:
    """`"Name <email>, email2, ..."` (RFC 5322 address list) -> invitees."""
    out: list[Invitee] = []
    for name, email in getaddresses([raw]):
        email = email.strip().lower()
        if not email or not is_address(email):
            continue
        out.append(Invitee(name=name.strip() or display_name(email), email=email))
    return out


def _dedupe(candidates: list[Invitee]) -> list[Invitee]:
    seen: set[str] = set()
    out: list[Invitee] = []
    for invitee in candidates:
        if invitee.email in seen:
            continue
        seen.add(invitee.email)
        out.append(invitee)
    return out


def resolve(
    inferred: list[BriefInvitee],
    *,
    source: str,
    explicit: list[Invitee],
    host: Invitee | None = None,
) -> Resolution:
    """The invite's guest list: the host, whoever was typed into the attendees
    field, then whoever the model read off the brief — in that order, one line
    per address, first spelling of a name wins.

    `source` is the host's own text (brief plus any typed agenda). An inferred
    address is kept only if it appears there verbatim (case-insensitively) or
    in the explicit field; anything else is a hallucination and is stripped.
    """
    allowed = addresses_in(source) | {i.email for i in explicit} | ({host.email} if host else set())
    kept: list[Invitee] = []
    stripped: list[str] = []
    for candidate in inferred:
        email = candidate.email.strip().lower()
        if not email:
            continue
        if not is_address(email) or email not in allowed:
            stripped.append(email)
            continue
        kept.append(Invitee(name=candidate.name.strip() or display_name(email), email=email))

    ordered = ([host] if host else []) + explicit + kept
    return Resolution(invitees=_dedupe(ordered), stripped=sorted(set(stripped)))


def from_form(form: FormData) -> list[Invitee]:
    """The confirm page's invitee rows, as edited. Blank rows and rows whose
    address is not one are dropped; the rest are de-duplicated on the address.
    """
    raw_count = form.get("invitees_count")
    count = int(raw_count) if isinstance(raw_count, str) and raw_count.isdigit() else 0
    out: list[Invitee] = []
    for i in range(count):
        email_value = form.get(f"invitee_email_{i}")
        name_value = form.get(f"invitee_name_{i}")
        email = email_value.strip().lower() if isinstance(email_value, str) else ""
        if not email or not is_address(email):
            continue
        name = name_value.strip() if isinstance(name_value, str) else ""
        out.append(Invitee(name=name or display_name(email), email=email))
    return _dedupe(out)


def as_field(invitees: list[Invitee]) -> str:
    return ", ".join(f"{i.name} <{i.email}>" for i in invitees)
