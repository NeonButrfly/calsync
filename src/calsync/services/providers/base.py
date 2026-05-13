from __future__ import annotations

from typing import Protocol

from calsync.models import ProviderAccount, ProviderCalendar
from calsync.schemas.providers import DiscoveredCalendar, NormalizedEvent


class ProviderAdapter(Protocol):
    provider_type: str

    def discover_calendars(
        self,
        account: ProviderAccount,
    ) -> list[DiscoveredCalendar]: ...

    def fetch_events(
        self,
        account: ProviderAccount,
        calendar: ProviderCalendar,
    ) -> list[NormalizedEvent]: ...


def get_provider_adapter(provider_type: str) -> ProviderAdapter:
    if provider_type == "mock":
        from calsync.services.providers.mock import MockProviderAdapter

        return MockProviderAdapter()
    raise LookupError(f"Unsupported provider type: {provider_type}")
