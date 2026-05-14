from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from calsync.models import Base, utcnow


class ProviderConfiguration(Base):
    __tablename__ = "provider_configurations"

    provider_type: Mapped[str] = mapped_column(String(64), primary_key=True)
    public_config_json: Mapped[dict[str, object] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    secret_config_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
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
