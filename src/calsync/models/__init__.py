from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import DeclarativeBase


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_uuid() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


from .apple_connection import AppleCalendarConnection
from .appointments import Appointment, AppointmentExternalLink
from .audit import AuditEntry
from .operator_settings import OperatorSetting

__all__ = [
    "AppleCalendarConnection",
    "Appointment",
    "AppointmentExternalLink",
    "AuditEntry",
    "OperatorSetting",
    "Base",
    "new_uuid",
    "utcnow",
]
