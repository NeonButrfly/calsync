from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, synonym

from calsync.models import Base, new_uuid, utcnow


class AppleCalendarConnection(Base):
    __tablename__ = "apple_calendar_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    provider_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="icloud_caldav",
        server_default="icloud_caldav",
    )
    account_label: Mapped[str] = mapped_column(String(255), nullable=False)
    apple_username: Mapped[str] = mapped_column(String(255), nullable=False)
    primary_calendar_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    primary_calendar_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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

    account_identifier = synonym("apple_username")
    calendar_external_id = synonym("primary_calendar_url")
    calendar_display_name = synonym("primary_calendar_name")
