from __future__ import annotations

from pathlib import Path

import pyotp
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from calsync.config import Settings
from calsync.main import create_app
from calsync.models import Base
from calsync.repos.providers import upsert_provider_account
from calsync.repos.state import set_app_state
from calsync.repos.users import create_admin_user
from calsync.services.provider_config import save_microsoft_oauth_configuration
from calsync.services.auth import (
    generate_recovery_codes,
    hash_password,
    store_recovery_codes,
    store_totp_secret,
)


ENCRYPTION_KEY = "phase1-connections-page-encryption-key"


def test_connections_page_shows_google_microsoft_and_apple_cards(
    tmp_path: Path,
) -> None:
    with _build_client(tmp_path) as client:
        _login(client, client.app.state.test_totp_secret)

        response = client.get("/admin/connections")

    assert response.status_code == 200
    assert "Connect a calendar" in response.text
    assert "Google Calendar" in response.text
    assert "Outlook / Microsoft 365" in response.text
    assert "Apple Calendar" in response.text


def test_connections_page_shows_connect_microsoft_action_when_configured(
    tmp_path: Path,
) -> None:
    with _build_client(tmp_path, seed_microsoft_provider_settings=True) as client:
        _login(client, client.app.state.test_totp_secret)

        response = client.get("/admin/connections")

    assert response.status_code == 200
    assert "Connect Microsoft Account" in response.text
    assert "auth/microsoft/callback" in response.text


def test_connections_page_keeps_existing_apple_account_visible(
    tmp_path: Path,
) -> None:
    with _build_client(tmp_path) as client:
        _login(client, client.app.state.test_totp_secret)

        with _db_session(client) as session:
            upsert_provider_account(
                session,
                provider_type="icloud_caldav",
                provider_account_id="family@icloud.com",
                display_name="Family iCloud",
                provider_metadata={"auth_status": "connected"},
            )
            session.commit()

        response = client.get("/admin/connections")

    assert response.status_code == 200
    assert "Family iCloud" in response.text
    assert "Apple Calendar" in response.text


def test_accounts_route_remains_a_safe_alias_for_connections(
    tmp_path: Path,
) -> None:
    with _build_client(tmp_path) as client:
        _login(client, client.app.state.test_totp_secret)

        response = client.get("/admin/accounts")

    assert response.status_code == 200
    assert "Connect a calendar" in response.text


def _build_client(
    tmp_path: Path,
    *,
    seed_microsoft_provider_settings: bool = False,
) -> TestClient:
    database_path = tmp_path / "connections-page.sqlite3"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        public_base_url="http://localhost:3080",
        session_secret="phase1-connections-page-session-secret",
        encryption_key=ENCRYPTION_KEY,
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
        if seed_microsoft_provider_settings:
            save_microsoft_oauth_configuration(
                session,
                client_id="microsoft-client-id",
                client_secret="microsoft-client-secret",
                scopes="openid offline_access User.Read Calendars.Read",
                encryption_key=ENCRYPTION_KEY,
                settings=settings,
            )
        session.commit()

    app = create_app(settings)
    app.state.test_totp_secret = totp_secret
    return TestClient(app, base_url="http://localhost:3080")


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
