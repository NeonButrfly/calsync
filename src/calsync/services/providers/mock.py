from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from calsync.models import ProviderAccount, ProviderCalendar
from calsync.schemas.providers import DiscoveredCalendar, NormalizedEvent


ANCHORAGE = ZoneInfo("America/Anchorage")


class MockProviderAdapter:
    provider_type = "mock"

    def discover_calendars(
        self,
        account: ProviderAccount,
    ) -> list[DiscoveredCalendar]:
        return [
            DiscoveredCalendar(
                external_id="home",
                name="Home",
                timezone="America/Anchorage",
                metadata={"account_id": account.provider_account_id, "kind": "household"},
            ),
            DiscoveredCalendar(
                external_id="work",
                name="Work",
                timezone="America/Anchorage",
                metadata={"account_id": account.provider_account_id, "kind": "office"},
            ),
            DiscoveredCalendar(
                external_id="shared",
                name="Shared",
                timezone="UTC",
                metadata={"account_id": account.provider_account_id, "kind": "group"},
            ),
        ]

    def fetch_events(
        self,
        account: ProviderAccount,
        calendar: ProviderCalendar,
    ) -> list[NormalizedEvent]:
        event_specs = {
            "home": [
                {
                    "provider_event_id": "home-standup",
                    "title": "Morning Standup",
                    "description": "Daily household check-in.",
                    "location": "Kitchen table",
                    "starts_at": datetime(2026, 5, 13, 8, 0, tzinfo=ANCHORAGE),
                    "ends_at": datetime(2026, 5, 13, 8, 15, tzinfo=ANCHORAGE),
                    "source_payload": {"calendar": "home", "series": "daily-standup"},
                },
                {
                    "provider_event_id": "home-dinner",
                    "title": "Family Dinner",
                    "description": "Dinner with the whole household.",
                    "location": "Dining room",
                    "starts_at": datetime(2026, 5, 13, 18, 30, tzinfo=ANCHORAGE),
                    "ends_at": datetime(2026, 5, 13, 20, 0, tzinfo=ANCHORAGE),
                    "source_payload": {"calendar": "home", "series": None},
                },
            ],
            "work": [
                {
                    "provider_event_id": "work-planning",
                    "title": "Sprint Planning",
                    "description": "Plan the upcoming sprint.",
                    "location": "Conference Room A",
                    "starts_at": datetime(2026, 5, 14, 9, 0, tzinfo=ANCHORAGE),
                    "ends_at": datetime(2026, 5, 14, 10, 0, tzinfo=ANCHORAGE),
                    "source_payload": {"calendar": "work", "series": "weekly-planning"},
                },
                {
                    "provider_event_id": "work-demo",
                    "title": "Demo Review",
                    "description": "Review the current product demo.",
                    "location": "Zoom",
                    "starts_at": datetime(2026, 5, 15, 14, 0, tzinfo=ANCHORAGE),
                    "ends_at": datetime(2026, 5, 15, 15, 0, tzinfo=ANCHORAGE),
                    "source_payload": {"calendar": "work", "series": None},
                },
            ],
            "shared": [
                {
                    "provider_event_id": "shared-game-night",
                    "title": "Community Game Night",
                    "description": "Open invite for friends and family.",
                    "location": "Online",
                    "starts_at": datetime(2026, 5, 16, 2, 0, tzinfo=UTC),
                    "ends_at": datetime(2026, 5, 16, 4, 0, tzinfo=UTC),
                    "source_payload": {"calendar": "shared", "series": "monthly-game-night"},
                },
            ],
        }

        return [
            NormalizedEvent(
                provider_type=self.provider_type,
                provider_account_id=account.provider_account_id,
                provider_calendar_id=calendar.provider_calendar_id,
                status="confirmed",
                all_day=False,
                **spec,
            )
            for spec in event_specs.get(calendar.provider_calendar_id, [])
        ]
