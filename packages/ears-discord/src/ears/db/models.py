"""What ears records about a call.

`events` is the verbatim frame log — `export_replay` turns it into the brain's
replay.jsonl. The other tables are the same facts shaped for querying.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# JSONB on Postgres, JSON under SQLite in tests. BigInteger ids autoincrement on both.
JSONType = JSON().with_variant(JSONB, "postgresql")
BigId = BigInteger().with_variant(Integer, "sqlite")


class Base(DeclarativeBase):
    metadata: ClassVar[MetaData] = MetaData(naming_convention=NAMING_CONVENTION)


def _ts(**kw: Any) -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), **kw)


class Meeting(Base):
    """What a call is for, set up in the console. `agenda` is the contract agenda."""

    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    context: Mapped[str] = mapped_column(Text, default="")
    agenda: Mapped[dict[str, Any]] = mapped_column(JSONType)
    created_at: Mapped[datetime] = _ts(server_default=func.now())
    updated_at: Mapped[datetime] = _ts(server_default=func.now(), onupdate=func.now())


class DiscordGuild(Base):
    """The meeting voice channel selected for one Discord server."""

    __tablename__ = "discord_guilds"

    guild_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    channel_id: Mapped[str] = mapped_column(String(32))
    updated_at: Mapped[datetime] = _ts(server_default=func.now(), onupdate=func.now())


class DiscordStatus(Base):
    """How one Discord server wants the live meeting-status message (status_board.py)."""

    __tablename__ = "discord_status"

    guild_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    # A text channel; NULL posts in the meeting voice channel's own text chat.
    channel_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    updated_at: Mapped[datetime] = _ts(server_default=func.now(), onupdate=func.now())


class AppSetting(Base):
    """One operator-set value, live-editable from the console and outliving the
    process that was told about it.

    Deliberately key/value rather than a column per setting: these are console
    knobs, not domain facts, and a new one should not need a migration on demo
    day. `tts_voice` is the first — the voice Karen speaks in, which is one
    setting for two synthesizers (ears' say-box and the brain's chair) so the
    two can no longer drift apart.
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = _ts(server_default=func.now(), onupdate=func.now())


class CallSession(Base):
    """One run of a meeting: started from the console, or on joining voice."""

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    meeting_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("meetings.id", ondelete="SET NULL"), nullable=True
    )
    # Null until the bot is in a channel — a session can start before it joins.
    guild_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    channel_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    started_at: Mapped[datetime] = _ts(server_default=func.now())
    ended_at: Mapped[datetime | None] = _ts(nullable=True)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_session_id_id", "session_id", "id"),)

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(32))
    at: Mapped[datetime] = _ts()
    frame: Mapped[dict[str, Any]] = mapped_column(JSONType)


class Participant(Base):
    __tablename__ = "participants"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )
    discord_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    first_seen: Mapped[datetime] = _ts(server_default=func.now())
    last_seen: Mapped[datetime] = _ts(server_default=func.now())


class Turn(Base):
    __tablename__ = "turns"
    __table_args__ = (Index("ix_turns_session_id_started_at", "session_id", "started_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    discord_id: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = _ts()
    ended_at: Mapped[datetime] = _ts()
    duration_ms: Mapped[int] = mapped_column(Integer)
    speaking_ms: Mapped[int] = mapped_column(Integer)


class TranscriptChunk(Base):
    __tablename__ = "transcripts"
    __table_args__ = (
        UniqueConstraint("utterance_id", "seq"),
        Index("ix_transcripts_session_id_started_at", "session_id", "started_at"),
    )

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    discord_id: Mapped[str] = mapped_column(String(32))
    utterance_id: Mapped[uuid.UUID] = mapped_column()
    seq: Mapped[int] = mapped_column(Integer)
    turn_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime] = _ts()
    ended_at: Mapped[datetime] = _ts()
    text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    audio_ms: Mapped[int] = mapped_column(Integer)
    stt_ms: Mapped[int] = mapped_column(Integer)


# --- written by the brain, through the REST API ----------------------------------------
# ears is the one store: the brain keeps nothing on disk of its own.


class Memory(Base):
    """Something the chair remembers about a person — a parked off-agenda point, a note.

    Outlives the session: open items come back at the next meeting with that person.
    """

    __tablename__ = "memories"
    __table_args__ = (Index("ix_memories_discord_id_status", "discord_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    discord_id: Mapped[str] = mapped_column(String(32))
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    kind: Mapped[str] = mapped_column(String(16))  # "parked" | "note"
    summary: Mapped[str] = mapped_column(Text)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), default="open")  # "open" | "resolved"
    created_at: Mapped[datetime] = _ts(server_default=func.now())
    resolved_at: Mapped[datetime | None] = _ts(nullable=True)


class Intervention(Base):
    """One time the chair spoke up: why, to whom, what it said, how long it took."""

    __tablename__ = "interventions"
    __table_args__ = (Index("ix_interventions_session_id_at", "session_id", "at"),)

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    addressee_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    topic_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    line: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16))  # "llm" | "template" | "cache"
    actions: Mapped[list[str]] = mapped_column(JSONType)
    compose_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tts_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    at: Mapped[datetime] = _ts(server_default=func.now())


class LlmCall(Base):
    """Token and cost accounting for every model call the brain makes."""

    __tablename__ = "llm_calls"
    __table_args__ = (Index("ix_llm_calls_session_id_at", "session_id", "at"),)

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True
    )
    agent: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(128))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    at: Mapped[datetime] = _ts(server_default=func.now())
