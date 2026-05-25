from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from calsync.config import Settings
from calsync.crypto import encrypt_text
from calsync.models import Base, ProviderAccount, ProviderCalendar
from calsync.repos.provider_config import get_provider_configuration
from calsync.services.provider_config import (
    DEFAULT_MICROSOFT_OAUTH_SCOPES,
    resolve_microsoft_oauth_configuration,
    save_microsoft_oauth_configuration,
)
from calsync.services.providers.base import get_provider_adapter
from calsync.services.providers.microsoft import (
    ACCOUNT_AUTH_STATUS_KEY,
    ACCOUNT_RECONNECT_REQUIRED_KEY,
    MicrosoftOAuthError,
    MicrosoftProviderAdapter,
    build_microsoft_authorization_url,
    connect_microsoft_account_from_callback,
    ensure_microsoft_access_token,
    infer_microsoft_account_capabilities,
)


ENCRYPTION_KEY = "phase1-microsoft-provider-encryption-key"
SESSION_SECRET = "phase1-microsoft-provider-session-secret"


def test_microsoft_provider_configuration_round_trip(tmp_path: Path) -> None:
    with _build_session(tmp_path) as session:
        save_microsoft_oauth_configuration(
            session,
            client_id="microsoft-client-id",
            client_secret="microsoft-client-secret",
            scopes="openid,offline_access,Calendars.ReadWrite",
            encryption_key=ENCRYPTION_KEY,
        )
        session.commit()

        configuration = resolve_microsoft_oauth_configuration(
            session,
            encryption_key=ENCRYPTION_KEY,
        )
        stored_configuration = get_provider_configuration(session, "microsoft")

    assert configuration is not None
    assert configuration.client_id == "microsoft-client-id"
    assert configuration.scopes == (
        "openid",
        "offline_access",
        "Calendars.ReadWrite",
    )
    assert stored_configuration is not None
    assert stored_configuration.provider_type == "microsoft"


def test_microsoft_provider_scaffold_reports_provider_identity() -> None:
    adapter = MicrosoftProviderAdapter()

    assert adapter.provider_type == "microsoft"
    assert adapter.auth_mode == "oauth"


def test_provider_factory_resolves_microsoft_adapter() -> None:
    adapter = get_provider_adapter("microsoft")

    assert isinstance(adapter, MicrosoftProviderAdapter)
    assert adapter.provider_type == "microsoft"


def test_microsoft_provider_configuration_round_trip_supports_space_delimited_scopes(
    tmp_path: Path,
) -> None:
    account = ProviderAccount(
        provider_type="microsoft",
        provider_account_id="microsoft-user",
        provider_metadata={},
    )

    with _build_session(tmp_path) as session:
        save_microsoft_oauth_configuration(
            session,
            client_id="microsoft-client-id",
            client_secret="microsoft-client-secret",
            scopes=(
                "openid profile offline_access "
                "https://graph.microsoft.com/Calendars.ReadWrite"
            ),
            encryption_key=ENCRYPTION_KEY,
        )
        session.commit()

        configuration = resolve_microsoft_oauth_configuration(
            session,
            encryption_key=ENCRYPTION_KEY,
        )

    assert configuration is not None
    assert configuration.scopes == (
        "openid",
        "profile",
        "offline_access",
        "https://graph.microsoft.com/Calendars.ReadWrite",
    )

    account.provider_metadata = {
        "microsoft_scopes": list(configuration.scopes),
    }
    assert infer_microsoft_account_capabilities(account) == ("oauth", True, True)


def test_build_microsoft_authorization_url_uses_callback_and_scopes(
    tmp_path: Path,
) -> None:
    settings = _build_settings(tmp_path)
    with _build_session(tmp_path) as session:
        save_microsoft_oauth_configuration(
            session,
            client_id="microsoft-client-id",
            client_secret="microsoft-client-secret",
            scopes="openid offline_access User.Read Calendars.Read",
            encryption_key=ENCRYPTION_KEY,
        )
        session.commit()

        url = build_microsoft_authorization_url(
            "http://localhost:3080/auth/microsoft/callback",
            "microsoft-state",
            session=session,
            settings=settings,
        )

    parsed = urlsplit(url)
    query = parse_qs(parsed.query)
    assert parsed.netloc == "login.microsoftonline.com"
    assert query["redirect_uri"] == ["http://localhost:3080/auth/microsoft/callback"]
    assert query["state"] == ["microsoft-state"]
    assert query["scope"] == ["openid offline_access User.Read Calendars.Read"]


