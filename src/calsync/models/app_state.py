from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from calsync.models import Base, utcnow


class AppState(Base):
    __tablename__ = "app_state"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )
