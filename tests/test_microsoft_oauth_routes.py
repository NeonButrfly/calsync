from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from calsync.config import Settings
from calsync.main import create_app
from calsync.models import Base, ProviderAccount, ProviderCalendar
from calsync.repos.state import set_app_state
from calsync.repos.users import create_admin_user
from calsync.services.auth import (
    generate_recovery_codes,
    hash_password,
    store_recovery_codes,
    store_totp_secret,
)
from calsync.services.provider_config import save_microsoft_oauth_configuration


ENCRYPTION_KEY = "phase4-microsoft-route-key"


def _build_client(
    tmp_path: Path,
    *,
    microsoft_client_id: str | None,
    microsoft_client_secret: str | None,
    base_url: str,
    seed_provider_settings: bool = False,
    saved_public_base_url: str | None = None,
) -> TestClient:
    database_path = tmp_path / "microsoft-oauth-routes.sqlite3"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        public_base_url=None,
        session_secret="phase4-microsoft-route-session-secret",
        encryption_key=ENCRYPTION_KEY,
        microsoft_oauth_client_id=microsoft_client_id,
        microsoft_oauth_client_secret=microsoft_client_secret,
    )
    engine = create_engine(
        settings.database_url,
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        set_app_state(session, key="setup_completed", value_text="true")
        admin_user = create_admin_user(
            session,
            username="admin",
            email="admin@example.com",
            password_hash=hash_password("StrongPassword1!"),
        )
        totp_secret = pyotp.random_base32()
        store_totp_secret(
            session,
            admin_user,
            totp_secret,
            encryption_key=ENCRYPTION_KEY,
        )
        admin_user.mfa_enrolled = True
        store_recovery_codes(session, admin_user, generate_recovery_codes(count=2))
        if seed_provider_settings:
            save_microsoft_oauth_configuration(
                session,
                client_id="microsoft-client-id",
                client_secret="microsoft-client-secret",
                scopes="openid,offline_access,User.Read,Calendars.Read",
                encryption_key=ENCRYPTION_KEY,
                settings=settings,
            )
        if saved_public_base_url is not None:
            set_app_state(session, key="public_base_url", value_text=saved_public_base_url)
        session.commit()

    app = create_app(settings)
    app.state.test_totp_secret = totp_secret
    client = TestClient(app, base_url=base_url)
    _login(client, totp_secret)
    return client


def _login(client: TestClient, totp_secret: str) -> None:
    password_step = client.post(
        "/login",
        data={"identifier": "admin", "password": "StrongPassword1!"},
        follow_redirects=False,
    )
    assert password_step.status_code == 303

    mfa_step = client.post(
        "/login/mfa",
        data={"code": pyotp.TOTP(totp_secret).now()},
        follow_redirects=False,
    )
    assert mfa_step.status_code == 303


def _db_session(client: TestClient) -> Session:
    settings = client.app.state.settings
    engine = create_engine(
        settings.database_url,
        future=True,
        connect_args={"check_same_thread": False},
    )
    return Session(engine)


def test_microsoft_start_reports_missing_provider_settings(tmp_path: Path) -> None:
    with _build_client(
        tmp_path,
        microsoft_client_id=None,
        microsoft_client_secret=None,
        base_url="http://localhost:3080",
        seed_provider_settings=False,
    ) as client:
        response = client.get("/auth/microsoft/start")

    assert response.status_code == 400
    assert "Provider Settings" in response.text


def test_microsoft_start_redirects_to_microsoft_when_configured(
    tmp_path: Path,
) -> None:
    with _build_client(
        tmp_path,
        microsoft_client_id=None,
        microsoft_client_secret=None,
        base_url="http://localhost:3080",
        seed_provider_settings=True,
    ) as client:
        response = client.get("/auth/microsoft/start", follow_redirects=False)

    assert response.status_code == 303
    parsed = urlsplit(response.headers["location"])
    query = parse_qs(parsed.query)
    assert parsed.netloc == "login.microsoftonline.com"
    assert query["redirect_uri"] == ["http://localhost:3080/auth/microsoft/callback"]
    assert query["state"]


def test_microsoft_start_uses_saved_public_url_when_present(
    tmp_path: Path,
) -> None:
    with _build_client(
        tmp_path,
        microsoft_client_id=None,
        microsoft_client_secret=None,
        base_url="http://192.168.50.232:3080",
        seed_provider_settings=True,
        saved_public_base_url="https://calsync.neonbutterfly.net",
    ) as client:
        response = client.get("/auth/microsoft/start", follow_redirects=False)

    assert response.status_code == 303
    assert (
        "redirect_uri=https%3A%2F%2Fcalsync.neonbutterfly.net%2Fauth%2Fmicrosoft%2Fcallback"
        in response.headers["location"]
    )


def test_microsoft_callback_persists_account_and_discovers_calendars(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    with _build_client(
        tmp_path,
        microsoft_client_id=None,
        microsoft_client_secret=None,
        base_url="http://localhost:3080",
        seed_provider_settings=True,
    ) as client:
        start_response = client.get("/auth/microsoft/start", follow_redirects=False)
        state = parse_qs(urlsplit(start_response.headers["location"]).query)["state"][0]

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

        callback_response = client.get(
            f"/auth/microsoft/callback?state={state}&code=microsoft-code",
            follow_redirects=False,
        )

        assert callback_response.status_code == 303
        assert callback_response.headers["location"] == "/admin/calendars"

        with _db_session(client) as session:
            account = session.scalar(
                select(ProviderAccount).where(
                    ProviderAccount.provider_type == "microsoft"
                )
            )
            assert account is not None
            assert account.display_name == "owner@example.com"
            calendar = session.scalar(
                select(ProviderCalendar).where(
                    ProviderCalendar.provider_account_pk == account.id
                )
            )
            assert calendar is not None
            assert calendar.provider_calendar_id == "primary"
            assert calendar.enabled is False
