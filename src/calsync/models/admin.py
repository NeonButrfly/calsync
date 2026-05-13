from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from calsync.models import Base, new_uuid, utcnow


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    mfa_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    mfa_enrolled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recovery_codes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
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
