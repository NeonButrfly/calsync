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


from .admin import AdminUser
from .app_state import AppState
from .events import Event
from .provider_configurations import ProviderConfiguration
from .providers import ProviderAccount, ProviderCalendar, SyncLog
from .publishing import PublishedFeed

__all__ = [
    "AdminUser",
    "AppState",
    "Base",
    "Event",
    "ProviderConfiguration",
    "ProviderAccount",
    "ProviderCalendar",
    "PublishedFeed",
    "SyncLog",
    "new_uuid",
    "utcnow",
]
