from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterator

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from calsync.config import Settings
from calsync.main import create_app
from calsync.models import Base, Event, ProviderAccount, ProviderCalendar, PublishedFeed, SyncLog
from calsync.repos.events import upsert_event
from calsync.repos.state import set_app_state
from calsync.repos.users import create_admin_user
from calsync.services.auth import (
    generate_recovery_codes,
    hash_password,
    store_recovery_codes,
    store_totp_secret,
)
from calsync.services.publishing import ensure_combined_feed
from calsync.services.reconciliation import rebuild_duplicate_groups
from calsync.services.sync import discover_calendars, sync_account


ENCRYPTION_KEY = "phase1-dashboard-test-key"
SESSION_SECRET = "phase1-dashboard-session-secret"


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    yield from _build_client(tmp_path, seed_mock_account=True)


@pytest.fixture()
def empty_client(tmp_path: Path) -> TestClient:
    yield from _build_client(tmp_path, seed_mock_account=False)


def _build_client(
    tmp_path: Path,
    *,
    seed_mock_account: bool,
    request_base_url: str = "http://testserver",
    saved_public_base_url: str | None = None,
) -> Iterator[TestClient]:
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
        if saved_public_base_url is not None:
            set_app_state(
                session,
                key="public_base_url",
                value_text=saved_public_base_url,
            )
        combined_feed = ensure_combined_feed(session)
        combined_feed_id = combined_feed.id
        session.commit()

    app = create_app(settings)
    app.state.test_totp_secret = totp_secret
    app.state.test_account_id = account_id
    app.state.test_combined_feed_id = combined_feed_id

    with TestClient(app, base_url=request_base_url) as test_client:
        yield test_client


@pytest.fixture()
def authenticated_client(client: TestClient) -> TestClient:
    _authenticate_client(client)
    return client


