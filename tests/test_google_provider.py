from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from calsync.config import Settings
from calsync.crypto import decrypt_text, encrypt_text
from calsync.models import Base, ProviderAccount, ProviderCalendar
from calsync.repos.providers import upsert_provider_account
from calsync.services.providers.google import (
    ACCOUNT_DISCOVERY_SYNC_TOKEN_KEY,
    ACCOUNT_EMAIL_KEY,
    ACCOUNT_RECONNECT_REQUIRED_KEY,
    ACCOUNT_SCOPES_KEY,
    CALENDAR_EVENTS_SYNC_TOKEN_KEY,
    GoogleOAuthCompatibilityError,
    GoogleOAuthError,
    GoogleProviderAdapter,
    build_google_authorization_url,
    ensure_google_access_token,
    persist_google_oauth_account,
)


ENCRYPTION_KEY = "phase2-google-encryption-key"


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        public_base_url="https://calendar.example.com",
        encryption_key=ENCRYPTION_KEY,
        google_oauth_client_id="google-client-id",
        google_oauth_client_secret="google-client-secret",
    )


@pytest.fixture()
def session(tmp_path: Path) -> Session:
    database_path = tmp_path / "google-provider.sqlite3"
    engine = create_engine(
        f"sqlite+pysqlite:///{database_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session


def test_build_google_authorization_url_includes_required_query_fields(
    settings: Settings,
) -> None:
    authorization_url = build_google_authorization_url(
        "https://calendar.example.com/auth/google/callback",
        "state-123",
        settings=settings,
    )

    parsed = urlsplit(authorization_url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "accounts.google.com"
    assert query["client_id"] == ["google-client-id"]
    assert query["redirect_uri"] == [
        "https://calendar.example.com/auth/google/callback"
    ]
    assert query["response_type"] == ["code"]
    assert query["access_type"] == ["offline"]
    assert query["include_granted_scopes"] == ["true"]
    assert query["state"] == ["state-123"]
    assert query["scope"] == [
        "openid email profile https://www.googleapis.com/auth/calendar.readonly"
    ]


def test_build_google_authorization_url_rejects_raw_ip_callback(
    settings: Settings,
) -> None:
    with pytest.raises(GoogleOAuthCompatibilityError, match="raw IP addresses"):
        build_google_authorization_url(
            "http://192.168.50.232:3080/auth/google/callback",
            "state-123",
            settings=settings,
        )


def test_persist_google_oauth_account_requires_refresh_token_for_new_account(
    session: Session,
) -> None:
    with pytest.raises(GoogleOAuthError, match="refresh token"):
        persist_google_oauth_account(
            session,
            account=None,
            token_payload={"access_token": "access-token", "scope": "openid email"},
            user_info={"sub": "google-sub", "email": "owner@example.com"},
            encryption_key=ENCRYPTION_KEY,
        )


def test_persist_google_oauth_account_keeps_existing_refresh_token_when_missing(
    session: Session,
) -> None:
    existing_account = upsert_provider_account(
        session,
        provider_type="google",
        provider_account_id="google-sub",
        display_name="owner@example.com",
        provider_metadata={},
    )
    existing_account.refresh_token_encrypted = encrypt_text(
        ENCRYPTION_KEY,
        "old-refresh-token",
    )

    account = persist_google_oauth_account(
        session,
        account=existing_account,
        token_payload={
            "access_token": "new-access-token",
            "scope": "openid email profile https://www.googleapis.com/auth/calendar.readonly",
            "expires_in": 3600,
        },
        user_info={"sub": "google-sub", "email": "owner@example.com"},
        encryption_key=ENCRYPTION_KEY,
    )

    assert decrypt_text(ENCRYPTION_KEY, account.refresh_token_encrypted or "") == (
        "old-refresh-token"
    )
    assert decrypt_text(ENCRYPTION_KEY, account.access_token_encrypted or "") == (
        "new-access-token"
    )
    assert account.provider_metadata is not None
    assert account.provider_metadata[ACCOUNT_EMAIL_KEY] == "owner@example.com"
    assert account.provider_metadata[ACCOUNT_SCOPES_KEY] == [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/calendar.readonly",
    ]


def test_google_discovery_maps_calendars_and_stores_sync_token(
    session: Session,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = _seed_google_account(session)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/calendar/v3/users/me/calendarList"
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "primary",
                        "summary": "Primary",
                        "timeZone": "America/Anchorage",
                        "backgroundColor": "#123456",
                        "accessRole": "owner",
                        "hidden": False,
                        "selected": True,
                        "primary": True,
                    }
                ],
                "nextSyncToken": "calendar-sync-token",
            },
            request=request,
        )

    monkeypatch.setattr(
        "calsync.services.providers.google._build_http_client",
        lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )

    adapter = GoogleProviderAdapter(settings=settings)
    calendars = adapter.discover_calendars(account)

    assert [calendar.external_id for calendar in calendars] == ["primary"]
    assert calendars[0].default_enabled is False
    assert account.provider_metadata is not None
    assert account.provider_metadata[ACCOUNT_DISCOVERY_SYNC_TOKEN_KEY] == (
        "calendar-sync-token"
    )


