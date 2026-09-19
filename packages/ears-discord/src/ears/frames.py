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

from pydantic import BaseModel, ConfigDict, Field, ValidationError
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


# --- ears → brain: additive, moderation ---------------------------------------------
# The outcome of a brain `mute` / `unmute`, and of the auto-unmute ears runs itself.


class Moderation(Frame):
    type: Literal["moderation"] = "moderation"
    action: Literal["muted", "unmuted", "failed"]
    discord_id: str
    until: int | None = None  # epoch ms the mute lifts, on "muted"
    error: str | None = None


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
    | Moderation
)


# --- brain → ears ---------------------------------------------------------------


class Speak(Frame):
    type: Literal["speak"] = "speak"
    utterance_id: str
    audio: str  # base64
    # Additive: lets the operator console show exactly what the brain is saying.
    text: str | None = None
    format: str | None = None
    # additive: jump the queue, cut off non-priority playback, duck the room.
    priority: bool = False
    # additive: hold the line until nobody has spoken for `quiet_ms`; after `max_wait_ms`
    # in the queue it plays anyway. Unset: play as soon as it is first in line.
    quiet_ms: int | None = None
    max_wait_ms: int | None = None


# additive: a line streamed while it is synthesized. `speak.start` opens it (it queues and
# plays like `speak`), `speak.chunk`s carry raw PCM, `speak.end` closes it. One `spoken`
# per line, when playback of the whole line finishes.
class SpeakStart(Frame):
    type: Literal["speak.start"] = "speak.start"
    utterance_id: str
    text: str | None = None
    format: Literal["pcm_s16le"] = "pcm_s16le"
    sample_rate: Literal[48000] = 48000
    channels: Literal[1, 2] = 1
    priority: bool = False
    quiet_ms: int | None = None
    max_wait_ms: int | None = None


class SpeakChunk(Frame):
    type: Literal["speak.chunk"] = "speak.chunk"
    utterance_id: str
    audio: str  # base64 PCM


class SpeakEnd(Frame):
    type: Literal["speak.end"] = "speak.end"
    utterance_id: str
    error: str | None = None


class Stop(Frame):
    type: Literal["stop"] = "stop"


# additive: server-mute a participant. ears owns the unmute timer, so a brain that
# dies mid-mute never leaves anyone muted.
MAX_MUTE_SECONDS = 60


class Mute(Frame):
    type: Literal["mute"] = "mute"
    discord_id: str
    seconds: float = Field(gt=0)
    reason: str | None = None


class Unmute(Frame):
    type: Literal["unmute"] = "unmute"
    discord_id: str


BrainFrame = Speak | SpeakStart | SpeakChunk | SpeakEnd | Stop | Mute | Unmute
_BRAIN_FRAMES: dict[str, type[Frame]] = {
    "speak": Speak,
    "speak.start": SpeakStart,
    "speak.chunk": SpeakChunk,
    "speak.end": SpeakEnd,
    "mute": Mute,
    "unmute": Unmute,
}


def parse_brain_frame(raw: str | bytes) -> BrainFrame | None:
    """A frame from the brain, or None for anything malformed or unknown."""
    try:
        msg = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(msg, dict):
        return None
    kind = msg.get("type")
    if kind == "stop":
        return Stop()
    model = _BRAIN_FRAMES.get(kind) if isinstance(kind, str) else None
    if model is None:
        return None
    try:
        return model.model_validate(msg)  # type: ignore[return-value]
    except ValidationError:
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