def test_connect_microsoft_account_from_callback_persists_tokens_and_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = _build_settings(tmp_path)
    with _build_session(tmp_path) as session:
        save_microsoft_oauth_configuration(
            session,
            client_id="microsoft-client-id",
            client_secret="microsoft-client-secret",
            scopes="openid offline_access User.Read Calendars.Read",
            encryption_key=ENCRYPTION_KEY,
        )
        session.commit()

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url == httpx.URL(
                "https://login.microsoftonline.com/common/oauth2/v2.0/token"
            ):
                return httpx.Response(
                    200,
                    json={
                        "access_token": "microsoft-access-token",
                        "refresh_token": "microsoft-refresh-token",
                        "expires_in": 3600,
                        "scope": "openid offline_access User.Read Calendars.Read",
                    },
                    request=request,
                )
            if request.url == httpx.URL("https://graph.microsoft.com/v1.0/me"):
                return httpx.Response(
                    200,
                    json={
                        "id": "microsoft-sub",
                        "mail": "owner@example.com",
                        "displayName": "Owner Example",
                        "userPrincipalName": "owner@example.com",
                    },
                    request=request,
                )
            raise AssertionError(f"Unexpected request: {request.method} {request.url}")

        monkeypatch.setattr(
            "calsync.services.providers.microsoft._build_http_client",
            lambda: httpx.Client(transport=httpx.MockTransport(handler)),
        )

        account = connect_microsoft_account_from_callback(
            session,
            code="microsoft-code",
            callback_base_url="http://localhost:3080",
            settings=settings,
            encryption_key=ENCRYPTION_KEY,
        )

    assert account.provider_type == "microsoft"
    assert account.display_name == "owner@example.com"
    assert account.provider_metadata is not None
    assert account.provider_metadata[ACCOUNT_AUTH_STATUS_KEY] == "connected"
    assert account.provider_metadata["microsoft_email"] == "owner@example.com"
    assert account.provider_metadata["microsoft_subject"] == "microsoft-sub"