def test_dashboard_requires_authenticated_admin(client: TestClient) -> None:
    response = client.get("/admin", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_dashboard_shows_feed_links_and_sync_summary(
    authenticated_client: TestClient,
) -> None:
    with _db_session(authenticated_client) as session:
        hidden_event = session.scalar(
            select(Event).where(Event.provider_event_id == "home-standup")
        )
        assert hidden_event is not None
        hidden_event.event_visibility_state = "deleted_upstream"
        hidden_event.removed_upstream_at = datetime.now(UTC)
        combined_feed = session.get(
            PublishedFeed,
            authenticated_client.app.state.test_combined_feed_id,
        )
        assert combined_feed is not None
        combined_feed_token = combined_feed.token
        session.commit()

    response = authenticated_client.get("/admin")

    assert response.status_code == 200
    assert "Upcoming schedule" in response.text
    assert "Combined feed" in response.text
    assert "Last sync" in response.text
    assert f'href="http://testserver/feeds/{combined_feed_token}.ics"' in response.text
    assert "Morning Standup" not in response.text


def test_dashboard_feed_link_uses_saved_public_base_url_origin_when_present(
    tmp_path: Path,
) -> None:
    client_gen = _build_client(
        tmp_path,
        seed_mock_account=True,
        request_base_url="http://localhost:4010",
        saved_public_base_url="https://calendar.example.com/base/",
    )
    client = next(client_gen)
    try:
        _authenticate_client(client)
        with _db_session(client) as session:
            combined_feed = session.get(PublishedFeed, client.app.state.test_combined_feed_id)
            assert combined_feed is not None

        response = client.get("/admin")

        assert response.status_code == 200
        assert (
            f'href="https://calendar.example.com/base/feeds/{combined_feed.token}.ics"'
            in response.text
        )
        assert "http://localhost:4010/feeds/" not in response.text
    finally:
        _close_client_generator(client_gen)


def test_dashboard_feed_link_falls_back_to_request_origin_for_invalid_saved_public_base_url(
    tmp_path: Path,
) -> None:
    client_gen = _build_client(
        tmp_path,
        seed_mock_account=True,
        request_base_url="http://localhost:4010",
        saved_public_base_url="http://192.168.50.232:3080",
    )
    client = next(client_gen)
    try:
        _authenticate_client(client)
        with _db_session(client) as session:
            combined_feed = session.get(PublishedFeed, client.app.state.test_combined_feed_id)
            assert combined_feed is not None

        response = client.get("/admin")

        assert response.status_code == 200
        assert f'href="http://localhost:4010/feeds/{combined_feed.token}.ics"' in response.text
        assert "http://192.168.50.232:3080/feeds/" not in response.text
    finally:
        _close_client_generator(client_gen)


def test_dashboard_hides_events_from_disabled_calendars(
    authenticated_client: TestClient,
) -> None:
    with _db_session(authenticated_client) as session:
        calendar = session.scalar(
            select(ProviderCalendar).where(
                ProviderCalendar.provider_calendar_id == "home",
            )
        )
        event = session.scalar(select(Event).where(Event.provider_event_id == "home-standup"))
        assert calendar is not None
        assert event is not None
        calendar.enabled = False
        session.commit()

    response = authenticated_client.get("/admin")

    assert response.status_code == 200
    assert "Morning Standup" not in response.text


def test_dashboard_shows_trust_review_summary_for_duplicate_groups(
    authenticated_client: TestClient,
) -> None:
    with _db_session(authenticated_client) as session:
        source_event = session.scalar(select(Event).where(Event.provider_event_id == "home-standup"))
        assert source_event is not None

        upsert_event(
            session,
            {
                "provider_type": "google",
                "provider_account_id": "google-acct-1",
                "provider_calendar_id": "google-primary",
                "provider_event_id": "duplicate-standup",
                "title": source_event.title,
                "starts_at": source_event.starts_at,
                "ends_at": source_event.ends_at,
                "all_day": source_event.all_day,
                "status": "confirmed",
                "location": source_event.location,
                "source_payload": {"seed": "dashboard-duplicate"},
            },
        )
        rebuild_duplicate_groups(session)
        session.commit()

    response = authenticated_client.get("/admin")

    assert response.status_code == 200
    assert "Trust review" in response.text
    assert "Possible duplicates" in response.text
    assert "Open trust review" in response.text


def test_dashboard_shows_problem_to_fix_summary(
    authenticated_client: TestClient,
) -> None:
    with _db_session(authenticated_client) as session:
        source_event = session.scalar(select(Event).where(Event.provider_event_id == "home-standup"))
        account = session.scalar(select(ProviderAccount).where(ProviderAccount.provider_type == "mock"))
        assert source_event is not None
        assert account is not None

        upsert_event(
            session,
            {
                "provider_type": "google",
                "provider_account_id": "google-acct-1",
                "provider_calendar_id": "google-primary",
                "provider_event_id": "duplicate-standup-problem-summary",
                "title": source_event.title,
                "starts_at": source_event.starts_at,
                "ends_at": source_event.ends_at,
                "all_day": source_event.all_day,
                "status": "confirmed",
                "location": source_event.location,
                "source_payload": {"seed": "dashboard-problem-summary"},
            },
        )
        latest_log = session.scalar(
            select(SyncLog).where(SyncLog.provider_account_pk == account.id).order_by(SyncLog.started_at.desc(), SyncLog.id.desc())
        )
        assert latest_log is not None
        latest_log.status = "error"
        latest_log.error_text = "Mock sync stalled."
        rebuild_duplicate_groups(session)
        session.commit()

    response = authenticated_client.get("/admin")

    assert response.status_code == 200
    assert "Problems to fix" in response.text
    assert "Open problem-to-fix list" in response.text
    assert "Sync or auth issues" in response.text


def test_dashboard_combined_view_prefers_one_canonical_row_with_source_count(
    authenticated_client: TestClient,
) -> None:
    with _db_session(authenticated_client) as session:
        source_event = session.scalar(select(Event).where(Event.provider_event_id == "home-standup"))
        assert source_event is not None
        source_event.starts_at = datetime(2026, 5, 28, 18, 0, tzinfo=UTC)
        source_event.ends_at = datetime(2026, 5, 28, 18, 30, tzinfo=UTC)

        upsert_event(
            session,
            {
                "provider_type": "google",
                "provider_account_id": "google-acct-1",
                "provider_calendar_id": "google-primary",
                "provider_event_id": "duplicate-standup-source-badge",
                "title": f"{source_event.title} Appointment",
                "starts_at": source_event.starts_at,
                "ends_at": source_event.ends_at,
                "all_day": source_event.all_day,
                "status": "confirmed",
                "location": source_event.location,
                "source_payload": {"seed": "dashboard-source-badge"},
            },
        )
        rebuild_duplicate_groups(session)
        session.commit()

    response = authenticated_client.get("/admin")

    assert response.status_code == 200
    assert "2 sources" in response.text
    assert response.text.count("Morning Standup") == 1


def test_dashboard_upcoming_schedule_ignores_stale_long_running_history(
    authenticated_client: TestClient,
) -> None:
    with _db_session(authenticated_client) as session:
        stale_start = datetime.now(UTC) - timedelta(days=180)
        upsert_event(
            session,
            {
                "provider_type": "google",
                "provider_account_id": "google-acct-legacy",
                "provider_calendar_id": "google-primary",
                "provider_event_id": "legacy-long-running",
                "title": "Legacy Long Running Event",
                "starts_at": stale_start,
                "ends_at": datetime.now(UTC) + timedelta(days=120),
                "all_day": False,
                "status": "confirmed",
                "source_payload": {"seed": "legacy-long-running"},
            },
        )
        session.commit()

    response = authenticated_client.get("/admin")

    assert response.status_code == 200
    assert "Legacy Long Running Event" not in response.text


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
    assert "Fri May 15 at 10:00 AM AKST" in response.text
    assert "+00:00" not in response.text


def test_dashboard_upcoming_schedule_ignores_ancient_events(
    authenticated_client: TestClient,
) -> None:
    with _db_session(authenticated_client) as session:
        upcoming_event = session.scalar(
            select(Event).where(Event.provider_event_id == "home-standup")
        )
        assert upcoming_event is not None
        upcoming_event.title = "Alaska School Leadership Institute 2012"
        upcoming_event.starts_at = datetime(2012, 5, 28, 20, 0, tzinfo=UTC)
        upcoming_event.ends_at = datetime(2012, 5, 28, 21, 0, tzinfo=UTC)
        session.commit()

    response = authenticated_client.get("/admin")

    assert response.status_code == 200
    assert "Alaska School Leadership Institute 2012" not in response.text


@pytest.fixture()
def authenticated_empty_client(empty_client: TestClient) -> TestClient:
    _authenticate_client(empty_client)
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
    assert "Fri May 15 at 5:30 PM AKST" in response.text
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
        assert session.query(Event).count() > 0

    dashboard = authenticated_empty_client.get("/admin")
    assert dashboard.status_code == 200
    assert "Upcoming schedule" in dashboard.text


def _db_session(client: TestClient) -> Session:
    settings = client.app.state.settings
    engine = create_engine(
        settings.database_url,
        future=True,
        connect_args={"check_same_thread": False},
    )
    return Session(engine)


def _authenticate_client(client: TestClient) -> None:
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


def _close_client_generator(client_gen: Iterator[TestClient]) -> None:
    try:
        next(client_gen)
    except StopIteration:
        return
