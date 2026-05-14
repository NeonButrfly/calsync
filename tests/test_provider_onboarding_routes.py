from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from calsync.config import Settings
from calsync.crypto import decrypt_text
from calsync.main import create_app
from calsync.models import Base, ProviderAccount, ProviderCalendar
from calsync.repos.state import set_app_state
from calsync.repos.users import create_admin_user
from calsync.schemas.providers import DiscoveredCalendar
from calsync.services.auth import (
    generate_recovery_codes,
    hash_password,
    store_recovery_codes,
    store_totp_secret,
)


ENCRYPTION_KEY = "phase3-provider-onboarding-encryption-key"


def test_accounts_page_shows_apple_add_account_form(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client, client.app.state.test_totp_secret)

        response = client.get("/admin/accounts")

    assert response.status_code == 200
    assert "Add Apple/iCloud Account" in response.text
    assert "Provider Settings" in response.text


def test_adding_icloud_account_discovers_calendars_and_stores_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _build_client(tmp_path) as client:
        _login(client, client.app.state.test_totp_secret)

        class FakeICloudAdapter:
            provider_type = "icloud_caldav"

            def discover_calendars(self, account: ProviderAccount) -> list[DiscoveredCalendar]:
                assert account.provider_account_id == "kay@icloud.com"
                return [
                    DiscoveredCalendar(
                        external_id="family",
                        name="Family",
                        timezone="America/Anchorage",
                        default_enabled=False,
                        metadata={"color": "#00aa88"},
                    )
                ]

            def fetch_events(self, account, calendar):
                return []

        monkeypatch.setattr(
            "calsync.services.sync.get_provider_adapter",
            lambda provider_type, settings=None, session=None: FakeICloudAdapter(),
        )

        response = client.post(
            "/admin/accounts/icloud/connect",
            data={
                "label": "Kay iCloud",
                "username": "kay@icloud.com",
                "app_password": "abcd-efgh-ijkl-mnop",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/accounts"

        with _db_session(client) as session:
            account = session.scalar(
                select(ProviderAccount).where(
                    ProviderAccount.provider_type == "icloud_caldav"
                )
            )
            assert account is not None
            assert account.display_name == "Kay iCloud"
            assert account.credential_secret_encrypted is not None
            assert (
                decrypt_text(ENCRYPTION_KEY, account.credential_secret_encrypted)
                == "abcd-efgh-ijkl-mnop"
            )
            calendar = session.scalar(
                select(ProviderCalendar).where(
                    ProviderCalendar.provider_account_pk == account.id
                )
            )
            assert calendar is not None
            assert calendar.provider_calendar_id == "family"
            assert calendar.enabled is False


def _build_client(tmp_path: Path) -> TestClient:
    database_path = tmp_path / "provider-onboarding.sqlite3"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        public_base_url="http://localhost:3080",
        session_secret="phase3-provider-onboarding-session-secret",
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
