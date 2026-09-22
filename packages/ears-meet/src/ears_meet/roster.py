"""Who is in the call, from the tiles and the People panel — and the identity mapping.

Meet gives every participant a per-call id in `data-participant-id` (a `spaces/…/devices/…`
path). That string is the contract's `discordId` verbatim: it is the generic
participant-id field despite the name, the brain only ever compares it for equality, and
renaming it would break the contract. The display name rides in `name`, as on Discord.

The bot's own tile (`data-self-name`) is left out, as ears-discord leaves out bots: the
chair is not a participant of the meeting it chairs.

Pure: `update()` takes what the observer saw and returns whether the set changed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .frames import Participant


@dataclass(frozen=True)
class Tile:
    id: str
    name: str
    self: bool = False
    muted: bool = False

    @classmethod
    def from_event(cls, raw: dict[str, Any]) -> Tile:
        return cls(
            id=str(raw.get("id", "")),
            name=str(raw.get("name", "")).strip(),
            self=bool(raw.get("self", False)),
            muted=bool(raw.get("muted", False)),
        )


def participant_of(tile: Tile) -> Participant:
    return Participant(discord_id=tile.id, name=tile.name or tile.id)


@dataclass
class Roster:
    bot_name: str
    _people: dict[str, Participant] = field(default_factory=dict)
    _self_ids: set[str] = field(default_factory=set)

    def update(self, tiles: list[Tile]) -> tuple[bool, list[str], list[str]]:
        """Replace the roster with what is on stage. Returns (changed, joined ids, left ids).

        A tile with an empty name is Meet still laying out; it is kept (so speaking events
        for it are not dropped) and named by its id until the name arrives — the next
        `tiles` event with the name counts as a change and re-emits `participants`.
        """
        fresh: dict[str, Participant] = {}
        for t in tiles:
            if not t.id:
                continue
            if t.self or (self.bot_name and t.name == self.bot_name):
                self._self_ids.add(t.id)
                continue
            fresh[t.id] = participant_of(t)
        joined = [pid for pid in fresh if pid not in self._people]
        left = [pid for pid in self._people if pid not in fresh]
        changed = fresh != self._people
        self._people = fresh
        return changed, joined, left

    def is_self(self, participant_id: str) -> bool:
        return participant_id in self._self_ids

    def get(self, participant_id: str) -> Participant | None:
        return self._people.get(participant_id)

    def by_name(self, name: str) -> Participant | None:
        """Captions name people, tiles identify them — match the two, exact then loose."""
        want = name.strip().casefold()
        if not want:
            return None
        for p in self._people.values():
            if p.name.casefold() == want:
                return p
        for p in self._people.values():
            have = p.name.casefold()
            if have.startswith(want) or want.startswith(have):
                return p
        return None

    def participants(self) -> list[Participant]:
        return list(self._people.values())

    def ids(self) -> set[str]:
        return set(self._people)

    def __len__(self) -> int:
        return len(self._people)
