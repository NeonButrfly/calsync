from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from calsync.models import Base, new_uuid, utcnow


EVENT_VISIBILITY_STATES = frozenset(
    {
        "active",
        "cancelled",
        "deleted_upstream",
        "hidden_duplicate",
        "stale_unverified",
    }
)


class UtcDateTime(TypeDecorator[datetime]):
    impl = DateTime
    cache_ok = True

    def process_bind_param(
        self,
        value: datetime | None,
        dialect: object,
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Expected timezone-aware datetime value")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(
        self,
        value: datetime | None,
        dialect: object,
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint(
            "provider_type",
            "provider_account_id",
            "provider_calendar_id",
            "provider_event_id",
            name="uq_events_provider_identity",
        ),
        CheckConstraint(
            "event_visibility_state IN ('active', 'cancelled', 'deleted_upstream', 'hidden_duplicate', 'stale_unverified')",
            name="ck_events_visibility_state",
        ),
        CheckConstraint(
            "event_visibility_state != 'active' OR removed_upstream_at IS NULL",
            name="ck_events_active_not_removed",
        ),
        CheckConstraint(
            "event_visibility_state != 'deleted_upstream' OR removed_upstream_at IS NOT NULL",
            name="ck_events_deleted_requires_removed_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    provider_type: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_calendar_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_account_pk: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("provider_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider_calendar_pk: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("provider_calendars.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="confirmed")
    event_visibility_state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default="active",
    )
    duplicate_visibility_override: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    last_seen_upstream_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime(),
        nullable=True,
        default=utcnow,
    )
    removed_upstream_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime(),
        nullable=True,
    )
    canonical_group_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("event_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )
