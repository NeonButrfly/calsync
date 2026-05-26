from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from calsync.config import Settings
from calsync.crypto import encrypt_text
from calsync.main import create_app
from calsync.models import Base, Event, ProviderAccount, ProviderCalendar
from calsync.repos.events import upsert_event
from calsync.repos.state import set_app_state
from calsync.repos.users import create_admin_user
from calsync.services.auth import (
    generate_recovery_codes,
    hash_password,
    store_recovery_codes,
    store_totp_secret,
)


ENCRYPTION_KEY = "appointment-editor-test-key"
SESSION_SECRET = "appointment-editor-test-session-secret"


@contextmanager
def _build_client(tmp_path: Path):
    database_path = tmp_path / "appointment-editor.sqlite3"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        public_base_url="http://testserver",
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
        store_totp_secret(session, admin_user, totp_secret, encryption_key=ENCRYPTION_KEY)
        admin_user.mfa_enrolled = True
        store_recovery_codes(session, admin_user, generate_recovery_codes(count=2))

        account = ProviderAccount(
            provider_type="google",
            provider_account_id="writer@example.com",
            display_name="Writable Google",
            can_write=True,
            provider_metadata={
                "google_scopes": ["https://www.googleapis.com/auth/calendar"],
                "google_access_token_expires_at": datetime(2026, 6, 30, 0, 0, tzinfo=UTC).isoformat(),
            },
        )
        account.access_token_encrypted = encrypt_text(ENCRYPTION_KEY, "access-token")
        account.refresh_token_encrypted = encrypt_text(ENCRYPTION_KEY, "refresh-token")
        session.add(account)
        session.flush()
        calendar = ProviderCalendar(
            provider_account_pk=account.id,
            provider_calendar_id="primary",
            name="Primary",
            enabled=True,
            calendar_role="writable_booking_target",
            provider_metadata={"access_role": "owner"},
        )
        session.add(calendar)
        session.flush()
        event = upsert_event(
            session,
            {
                "provider_type": "google",
                "provider_account_id": account.provider_account_id,
                "provider_calendar_id": calendar.provider_calendar_id,
                "provider_event_id": "evt-existing",
                "title": "Existing Visit",
                "description": "Existing description",
                "location": "Existing location",
                "starts_at": datetime(2026, 6, 3, 18, 0, tzinfo=UTC),
                "ends_at": datetime(2026, 6, 3, 19, 0, tzinfo=UTC),
                "status": "confirmed",
                "all_day": False,
                "source_payload": {"href": "provider://existing"},
            },
        )
        event_id = event.id
        session.commit()

    app = create_app(settings)
    app.state.test_totp_secret = totp_secret
    app.state.test_event_id = event_id

    with TestClient(app) as test_client:
        yield test_client


def _login(client: TestClient) -> None:
    password_step = client.post(
        "/login",
        data={"identifier": "admin", "password": "StrongPassword1!"},
        follow_redirects=False,
    )
    assert password_step.status_code == 303

    mfa_step = client.post(
        "/login/mfa",
        data={"code": pyotp.TOTP(client.app.state.test_totp_secret).now()},
        follow_redirects=False,
    )
    assert mfa_step.status_code == 303


def test_create_appointment_page_requires_admin(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        response = client.get("/admin/appointments/new", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_create_appointment_page_lists_writable_calendars(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client)
        response = client.get("/admin/appointments/new")

    assert response.status_code == 200
    assert "Create appointment" in response.text
    assert "Writable Google" in response.text
    assert "Primary" in response.text


def test_edit_appointment_page_prefills_existing_event(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client)
        response = client.get(f"/admin/events/{client.app.state.test_event_id}/edit")

    assert response.status_code == 200
    assert "Edit appointment" in response.text
    assert "Existing Visit" in response.text
    assert "Existing location" in response.text


def test_cancel_appointment_marks_event_inactive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_cancel_event(self, account, calendar, provider_event_id, *, source_payload=None):
        return None

    monkeypatch.setattr(
        "calsync.services.providers.google.GoogleProviderAdapter.cancel_event",
        fake_cancel_event,
    )

    with _build_client(tmp_path) as client:
        _login(client)
        response = client.post(
            f"/admin/events/{client.app.state.test_event_id}/cancel",
            follow_redirects=False,
        )

    assert response.status_code == 303
    with _db_session(client) as session:
        event = session.get(Event, client.app.state.test_event_id)
        assert event is not None
        assert event.event_visibility_state in {"cancelled", "deleted_upstream"}


def _db_session(client: TestClient) -> Session:
    settings = client.app.state.settings
    engine = create_engine(
        settings.database_url,
        future=True,
        connect_args={"check_same_thread": False},
    )
    return Session(engine)
