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
from .events import EVENT_VISIBILITY_STATES, Event
from .provider_configurations import ProviderConfiguration
from .providers import ProviderAccount, ProviderCalendar, SyncLog
from .publishing import PublishedFeed
from .reconciliation import EventGroup
from .scheduling import (
    CALENDAR_ROLE_AVAILABILITY_ONLY,
    CALENDAR_ROLE_CONFLICT_ONLY,
    CALENDAR_ROLE_HIDDEN,
    CALENDAR_ROLE_PERSONAL_REFERENCE,
    CALENDAR_ROLE_WRITABLE_BOOKING_TARGET,
    CALENDAR_ROLES,
)

__all__ = [
    "AdminUser",
    "AppState",
    "Base",
    "CALENDAR_ROLE_AVAILABILITY_ONLY",
    "CALENDAR_ROLE_CONFLICT_ONLY",
    "CALENDAR_ROLE_HIDDEN",
    "CALENDAR_ROLE_PERSONAL_REFERENCE",
    "CALENDAR_ROLE_WRITABLE_BOOKING_TARGET",
    "CALENDAR_ROLES",
    "Event",
    "EVENT_VISIBILITY_STATES",
    "EventGroup",
    "ProviderConfiguration",
    "ProviderAccount",
    "ProviderCalendar",
    "PublishedFeed",
    "SyncLog",
    "new_uuid",
    "utcnow",
]
