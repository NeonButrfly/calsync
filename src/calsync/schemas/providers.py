from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DiscoveredCalendar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_id: str
    name: str
    timezone: str | None = None
    default_enabled: bool = True
    metadata: dict[str, object] | None = None


class NormalizedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_type: str
    provider_account_id: str
    provider_calendar_id: str
    provider_event_id: str
    title: str
    description: str | None = None
    location: str | None = None
    starts_at: datetime
    ends_at: datetime
    all_day: bool = False
    status: str = "confirmed"
    source_payload: dict[str, object] | None = None
