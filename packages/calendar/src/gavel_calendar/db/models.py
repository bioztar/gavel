"""The one table this service owns, in the same Postgres as everything else.

`packages/ears-discord` owns the database and every table in it that describes a
*call*. This is not one of those: an invite exists long before a session does,
and may never become one. So calendar keeps its own table, with its own Alembic
lineage and its own `alembic_version_calendar` (see `alembic/env.py`), and never
touches ears' schema — the working agreement's directory ownership is absolute,
and that has to hold for the schema too, not just the source.

One database, two owners, no shared tables. `calendar_invites` is the durable
copy of `store.InviteRecord`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import JSON, Boolean, DateTime, MetaData, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# JSONB on Postgres, JSON under SQLite in tests — same trick as ears' models.
JSONType = JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    metadata: ClassVar[MetaData] = MetaData(naming_convention=NAMING_CONVENTION)


class Invite(Base):
    """One invite: what `GET /m/{id}` renders, before, during and after.

    `started` plus the two ears ids are the record of a session having been
    started for this invite. They are what stops the scheduler starting a
    *second* one after a restart — in-process state cannot do that job.
    """

    __tablename__ = "calendar_invites"

    # Our own id, not ears' — 12 hex chars from `uuid4` (compose) or a sha256
    # of (feed, occurrence UID) (feeds). It is what the public /m/ link carries.
    session_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    # An .ics SUMMARY has no length limit worth trusting; never truncate a title.
    title: Mapped[str] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    agenda: Mapped[dict[str, Any]] = mapped_column(JSONType)
    context: Mapped[str] = mapped_column(Text, default="")
    started: Mapped[bool] = mapped_column(Boolean, default=False)
    ears_meeting_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ears_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # The last brain state seen for this meeting. The brain keeps one live
    # session in memory and drops it when the next starts, so this banked copy
    # is the only thing the report can be rendered from afterwards.
    last_state: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