def test_google_event_sync_stores_calendar_sync_token_and_normalizes_events(
    session: Session,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = _seed_google_account(session)
    calendar = ProviderCalendar(
        provider_account_pk=account.id,
        provider_calendar_id="primary",
        name="Primary",
        enabled=True,
        provider_metadata={},
    )
    session.add(calendar)
    session.flush()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/calendars/primary/events")
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "evt-1",
                        "summary": "Sprint Planning",
                        "description": "Discuss sprint work",
                        "location": "Conference Room",
                        "status": "confirmed",
                        "start": {"dateTime": "2026-05-13T16:00:00Z"},
                        "end": {"dateTime": "2026-05-13T17:00:00Z"},
                    },
                    {
                        "id": "evt-2",
                        "summary": "Holiday",
                        "status": "confirmed",
                        "start": {"date": "2026-05-15"},
                        "end": {"date": "2026-05-16"},
                    },
                ],
                "nextSyncToken": "events-sync-token",
            },
            request=request,
        )

    monkeypatch.setattr(
        "calsync.services.providers.google._build_http_client",
        lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )

    adapter = GoogleProviderAdapter(settings=settings)
    events = adapter.fetch_events(account, calendar)

    assert [event.provider_event_id for event in events] == ["evt-1", "evt-2"]
    assert events[0].title == "Sprint Planning"
    assert events[0].all_day is False
    assert events[0].starts_at == datetime(2026, 5, 13, 16, 0, tzinfo=UTC)
    assert events[1].all_day is True
    assert events[1].starts_at == datetime(2026, 5, 15, 0, 0, tzinfo=UTC)
    assert calendar.provider_metadata is not None
    assert calendar.provider_metadata[CALENDAR_EVENTS_SYNC_TOKEN_KEY] == (
        "events-sync-token"
    )


def test_google_event_sync_recovers_from_expired_sync_token(
    session: Session,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = _seed_google_account(session)
    calendar = ProviderCalendar(
        provider_account_pk=account.id,
        provider_calendar_id="primary",
        name="Primary",
        enabled=True,
        provider_metadata={CALENDAR_EVENTS_SYNC_TOKEN_KEY: "stale-token"},
    )
    session.add(calendar)
    session.flush()

    request_count = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        request_count["count"] += 1
        if request_count["count"] == 1:
            assert request.url.params["syncToken"] == "stale-token"
            return httpx.Response(410, json={"error": {"message": "sync token expired"}}, request=request)
        assert "syncToken" not in request.url.params
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "evt-1",
                        "summary": "Recovered Full Sync",
                        "status": "confirmed",
                        "start": {"dateTime": "2026-05-13T18:00:00Z"},
                        "end": {"dateTime": "2026-05-13T19:00:00Z"},
                    }
                ],
                "nextSyncToken": "fresh-token",
            },
            request=request,
        )

    monkeypatch.setattr(
        "calsync.services.providers.google._build_http_client",
        lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )

    adapter = GoogleProviderAdapter(settings=settings)
    events = adapter.fetch_events(account, calendar)

    assert request_count["count"] == 2
    assert [event.title for event in events] == ["Recovered Full Sync"]
    assert calendar.provider_metadata is not None
    assert calendar.provider_metadata[CALENDAR_EVENTS_SYNC_TOKEN_KEY] == "fresh-token"


def test_ensure_google_access_token_marks_reconnect_when_refresh_fails(
    session: Session,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = _seed_google_account(session)
    account.provider_metadata = {
        "google_access_token_expires_at": (
            datetime.now(UTC) - timedelta(minutes=10)
        ).isoformat()
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"error": "invalid_grant"},
            request=request,
        )

    monkeypatch.setattr(
        "calsync.services.providers.google._build_http_client",
        lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(GoogleOAuthError, match="revoked"):
        ensure_google_access_token(account, settings=settings, force_refresh=True)

    assert account.provider_metadata is not None
    assert account.provider_metadata[ACCOUNT_RECONNECT_REQUIRED_KEY] is True


def _seed_google_account(session: Session) -> ProviderAccount:
    account = upsert_provider_account(
        session,
        provider_type="google",
        provider_account_id="google-sub",
        display_name="owner@example.com",
        provider_metadata={
            "google_access_token_expires_at": (
                datetime.now(UTC) + timedelta(hours=1)
            ).isoformat()
        },
    )
    account.access_token_encrypted = encrypt_text(ENCRYPTION_KEY, "access-token")
    account.refresh_token_encrypted = encrypt_text(ENCRYPTION_KEY, "refresh-token")
    session.add(account)
    session.flush()
    return account
