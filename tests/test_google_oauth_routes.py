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


ENCRYPTION_KEY = "phase2-google-route-key"


@pytest.fixture()
def localhost_client(tmp_path: Path) -> TestClient:
    yield from _build_client(
        tmp_path,
        public_base_url=None,
        google_client_id="google-client-id",
        google_client_secret="google-client-secret",
        base_url="http://localhost:3080",
    )


@pytest.fixture()
def lan_ip_client(tmp_path: Path) -> TestClient:
    yield from _build_client(
        tmp_path,
        public_base_url=None,
        google_client_id="google-client-id",
        google_client_secret="google-client-secret",
        base_url="http://192.168.50.232:3080",
    )


def _build_client(
    tmp_path: Path,
    *,
    public_base_url: str | None,
    google_client_id: str | None,
    google_client_secret: str | None,
    base_url: str,
) -> TestClient:
    database_path = tmp_path / "google-oauth-routes.sqlite3"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        public_base_url=public_base_url,
        session_secret="phase2-google-route-session-secret",
        encryption_key=ENCRYPTION_KEY,
        google_oauth_client_id=google_client_id,
        google_oauth_client_secret=google_client_secret,
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
        session.commit()

    app = create_app(settings)
    app.state.test_totp_secret = totp_secret
    with TestClient(app, base_url=base_url) as client:
        _login(client, totp_secret)
        yield client


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


def test_google_start_blocks_raw_ip_callback_origin(
    lan_ip_client: TestClient,
) -> None:
    response = lan_ip_client.get("/auth/google/start")

    assert response.status_code == 400
    assert "raw IP addresses" in response.text


def test_google_start_redirects_to_google_when_callback_is_compatible(
    localhost_client: TestClient,
) -> None:
    response = localhost_client.get("/auth/google/start", follow_redirects=False)

    assert response.status_code == 303
    parsed = urlsplit(response.headers["location"])
    query = parse_qs(parsed.query)
    assert parsed.netloc == "accounts.google.com"
    assert query["redirect_uri"] == ["http://localhost:3080/auth/google/callback"]
    assert query["state"]


def test_google_callback_persists_account_and_discovers_calendars(
    localhost_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start_response = localhost_client.get("/auth/google/start", follow_redirects=False)
    assert start_response.status_code == 303
    state = parse_qs(urlsplit(start_response.headers["location"]).query)["state"][0]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == httpx.URL("https://oauth2.googleapis.com/token"):
            return httpx.Response(
                200,
                json={
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                    "expires_in": 3600,
                    "scope": "openid email profile https://www.googleapis.com/auth/calendar.readonly",
                },
                request=request,
            )
        if request.url == httpx.URL("https://openidconnect.googleapis.com/v1/userinfo"):
            return httpx.Response(
                200,
                json={
                    "sub": "google-sub",
                    "email": "owner@example.com",
                    "name": "Owner",
                },
                request=request,
            )
        if request.url.path == "/calendar/v3/users/me/calendarList":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "primary",
                            "summary": "Primary",
                            "timeZone": "America/Anchorage",
                            "accessRole": "owner",
                            "selected": True,
                        }
                    ],
                    "nextSyncToken": "calendar-sync-token",
                },
                request=request,
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    monkeypatch.setattr(
        "calsync.services.providers.google._build_http_client",
        lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )

    callback_response = localhost_client.get(
        f"/auth/google/callback?state={state}&code=google-code",
        follow_redirects=False,
    )

    assert callback_response.status_code == 303
    assert callback_response.headers["location"] == "/admin/accounts"

    with _db_session(localhost_client) as session:
        account = session.scalar(
            select(ProviderAccount).where(ProviderAccount.provider_type == "google")
        )
        assert account is not None
        assert account.display_name == "owner@example.com"
        assert account.provider_metadata is not None
        calendar = session.scalar(
            select(ProviderCalendar).where(
                ProviderCalendar.provider_account_pk == account.id
            )
        )
        assert calendar is not None
        assert calendar.provider_calendar_id == "primary"
        assert calendar.enabled is False


def test_google_callback_reports_missing_refresh_token_for_new_account(
    localhost_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start_response = localhost_client.get("/auth/google/start", follow_redirects=False)
    assert start_response.status_code == 303
    state = parse_qs(urlsplit(start_response.headers["location"]).query)["state"][0]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == httpx.URL("https://oauth2.googleapis.com/token"):
            return httpx.Response(
                200,
                json={
                    "access_token": "access-token",
                    "expires_in": 3600,
                    "scope": "openid email profile https://www.googleapis.com/auth/calendar.readonly",
                },
                request=request,
            )
        if request.url == httpx.URL("https://openidconnect.googleapis.com/v1/userinfo"):
            return httpx.Response(
                200,
                json={"sub": "google-sub", "email": "owner@example.com"},
                request=request,
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    monkeypatch.setattr(
        "calsync.services.providers.google._build_http_client",
        lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )

    callback_response = localhost_client.get(
        f"/auth/google/callback?state={state}&code=google-code"
    )

    assert callback_response.status_code == 400
    assert "refresh token" in callback_response.text


def _db_session(client: TestClient) -> Session:
    settings = client.app.state.settings
    engine = create_engine(
        settings.database_url,
        future=True,
        connect_args={"check_same_thread": False},
    )
    return Session(engine)
