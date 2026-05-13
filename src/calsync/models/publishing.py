from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from calsync.models import Base, new_uuid, utcnow


class PublishedFeed(Base):
    __tablename__ = "published_feeds"
    __table_args__ = (
        UniqueConstraint("scope_type", "scope_key", name="uq_published_feeds_scope"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(255), nullable=False)
    token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    feed_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )
    rotated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
