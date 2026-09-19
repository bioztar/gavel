"""The ears↔brain wire, docs/CONTRACT.md §2.

Contract frames first, additive ones after. Every ears→brain frame is stamped
with `at` (ISO 8601, UTC) and `atMs` (epoch milliseconds) when emitted.
Field names are camelCase on the wire, as in the contract.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel


class Frame(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, frozen=True)


class Participant(Frame):
    discord_id: str
    name: str


# --- ears → brain: contract ---------------------------------------------------


class Ready(Frame):
    type: Literal["ready"] = "ready"
    channel_id: str
    participants: list[Participant]


class Participants(Frame):
    type: Literal["participants"] = "participants"
    participants: list[Participant]


class SpeakingStart(Frame):
    type: Literal["speaking.start"] = "speaking.start"
    discord_id: str


class SpeakingEnd(Frame):
    type: Literal["speaking.end"] = "speaking.end"
    discord_id: str


class Transcript(Frame):
    type: Literal["transcript"] = "transcript"
    discord_id: str
    text: str
    started_at: str
    ended_at: str
    # additive
    name: str
    utterance_id: str
    seq: int
    final: bool
    turn_id: str | None
    confidence: float | None
    # Diarization label within this Discord user's audio ("0", "1", …) — several people
    # on one account (a room mic). None when the model gave none (HTTP mode).
    speaker: str | None = None


class Spoken(Frame):
    type: Literal["spoken"] = "spoken"
    utterance_id: str
    # additive: set when a `stop` cut it short, or playback failed.
    interrupted: bool = False
    error: str | None = None


# --- ears → brain: additive ----------------------------------------------------
# A turn is speaking.start/end smoothed over short pauses: one person holding the
# floor. turn.tick repeats while they keep it, so the brain never has to poll.


class TurnStart(Frame):
    type: Literal["turn.start"] = "turn.start"
    discord_id: str
    turn_id: str
    previous_discord_id: str | None


class TurnTick(Frame):
    type: Literal["turn.tick"] = "turn.tick"
    discord_id: str
    turn_id: str
    started_at: str
    duration_ms: int
    speaking_ms: int


class TurnEnd(Frame):
    type: Literal["turn.end"] = "turn.end"
    discord_id: str
    turn_id: str
    started_at: str
    ended_at: str
    duration_ms: int
    speaking_ms: int


# --- ears → brain: additive, sessions ------------------------------------------------
# A session is one run of a meeting, started from the console (or automatically on
# joining voice). `agenda` is the contract agenda as typed in the console, or null.


class SessionStarted(Frame):
    type: Literal["session.started"] = "session.started"
    session_id: str
    meeting_id: str | None
    title: str | None
    context: str | None
    agenda: dict[str, Any] | None


class SessionEnded(Frame):
    type: Literal["session.ended"] = "session.ended"
    session_id: str


EarsFrame = (
    Ready
    | SessionStarted
    | SessionEnded
    | Participants
    | SpeakingStart
    | SpeakingEnd
    | Transcript
    | Spoken
    | TurnStart
    | TurnTick
    | TurnEnd
)


# --- brain → ears ---------------------------------------------------------------


class Speak(Frame):
    type: Literal["speak"] = "speak"
    utterance_id: str
    audio: str  # base64
    format: str | None = None


class Stop(Frame):
    type: Literal["stop"] = "stop"


def parse_brain_frame(raw: str | bytes) -> Speak | Stop | None:
    """A frame from the brain, or None for anything malformed or unknown."""
    try:
        msg = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(msg, dict):
        return None
    try:
        if msg.get("type") == "speak":
            return Speak.model_validate(msg)
        if msg.get("type") == "stop":
            return Stop()
    except ValidationError:
        return None
    return None


def iso(ts: float) -> str:
    """Epoch seconds → ISO 8601 UTC with milliseconds."""
    return datetime.fromtimestamp(ts, UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def stamp(frame: EarsFrame, at: float | None = None) -> dict[str, Any]:
    """The wire dict for a frame: camelCase fields plus `at` / `atMs`."""
    at = time.time() if at is None else at
    body = frame.model_dump(by_alias=True)
    body["at"] = iso(at)
    body["atMs"] = int(at * 1000)
    return body
