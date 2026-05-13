from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from calsync.models import Base, new_uuid, utcnow


class ProviderAccount(Base):
    __tablename__ = "provider_accounts"
    __table_args__ = (
        UniqueConstraint(
            "provider_type",
            "provider_account_id",
            name="uq_provider_accounts_provider_identity",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    provider_type: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
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

    calendars: Mapped[list["ProviderCalendar"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    sync_logs: Mapped[list["SyncLog"]] = relationship(back_populates="account")


class ProviderCalendar(Base):
    __tablename__ = "provider_calendars"
    __table_args__ = (
        UniqueConstraint(
            "provider_account_pk",
            "provider_calendar_id",
            name="uq_provider_calendars_provider_identity",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    provider_account_pk: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("provider_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_calendar_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    provider_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
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

    account: Mapped[ProviderAccount] = relationship(back_populates="calendars")


class SyncLog(Base):
    __tablename__ = "sync_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    provider_account_pk: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("provider_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider_type: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    events_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    events_upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    account: Mapped[ProviderAccount | None] = relationship(back_populates="sync_logs")