def test_microsoft_refresh_marks_reconnect_required_on_invalid_grant(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = _build_settings(tmp_path)
    with _build_session(tmp_path) as session:
        save_microsoft_oauth_configuration(
            session,
            client_id="microsoft-client-id",
            client_secret="microsoft-client-secret",
            scopes="openid offline_access User.Read Calendars.Read",
            encryption_key=ENCRYPTION_KEY,
        )
        session.commit()

        account = ProviderAccount(
            provider_type="microsoft",
            provider_account_id="microsoft-sub",
            access_token_encrypted=None,
            refresh_token_encrypted=encrypt_text(ENCRYPTION_KEY, "refresh-token"),
        )
        session.add(account)
        session.flush()

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url == httpx.URL(
                "https://login.microsoftonline.com/common/oauth2/v2.0/token"
            ):
                return httpx.Response(
                    400,
                    json={"error_description": "invalid_grant: token revoked"},
                    request=request,
                )
            raise AssertionError(f"Unexpected request: {request.method} {request.url}")

        monkeypatch.setattr(
            "calsync.services.providers.microsoft._build_http_client",
            lambda: httpx.Client(transport=httpx.MockTransport(handler)),
        )

        with pytest.raises(MicrosoftOAuthError):
            ensure_microsoft_access_token(account, session=session, settings=settings)

    assert account.provider_metadata is not None
    assert account.provider_metadata[ACCOUNT_RECONNECT_REQUIRED_KEY] is True


def test_microsoft_discovery_maps_calendars(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = _build_settings(tmp_path)
    with _build_session(tmp_path) as session:
        account = _seed_connected_account(session)

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url == httpx.URL("https://graph.microsoft.com/v1.0/me/calendars"):
                return httpx.Response(
                    200,
                    json={
                        "value": [
                            {
                                "id": "primary",
                                "name": "Calendar",
                                "canEdit": True,
                                "isDefaultCalendar": True,
                            }
                        ]
                    },
                    request=request,
                )
            raise AssertionError(f"Unexpected request: {request.method} {request.url}")

        monkeypatch.setattr(
            "calsync.services.providers.microsoft._build_http_client",
            lambda: httpx.Client(transport=httpx.MockTransport(handler)),
        )

        adapter = MicrosoftProviderAdapter(session=session, settings=settings)
        calendars = adapter.discover_calendars(account)

    assert len(calendars) == 1
    assert calendars[0].external_id == "primary"
    assert calendars[0].default_enabled is False
    assert calendars[0].metadata is not None
    assert calendars[0].metadata["can_write"] is True


def test_microsoft_fetch_events_normalizes_graph_events(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = _build_settings(tmp_path)
    with _build_session(tmp_path) as session:
        account = _seed_connected_account(session)
        adapter = MicrosoftProviderAdapter(session=session, settings=settings)
        calendar_obj = ProviderCalendar(
            provider_account_pk=account.id,
            provider_calendar_id="primary",
            name="Calendar",
            enabled=True,
        )
        session.add(calendar_obj)
        session.commit()

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url == httpx.URL(
                "https://graph.microsoft.com/v1.0/me/calendars/primary/events"
            ):
                return httpx.Response(
                    200,
                    json={
                        "value": [
                            {
                                "id": "evt-1",
                                "subject": "Checkup",
                                "bodyPreview": "Bring paperwork",
                                "isAllDay": False,
                                "isCancelled": False,
                                "start": {"dateTime": "2026-05-26T15:00:00Z", "timeZone": "UTC"},
                                "end": {"dateTime": "2026-05-26T16:00:00Z", "timeZone": "UTC"},
                                "location": {"displayName": "Clinic"},
                            }
                        ]
                    },
                    request=request,
                )
            raise AssertionError(f"Unexpected request: {request.method} {request.url}")

        monkeypatch.setattr(
            "calsync.services.providers.microsoft._build_http_client",
            lambda: httpx.Client(transport=httpx.MockTransport(handler)),
        )

        events = adapter.fetch_events(account, calendar_obj)

    assert len(events) == 1
    assert events[0].provider_type == "microsoft"
    assert events[0].provider_event_id == "evt-1"
    assert events[0].title == "Checkup"
    assert events[0].location == "Clinic"


def test_microsoft_provider_configuration_defaults_blank_scopes(
    tmp_path: Path,
) -> None:
    with _build_session(tmp_path) as session:
        save_microsoft_oauth_configuration(
            session,
            client_id="microsoft-client-id",
            client_secret="microsoft-client-secret",
            scopes="   ",
            encryption_key=ENCRYPTION_KEY,
        )
        session.commit()

        configuration = resolve_microsoft_oauth_configuration(
            session,
            encryption_key=ENCRYPTION_KEY,
        )
        stored_configuration = get_provider_configuration(session, "microsoft")

    assert configuration is not None
    assert configuration.scopes == DEFAULT_MICROSOFT_OAUTH_SCOPES
    assert stored_configuration is not None
    assert stored_configuration.public_config_json is not None
    assert stored_configuration.public_config_json["scopes"] == " ".join(
        DEFAULT_MICROSOFT_OAUTH_SCOPES
    )


def test_microsoft_provider_configuration_defaults_delimiter_only_scopes(
    tmp_path: Path,
) -> None:
    with _build_session(tmp_path) as session:
        save_microsoft_oauth_configuration(
            session,
            client_id="microsoft-client-id",
            client_secret="microsoft-client-secret",
            scopes=", , ,",
            encryption_key=ENCRYPTION_KEY,
        )
        session.commit()

        configuration = resolve_microsoft_oauth_configuration(
            session,
            encryption_key=ENCRYPTION_KEY,
        )
        stored_configuration = get_provider_configuration(session, "microsoft")

    assert configuration is not None
    assert configuration.scopes == DEFAULT_MICROSOFT_OAUTH_SCOPES
    assert stored_configuration is not None
    assert stored_configuration.public_config_json is not None
    assert stored_configuration.public_config_json["scopes"] == " ".join(
        DEFAULT_MICROSOFT_OAUTH_SCOPES
    )


def _build_session(tmp_path: Path) -> Session:
    database_path = tmp_path / "microsoft-provider.sqlite3"
    engine = create_engine(
        f"sqlite+pysqlite:///{database_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def _build_settings(tmp_path: Path) -> Settings:
    database_path = tmp_path / "microsoft-provider.sqlite3"
    return Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        session_secret=SESSION_SECRET,
        encryption_key=ENCRYPTION_KEY,
    )


def _seed_connected_account(session: Session) -> ProviderAccount:
    account = ProviderAccount(
        provider_type="microsoft",
        provider_account_id="microsoft-sub",
        display_name="owner@example.com",
        access_token_encrypted=encrypt_text(ENCRYPTION_KEY, "access-token"),
        refresh_token_encrypted=encrypt_text(ENCRYPTION_KEY, "refresh-token"),
        provider_metadata={
            "microsoft_auth_status": "connected",
            "microsoft_access_token_expires_at": "2099-01-01T00:00:00+00:00",
            "microsoft_scopes": [
                "openid",
                "offline_access",
                "User.Read",
                "Calendars.Read",
            ],
        },
    )
    session.add(account)
    session.commit()
    return account
