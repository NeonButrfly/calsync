from datetime import UTC, datetime

import httpx

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


def test_list_events_parses_calendar_report(monkeypatch) -> None:
    config = AppleCalDAVConfig(
        account_label="Family",
        apple_username="family@example.com",
        app_specific_password="secret",
        primary_calendar_url="https://caldav.icloud.com/calendar/",
        primary_calendar_name="Family",
    )
    client = AppleCalDAVClient(config)

    xml_body = """<?xml version="1.0" encoding="utf-8"?>
<d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
  <d:response>
    <d:href>https://caldav.icloud.com/calendar/provider-existing.ics</d:href>
    <d:propstat>
      <d:prop>
        <d:getetag>"etag-existing"</d:getetag>
        <c:calendar-data>BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:provider-existing
SUMMARY:Existing School Visit
DTSTART:20260610T170000Z
DTEND:20260610T174500Z
LOCATION:School office
DESCRIPTION:Already on the family calendar
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR</c:calendar-data>
      </d:prop>
    </d:propstat>
  </d:response>
</d:multistatus>
"""

    def fake_request(method: str, url: str, **_: object) -> httpx.Response:
        assert method == "REPORT"
        assert url == "https://caldav.icloud.com/calendar/"
        return httpx.Response(207, text=xml_body)

    monkeypatch.setattr("calsync.services.apple_caldav.httpx.request", fake_request)

    events = client.list_events(
        starts_at=datetime(2026, 6, 10, 0, 0, tzinfo=UTC),
        ends_at=datetime(2026, 6, 10, 23, 59, tzinfo=UTC),
    )

    assert len(events) == 1
    assert events[0].provider_event_id == "provider-existing"
    assert events[0].title == "Existing School Visit"
    assert events[0].location == "School office"
