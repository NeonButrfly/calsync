from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from calsync.models import Base, new_uuid
from calsync.models.events import UtcDateTime


class EventGroup(Base):
    __tablename__ = "event_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    display_title: Mapped[str] = mapped_column(String(255), nullable=False)
    preferred_starts_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    preferred_ends_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    preferred_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preferred_event_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
    )
