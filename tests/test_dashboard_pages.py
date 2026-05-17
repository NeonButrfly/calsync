from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from calsync.config import Settings
from calsync.main import create_app
from calsync.models import Base, Event, ProviderAccount, ProviderCalendar, PublishedFeed, SyncLog
from calsync.repos.state import set_app_state
from calsync.repos.users import create_admin_user
from calsync.services.auth import (
    generate_recovery_codes,
    hash_password,
    store_recovery_codes,
    store_totp_secret,
)
from calsync.services.publishing import ensure_combined_feed
from calsync.services.sync import discover_calendars, sync_account


ENCRYPTION_KEY = "phase1-dashboard-test-key"
SESSION_SECRET = "phase1-dashboard-session-secret"


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    yield from _build_client(tmp_path, seed_mock_account=True)


@pytest.fixture()
def empty_client(tmp_path: Path) -> TestClient:
    yield from _build_client(tmp_path, seed_mock_account=False)


def _build_client(tmp_path: Path, *, seed_mock_account: bool) -> TestClient:
    database_path = tmp_path / "dashboard-pages.sqlite3"
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
        store_totp_secret(
            session,
            admin_user,
            totp_secret,
            encryption_key=ENCRYPTION_KEY,
        )
        admin_user.mfa_enrolled = True
        store_recovery_codes(session, admin_user, generate_recovery_codes(count=2))

        account = ProviderAccount(
            provider_type="mock",
            provider_account_id="mock-acct-1",
            display_name="Mock Account",
            provider_metadata={"seed": "phase1"},
        )
        if seed_mock_account:
            session.add(account)
            session.flush()
            account_id = account.id
            discover_calendars(session, account.id)
            sync_account(session, account.id, trigger="manual")
        else:
            account_id = None
        combined_feed = ensure_combined_feed(session)
        combined_feed_id = combined_feed.id
        session.commit()

    app = create_app(settings)
    app.state.test_totp_secret = totp_secret
    app.state.test_account_id = account_id
    app.state.test_combined_feed_id = combined_feed_id

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def authenticated_client(client: TestClient) -> TestClient:
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
    return client


def test_dashboard_requires_authenticated_admin(client: TestClient) -> None:
    response = client.get("/admin", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_dashboard_shows_feed_links_and_sync_summary(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.get("/admin")

    assert response.status_code == 200
    assert "Combined feed" in response.text
    assert "Last sync" in response.text
    assert "/feeds/" in response.text
    assert "Morning Standup" in response.text


def test_dashboard_renders_sync_and_event_times_in_alaska_time(
    authenticated_client: TestClient,
) -> None:
    with _db_session(authenticated_client) as session:
        latest_sync = session.scalar(
            select(SyncLog).order_by(SyncLog.started_at.desc(), SyncLog.id.desc())
        )
        assert latest_sync is not None
        latest_sync.started_at = datetime(2026, 5, 15, 18, 0, tzinfo=UTC)

        upcoming_event = session.scalar(
            select(Event).order_by(Event.starts_at, Event.id)
        )
        assert upcoming_event is not None
        upcoming_event.starts_at = datetime(2026, 5, 15, 18, 0, tzinfo=UTC)
        session.commit()

    response = authenticated_client.get("/admin")

    assert response.status_code == 200
    assert "Fri May 15 at 10:00 AM AKDT" in response.text
    assert "+00:00" not in response.text


@pytest.fixture()
def authenticated_empty_client(empty_client: TestClient) -> TestClient:
    password_step = empty_client.post(
        "/login",
        data={"identifier": "admin", "password": "StrongPassword1!"},
        follow_redirects=False,
    )
    assert password_step.status_code == 303

    mfa_step = empty_client.post(
        "/login/mfa",
        data={"code": pyotp.TOTP(empty_client.app.state.test_totp_secret).now()},
        follow_redirects=False,
    )
    assert mfa_step.status_code == 303
    return empty_client


def test_calendar_toggle_updates_enabled_state(
    authenticated_client: TestClient,
) -> None:
    with _db_session(authenticated_client) as session:
        calendar = session.scalar(
            select(ProviderCalendar).where(
                ProviderCalendar.provider_calendar_id == "work",
            )
        )
        assert calendar is not None
        original_enabled = calendar.enabled

    response = authenticated_client.post(
        f"/admin/calendars/{calendar.id}/toggle",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/calendars"

    with _db_session(authenticated_client) as session:
        refreshed_calendar = session.get(ProviderCalendar, calendar.id)
        assert refreshed_calendar is not None
        assert refreshed_calendar.enabled is (not original_enabled)


def test_manual_sync_action_records_new_sync_log(
    authenticated_client: TestClient,
) -> None:
    with _db_session(authenticated_client) as session:
        before_count = session.query(SyncLog).count()

    response = authenticated_client.post(
        f"/admin/sync/accounts/{authenticated_client.app.state.test_account_id}/run",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/sync"

    with _db_session(authenticated_client) as session:
        logs = session.scalars(select(SyncLog).order_by(SyncLog.started_at)).all()
        assert len(logs) == before_count + 1
        assert logs[-1].status == "success"


def test_sync_status_page_renders_last_sync_in_alaska_time(
    authenticated_client: TestClient,
) -> None:
    with _db_session(authenticated_client) as session:
        latest_log = session.scalar(
            select(SyncLog).order_by(SyncLog.started_at.desc(), SyncLog.id.desc())
        )
        assert latest_log is not None
        latest_log.finished_at = datetime(2026, 5, 16, 1, 30, tzinfo=UTC)
        session.commit()

    response = authenticated_client.get("/admin/sync")

    assert response.status_code == 200
    assert "Fri May 15 at 5:30 PM AKDT" in response.text
    assert "+00:00" not in response.text


def test_rotating_combined_feed_changes_token(
    authenticated_client: TestClient,
) -> None:
    with _db_session(authenticated_client) as session:
        original_feed = session.get(
            PublishedFeed,
            authenticated_client.app.state.test_combined_feed_id,
        )
        assert original_feed is not None
        original_token = original_feed.token

    response = authenticated_client.post(
        "/admin/feeds/combined/rotate",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/feeds"

    with _db_session(authenticated_client) as session:
        rotated_feed = session.get(
            PublishedFeed,
            authenticated_client.app.state.test_combined_feed_id,
        )
        assert rotated_feed is not None
        assert rotated_feed.token != original_token


def test_connecting_mock_provider_creates_account_and_events(
    authenticated_empty_client: TestClient,
) -> None:
    response = authenticated_empty_client.post(
        "/admin/accounts/mock/connect",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/accounts"

    with _db_session(authenticated_empty_client) as session:
        assert session.query(ProviderAccount).count() == 1
        assert session.query(SyncLog).count() == 1

    dashboard = authenticated_empty_client.get("/admin")
    assert dashboard.status_code == 200
    assert "Morning Standup" in dashboard.text


def _db_session(client: TestClient) -> Session:
    settings = client.app.state.settings
    engine = create_engine(
        settings.database_url,
        future=True,
        connect_args={"check_same_thread": False},
    )
    return Session(engine)
