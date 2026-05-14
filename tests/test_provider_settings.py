from __future__ import annotations

from pathlib import Path

import pyotp
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from calsync.config import Settings
from calsync.crypto import decrypt_text
from calsync.main import create_app
from calsync.models import Base, ProviderConfiguration
from calsync.repos.state import set_app_state
from calsync.repos.users import create_admin_user
from calsync.services.auth import (
    generate_recovery_codes,
    hash_password,
    store_recovery_codes,
    store_totp_secret,
)


ENCRYPTION_KEY = "phase3-provider-settings-encryption-key"
SESSION_SECRET = "phase3-provider-settings-session-secret"


def test_google_provider_settings_can_be_saved_from_admin_ui(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client, client.app.state.test_totp_secret)

        response = client.post(
            "/admin/providers/google",
            data={
                "client_id": "google-client-id",
                "client_secret": "google-client-secret",
                "scopes": (
                    "openid,email,profile,"
                    "https://www.googleapis.com/auth/calendar.readonly"
                ),
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/providers?saved=google"

        providers_page = client.get("/admin/providers?saved=google")
        assert providers_page.status_code == 200
        assert "Google OAuth app settings saved." in providers_page.text
        assert "google-client-id" in providers_page.text
        assert "auth/google/callback" in providers_page.text

        accounts_page = client.get("/admin/accounts")
        assert accounts_page.status_code == 200
        assert "Connect Google Account" in accounts_page.text
        assert "Google OAuth is not configured yet" not in accounts_page.text

        with _db_session(client) as session:
            configuration = session.scalar(
                select(ProviderConfiguration).where(
                    ProviderConfiguration.provider_type == "google_oauth"
                )
            )
            assert configuration is not None
            assert configuration.public_config_json is not None
            assert configuration.public_config_json["client_id"] == "google-client-id"
            assert configuration.secret_config_encrypted is not None
            assert "google-client-secret" not in configuration.secret_config_encrypted
            decrypted_secret = decrypt_text(
                ENCRYPTION_KEY,
                configuration.secret_config_encrypted,
            )
            assert decrypted_secret == "google-client-secret"


def test_provider_settings_can_save_public_base_url(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client, client.app.state.test_totp_secret)

        response = client.post(
            "/admin/providers/public-url",
            data={"public_base_url": "https://calsync.neonbutterfly.net"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/providers?saved=public-url"

        page = client.get("/admin/providers?saved=public-url")
        assert "https://calsync.neonbutterfly.net" in page.text
        assert "Public app URL saved." in page.text


def test_provider_settings_rejects_invalid_public_base_url(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client, client.app.state.test_totp_secret)

        response = client.post(
            "/admin/providers/public-url",
            data={"public_base_url": "not-a-valid-url"},
            follow_redirects=False,
        )

        assert response.status_code == 400
        assert "Public app URL must be a valid http or https URL." in response.text


def test_provider_settings_page_requires_authenticated_admin(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        response = client.get("/admin/providers", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def _build_client(tmp_path: Path) -> TestClient:
    database_path = tmp_path / "provider-settings.sqlite3"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        public_base_url="http://localhost:3080",
        session_secret=SESSION_SECRET,
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
