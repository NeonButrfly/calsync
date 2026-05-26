from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from calsync.config import Settings
from calsync.crypto import encrypt_text
from calsync.models import Base, ProviderAccount, ProviderCalendar
from calsync.repos.providers import upsert_provider_account
from calsync.services.providers.icloud import (
    ICloudCalDAVError,
    ICloudCalDAVProviderAdapter,
    infer_icloud_account_capabilities,
)
from calsync.schemas.providers import WritableEventInput


ENCRYPTION_KEY = "phase3-icloud-provider-encryption-key"


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        public_base_url="http://localhost:3080",
        encryption_key=ENCRYPTION_KEY,
    )


@pytest.fixture()
def session(tmp_path: Path) -> Session:
    database_path = tmp_path / "icloud-provider.sqlite3"
    engine = create_engine(
        f"sqlite+pysqlite:///{database_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session


def test_icloud_discovery_maps_calendars(
    session: Session,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = _seed_icloud_account(session)

    responses = iter(
        [
            httpx.Response(
                207,
                text=_principal_discovery_xml(),
                request=httpx.Request("PROPFIND", "https://caldav.icloud.com/"),
            ),
            httpx.Response(
                207,
                text=_calendar_home_xml(),
                request=httpx.Request(
                    "PROPFIND",
                    "https://caldav.icloud.com/123/principal/",
                ),
            ),
            httpx.Response(
                207,
                text=_calendar_listing_xml(),
                request=httpx.Request(
                    "PROPFIND",
                    "https://caldav.icloud.com/123/calendars/",
                ),
            ),
        ]
    )

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def request(self, *args, **kwargs):
            return next(responses)

    monkeypatch.setattr(
        "calsync.services.providers.icloud._build_http_client",
        lambda: FakeClient(),
    )

    adapter = ICloudCalDAVProviderAdapter(settings=settings)
    calendars = adapter.discover_calendars(account)

    assert [calendar.external_id for calendar in calendars] == [
        "https://caldav.icloud.com/123/calendars/family/"
    ]
    assert calendars[0].name == "Family"
    assert calendars[0].timezone == "America/Anchorage"
    assert calendars[0].default_enabled is False


def test_icloud_connected_accounts_infer_write_capability_from_credentials(
    session: Session,
) -> None:
    account = _seed_icloud_account(session)
    account.provider_metadata = {"auth_status": "connected"}

    auth_mode, can_read, can_write = infer_icloud_account_capabilities(account)

    assert auth_mode == "caldav"
    assert can_read is True
    assert can_write is True


def test_icloud_fetch_events_parses_calendar_data(
    session: Session,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = _seed_icloud_account(session)
    calendar = ProviderCalendar(
        provider_account_pk=account.id,
        provider_calendar_id="https://caldav.icloud.com/123/calendars/family/",
        name="Family",
        enabled=True,
    )
    session.add(calendar)
    session.flush()

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def request(self, *args, **kwargs):
            return httpx.Response(
                207,
                text=_calendar_query_xml(),
                request=httpx.Request(
                    "REPORT",
                    "https://caldav.icloud.com/123/calendars/family/",
                ),
            )

    monkeypatch.setattr(
        "calsync.services.providers.icloud._build_http_client",
        lambda: FakeClient(),
    )

    adapter = ICloudCalDAVProviderAdapter(settings=settings)
    events = adapter.fetch_events(account, calendar)

    assert [event.provider_event_id for event in events] == ["family-1"]
    assert events[0].title == "Family Dinner"
    assert events[0].starts_at == datetime(2026, 5, 14, 2, 0, tzinfo=UTC)
    assert events[0].ends_at == datetime(2026, 5, 14, 4, 0, tzinfo=UTC)


def test_icloud_discovery_surfaces_auth_failures(
    session: Session,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = _seed_icloud_account(session)

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def request(self, *args, **kwargs):
            return httpx.Response(
                401,
                request=httpx.Request("PROPFIND", "https://caldav.icloud.com/"),
            )

    monkeypatch.setattr(
        "calsync.services.providers.icloud._build_http_client",
        lambda: FakeClient(),
    )

    adapter = ICloudCalDAVProviderAdapter(settings=settings)
    with pytest.raises(ICloudCalDAVError, match="app-specific password"):
        adapter.discover_calendars(account)


def test_icloud_create_event_puts_ics_resource(
    session: Session,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = _seed_icloud_account(session)
    calendar = ProviderCalendar(
        provider_account_pk=account.id,
        provider_calendar_id="https://caldav.icloud.com/123/calendars/family/",
        name="Family",
        enabled=True,
        provider_metadata={"can_write": True},
    )
    session.add(calendar)
    session.flush()

    captured: dict[str, object] = {}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def request(self, method, url, **kwargs):
            captured["method"] = method
            captured["url"] = url
            captured["headers"] = kwargs.get("headers", {})
            captured["content"] = kwargs.get("content", b"")
            return httpx.Response(
                201,
                headers={"ETag": '"etag-created"'},
                request=httpx.Request(method, url),
            )

    monkeypatch.setattr(
        "calsync.services.providers.icloud._build_http_client",
        lambda: FakeClient(),
    )
    monkeypatch.setattr(
        "calsync.services.providers.icloud.new_uuid",
        lambda: "family-created",
    )

    adapter = ICloudCalDAVProviderAdapter(settings=settings)
    event = adapter.create_event(
        account,
        calendar,
        WritableEventInput(
            title="Family Check-in",
            description="Created by CalSync",
            location="Home",
            starts_at=datetime(2026, 6, 2, 18, 0, tzinfo=UTC),
            ends_at=datetime(2026, 6, 2, 19, 0, tzinfo=UTC),
        ),
    )

    assert captured["method"] == "PUT"
    assert str(captured["url"]).endswith("/family-created.ics")
    assert b"SUMMARY:Family Check-in" in captured["content"]
    assert event.provider_event_id == "family-created"
    assert event.source_payload == {
        "href": "https://caldav.icloud.com/123/calendars/family/family-created.ics",
        "etag": '"etag-created"',
    }


def test_icloud_update_event_puts_existing_resource_with_etag(
    session: Session,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = _seed_icloud_account(session)
    calendar = ProviderCalendar(
        provider_account_pk=account.id,
        provider_calendar_id="https://caldav.icloud.com/123/calendars/family/",
        name="Family",
        enabled=True,
        provider_metadata={"can_write": True},
    )
    session.add(calendar)
    session.flush()

    captured: dict[str, object] = {}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def request(self, method, url, **kwargs):
            captured["method"] = method
            captured["url"] = url
            captured["headers"] = kwargs.get("headers", {})
            captured["content"] = kwargs.get("content", b"")
            return httpx.Response(
                204,
                headers={"ETag": '"etag-updated"'},
                request=httpx.Request(method, url),
            )

    monkeypatch.setattr(
        "calsync.services.providers.icloud._build_http_client",
        lambda: FakeClient(),
    )

    adapter = ICloudCalDAVProviderAdapter(settings=settings)
    event = adapter.update_event(
        account,
        calendar,
        "family-1",
        WritableEventInput(
            title="Updated Family Check-in",
            description="Updated by CalSync",
            location="Clinic",
            starts_at=datetime(2026, 6, 2, 20, 0, tzinfo=UTC),
            ends_at=datetime(2026, 6, 2, 21, 0, tzinfo=UTC),
        ),
        source_payload={
            "href": "https://caldav.icloud.com/123/calendars/family/family-1.ics",
            "etag": '"etag-old"',
        },
    )

    assert captured["method"] == "PUT"
    assert captured["headers"]["If-Match"] == '"etag-old"'
    assert b"SUMMARY:Updated Family Check-in" in captured["content"]
    assert event.provider_event_id == "family-1"
    assert event.source_payload == {
        "href": "https://caldav.icloud.com/123/calendars/family/family-1.ics",
        "etag": '"etag-updated"',
    }


def test_icloud_cancel_event_deletes_existing_resource(
    session: Session,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = _seed_icloud_account(session)
    calendar = ProviderCalendar(
        provider_account_pk=account.id,
        provider_calendar_id="https://caldav.icloud.com/123/calendars/family/",
        name="Family",
        enabled=True,
        provider_metadata={"can_write": True},
    )
    session.add(calendar)
    session.flush()

    captured: dict[str, object] = {}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def request(self, method, url, **kwargs):
            captured["method"] = method
            captured["url"] = url
            captured["headers"] = kwargs.get("headers", {})
            return httpx.Response(
                204,
                request=httpx.Request(method, url),
            )

    monkeypatch.setattr(
        "calsync.services.providers.icloud._build_http_client",
        lambda: FakeClient(),
    )

    adapter = ICloudCalDAVProviderAdapter(settings=settings)
    result = adapter.cancel_event(
        account,
        calendar,
        "family-1",
        source_payload={
            "href": "https://caldav.icloud.com/123/calendars/family/family-1.ics",
            "etag": '"etag-old"',
        },
    )

    assert result is None
    assert captured["method"] == "DELETE"
    assert captured["headers"]["If-Match"] == '"etag-old"'


def _seed_icloud_account(session: Session) -> ProviderAccount:
    account = upsert_provider_account(
        session,
        provider_type="icloud_caldav",
        provider_account_id="kay@icloud.com",
        display_name="Kay iCloud",
        provider_metadata={},
    )
    account.credential_secret_encrypted = encrypt_text(
        ENCRYPTION_KEY,
        "abcd-efgh-ijkl-mnop",
    )
    session.add(account)
    session.flush()
    return account


def _principal_discovery_xml() -> str:
    return """<?xml version="1.0" encoding="utf-8"?>
<D:multistatus xmlns:D="DAV:">
  <D:response>
    <D:href>/</D:href>
    <D:propstat>
      <D:prop>
        <D:current-user-principal>
          <D:href>/123/principal/</D:href>
        </D:current-user-principal>
      </D:prop>
      <D:status>HTTP/1.1 200 OK</D:status>
    </D:propstat>
  </D:response>
</D:multistatus>
"""


def _calendar_home_xml() -> str:
    return """<?xml version="1.0" encoding="utf-8"?>
<D:multistatus xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <D:response>
    <D:href>/123/principal/</D:href>
    <D:propstat>
      <D:prop>
        <C:calendar-home-set>
          <D:href>/123/calendars/</D:href>
        </C:calendar-home-set>
      </D:prop>
      <D:status>HTTP/1.1 200 OK</D:status>
    </D:propstat>
  </D:response>
</D:multistatus>
"""


def _calendar_listing_xml() -> str:
    return """<?xml version="1.0" encoding="utf-8"?>
<D:multistatus xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav" xmlns:CS="http://calendarserver.org/ns/">
  <D:response>
    <D:href>/123/calendars/family/</D:href>
    <D:propstat>
      <D:prop>
        <D:displayname>Family</D:displayname>
        <C:calendar-timezone>America/Anchorage</C:calendar-timezone>
        <D:resourcetype>
          <D:collection />
          <C:calendar />
        </D:resourcetype>
        <CS:getctag>tag-1</CS:getctag>
      </D:prop>
      <D:status>HTTP/1.1 200 OK</D:status>
    </D:propstat>
  </D:response>
</D:multistatus>
"""


def _calendar_query_xml() -> str:
    return """<?xml version="1.0" encoding="utf-8"?>
<D:multistatus xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <D:response>
    <D:href>/123/calendars/family/family-1.ics</D:href>
    <D:propstat>
      <D:prop>
        <D:getetag>"etag-1"</D:getetag>
        <C:calendar-data>BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:family-1
SUMMARY:Family Dinner
DTSTART:20260514T020000Z
DTEND:20260514T040000Z
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR</C:calendar-data>
      </D:prop>
      <D:status>HTTP/1.1 200 OK</D:status>
    </D:propstat>
  </D:response>
</D:multistatus>
"""
