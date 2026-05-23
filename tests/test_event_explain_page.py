from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pyotp
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from calsync.config import Settings
from calsync.main import create_app
from calsync.models import Base, Event, EventGroup, ProviderAccount, SyncLog
from calsync.repos.events import upsert_event
from calsync.repos.state import set_app_state
from calsync.repos.users import create_admin_user
from calsync.services.auth import (
    generate_recovery_codes,
    hash_password,
    store_recovery_codes,
    store_totp_secret,
)
from calsync.services.reconciliation import list_duplicate_groups, rebuild_duplicate_groups


ENCRYPTION_KEY = "event-explain-test-key"
SESSION_SECRET = "event-explain-session-secret"


@contextmanager
def _build_client(tmp_path: Path):
    database_path = tmp_path / "event-explain.sqlite3"
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

        google_event = upsert_event(
            session,
            _make_event(
                provider_type="google",
                provider_account_id="google-user@example.com",
                provider_calendar_id="google-primary",
                provider_event_id="evt-google",
                title="Orthodontist Appointment",
                description="Google copy",
                location="Smile Clinic",
            ),
        )
        upsert_event(
            session,
            _make_event(
                provider_type="icloud_caldav",
                provider_account_id="icloud-user@icloud.com",
                provider_calendar_id="icloud-family",
                provider_event_id="evt-icloud",
                title="Orthodontist Appointment",
            ),
        )
        rebuild_duplicate_groups(session)

        google_account = session.scalar(
            select(ProviderAccount).where(
                ProviderAccount.provider_type == "google",
                ProviderAccount.provider_account_id == "google-user@example.com",
            )
        )
        assert google_account is not None
        session.add(
            SyncLog(
                provider_account_pk=google_account.id,
                provider_type="google",
                trigger="manual",
                status="success",
                events_seen=2,
                events_upserted=2,
            )
        )
        google_event_id = google_event.id
        session.commit()

    app = create_app(settings)
    app.state.test_totp_secret = totp_secret
    app.state.test_google_event_id = google_event_id

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


def test_event_explain_page_requires_authenticated_admin(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        response = client.get("/admin/events/example-id", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_event_explain_page_shows_grouped_copies_and_preferred_state(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client)

        with _db_session(client) as session:
            group = list_duplicate_groups(session)[0]
            preferred = next(event for event in group.events if event.id == group.group.preferred_event_id)

        response = client.get(f"/admin/events/{preferred.id}")

    assert response.status_code == 200
    assert "Why CalSync is showing this appointment" in response.text
    assert "Preferred copy" in response.text
    assert "Grouped source copies" in response.text
    assert "google" in response.text.lower()
    assert "icloud" in response.text.lower()
    assert "Latest sync status" in response.text


def test_event_explain_page_persists_rebuilt_duplicate_state(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client)

        with _db_session(client) as session:
            group = list_duplicate_groups(session)[0]
            preferred = next(event for event in group.events if event.id == group.group.preferred_event_id)
            preferred_id = preferred.id
            session.query(EventGroup).delete()
            for event in group.events:
                stored_event = session.get(Event, event.id)
                assert stored_event is not None
                stored_event.canonical_group_id = None
                stored_event.event_visibility_state = "active"
            session.commit()

        response = client.get(f"/admin/events/{preferred_id}")
        assert response.status_code == 200

        with _db_session(client) as session:
            rebuilt_groups = list_duplicate_groups(session)

        assert len(rebuilt_groups) == 1


def _db_session(client: TestClient) -> Session:
    settings = client.app.state.settings
    engine = create_engine(
        settings.database_url,
        future=True,
        connect_args={"check_same_thread": False},
    )
    return Session(engine)


def _make_event(**overrides: object) -> dict[str, object]:
    payload = {
        "provider_type": "mock",
        "provider_account_id": "acct-1",
        "provider_calendar_id": "cal-1",
        "provider_event_id": "evt-1",
        "title": "Planning session",
        "starts_at": datetime(2026, 5, 24, 15, 0, tzinfo=UTC),
        "ends_at": datetime(2026, 5, 24, 16, 0, tzinfo=UTC),
        "all_day": False,
        "status": "confirmed",
        "source_payload": {"provider": "mock"},
    }
    payload.update(overrides)
    return payload
