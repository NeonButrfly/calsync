from datetime import UTC, datetime

from calsync.services.apple_caldav import (
    AppleCalDAVClient,
    AppleCalDAVConfig,
    build_event_payload,
)


def test_build_event_payload_uses_uid_and_summary() -> None:
    payload = build_event_payload(
        uid="appt-123",
        title="Dentist",
        starts_at=datetime(2026, 6, 1, 18, 0, tzinfo=UTC),
        ends_at=datetime(2026, 6, 1, 19, 0, tzinfo=UTC),
        all_day=False,
        location="Clinic",
        notes="Bring insurance card",
    )

    text = payload.decode("utf-8")
    assert "UID:appt-123" in text
    assert "SUMMARY:Dentist" in text
    assert "LOCATION:Clinic" in text


def test_config_requires_primary_calendar_url() -> None:
    config = AppleCalDAVConfig(
        account_label="Family",
        apple_username="family@example.com",
        app_specific_password="secret",
        primary_calendar_url="https://caldav.icloud.com/calendar/",
        primary_calendar_name="Family",
    )

    assert config.primary_calendar_name == "Family"


def test_resource_href_uses_calendar_root() -> None:
    config = AppleCalDAVConfig(
        account_label="Family",
        apple_username="family@example.com",
        app_specific_password="secret",
        primary_calendar_url="https://caldav.icloud.com/calendar/",
        primary_calendar_name="Family",
    )

    client = AppleCalDAVClient(config)

    assert (
        client.resource_href("appt-123")
        == "https://caldav.icloud.com/calendar/appt-123.ics"
    )
