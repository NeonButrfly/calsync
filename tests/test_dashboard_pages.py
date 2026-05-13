from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from calsync.config import Settings
from calsync.main import create_app
from calsync.models import Base, ProviderAccount, ProviderCalendar, PublishedFeed, SyncLog
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
        session.add(account)
        session.flush()
        account_id = account.id
        discover_calendars(session, account.id)
        sync_account(session, account.id, trigger="manual")
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


def _db_session(client: TestClient) -> Session:
    settings = client.app.state.settings
    engine = create_engine(
        settings.database_url,
        future=True,
        connect_args={"check_same_thread": False},
    )
    return Session(engine)
