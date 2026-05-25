from __future__ import annotations

from contextlib import contextmanager
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
from calsync.services.sync import discover_calendars, sync_account


ENCRYPTION_KEY = "problem-page-test-key"
SESSION_SECRET = "problem-page-session-secret"


@contextmanager
def _build_client(tmp_path: Path):
    database_path = tmp_path / "problem-page.sqlite3"
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

        mock_account = ProviderAccount(
            provider_type="mock",
            provider_account_id="mock-acct-1",
            display_name="Mock Account",
            provider_metadata={"seed": "problem-page"},
        )
        session.add(mock_account)
        session.flush()
        mock_account_id = mock_account.id
        discover_calendars(session, mock_account.id)
        sync_account(session, mock_account.id, trigger="manual")

        google_account = ProviderAccount(
            provider_type="google",
            provider_account_id="google-user@example.com",
            display_name="Google Household",
            provider_metadata={
                "google_auth_status": "reconnect_required",
                "google_reconnect_required": True,
                "google_last_auth_error": "Google access refresh failed. Reconnect the account.",
            },
        )
        session.add(google_account)
        session.flush()

        icloud_account = ProviderAccount(
            provider_type="icloud_caldav",
            provider_account_id="icloud-user@icloud.com",
            display_name="iCloud Household",
            provider_metadata={},
        )
        session.add(icloud_account)
        session.flush()

        source_event = session.scalar(select(Event).where(Event.provider_event_id == "home-standup"))
        assert source_event is not None
        upsert_event(
            session,
            {
                "provider_type": "google",
                "provider_account_id": "google-user@example.com",
                "provider_calendar_id": "google-primary",
                "provider_event_id": "problem-duplicate",
                "title": f"{source_event.title} Appointment",
                "starts_at": source_event.starts_at,
                "ends_at": source_event.ends_at,
                "all_day": source_event.all_day,
                "status": "confirmed",
                "location": source_event.location,
                "source_payload": {"seed": "problem-page-duplicate"},
            },
        )
        upsert_event(
            session,
            {
                "provider_type": "icloud_caldav",
                "provider_account_id": "icloud-user@icloud.com",
                "provider_calendar_id": "icloud-family",
                "provider_event_id": "problem-duplicate-icloud",
                "title": source_event.title,
                "starts_at": source_event.starts_at,
                "ends_at": source_event.ends_at,
                "all_day": source_event.all_day,
                "status": "confirmed",
                "location": source_event.location,
                "source_payload": {"seed": "problem-page-duplicate-icloud"},
            },
        )
        rebuild_duplicate_groups(session)
        session.commit()

    app = create_app(settings)
    app.state.test_totp_secret = totp_secret
    app.state.test_mock_account_id = mock_account_id

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


def test_problem_page_requires_authenticated_admin(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        response = client.get("/admin/problems", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_problem_page_lists_duplicate_and_reconnect_items(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client)
        response = client.get("/admin/problems")

    assert response.status_code == 200
    assert "Fix what needs attention" in response.text
    assert "Possible duplicate appointment" in response.text
    assert "Google account needs reconnection" in response.text
    assert "Resolve duplicate" in response.text
    assert "Reconnect in accounts" in response.text
    assert "CalSync recommends keeping" in response.text


def test_problem_page_lists_provider_specific_duplicate_actions(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client)
        response = client.get("/admin/problems")

    assert response.status_code == 200
    assert "Keep Google copy" in response.text
    assert "Keep iCloud copy" in response.text
    assert "Show all copies" in response.text
    assert "Explain this event" in response.text
    assert "Preferred now" in response.text
    with _db_session(client) as session:
        duplicate_group = list_duplicate_groups(session)[0]
        duplicate_group_id = duplicate_group.group.id
        preferred_event_id = duplicate_group.group.preferred_event_id
        anchor_id = duplicate_group.anchor_id
        hidden_event = session.scalar(select(Event).where(Event.canonical_group_id == duplicate_group_id, Event.event_visibility_state == "hidden_duplicate"))
        google_copy = session.scalar(select(Event).where(Event.canonical_group_id == duplicate_group_id, Event.provider_type == "google"))
        icloud_copy = session.scalar(select(Event).where(Event.canonical_group_id == duplicate_group_id, Event.provider_type == "icloud_caldav"))
        google_copy_id = google_copy.id if google_copy is not None else None
        icloud_copy_id = icloud_copy.id if icloud_copy is not None else None

    assert google_copy_id is not None
    assert icloud_copy_id is not None
    assert preferred_event_id is not None
    assert hidden_event is not None
    assert f'<form method="post" action="/admin/problems/actions/event/{preferred_event_id}/provider/google">' in response.text
    assert f'<form method="post" action="/admin/problems/actions/event/{preferred_event_id}/provider/icloud_caldav">' in response.text
    assert f'<form method="post" action="/admin/problems/actions/event/{preferred_event_id}/show-both">' in response.text
    assert f'<a class="button-link button-link--secondary" href="/admin/events/{preferred_event_id}">Explain this event</a>' in response.text


def test_problem_page_hides_provider_specific_action_when_provider_copy_missing(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client)

        with _db_session(client) as session:
            google_copy = session.scalar(select(Event).where(Event.provider_type == "google"))
            assert google_copy is not None
            session.delete(google_copy)
            rebuild_duplicate_groups(session)
            session.commit()

        response = client.get("/admin/problems")

    assert response.status_code == 200
    assert "Keep Google copy" not in response.text


def test_problem_page_sync_action_retries_account_and_returns_to_inbox(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client)

        with _db_session(client) as session:
            account = session.scalar(select(ProviderAccount).where(ProviderAccount.provider_type == "mock"))
            assert account is not None
            latest_log = session.scalar(
                select(SyncLog)
                .where(SyncLog.provider_account_pk == account.id)
                .order_by(SyncLog.started_at.desc(), SyncLog.id.desc())
            )
            assert latest_log is not None
            latest_log.status = "error"
            latest_log.error_text = "Mock provider sync stalled."
            session.commit()
            before_count = session.query(SyncLog).count()

        response = client.post(
            f"/admin/problems/actions/sync/{client.app.state.test_mock_account_id}",
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/problems"

        with _db_session(client) as session:
            logs = session.scalars(select(SyncLog).order_by(SyncLog.started_at, SyncLog.id)).all()
            assert len(logs) == before_count + 1
            assert logs[-1].status == "success"


def test_problem_page_can_keep_google_copy(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client)

        with _db_session(client) as session:
            duplicate_group = list_duplicate_groups(session)[0]
            preferred_event_id = duplicate_group.group.preferred_event_id
            google_copy = session.scalar(
                select(Event).where(
                    Event.canonical_group_id == duplicate_group.group.id,
                    Event.provider_type == "google",
                )
            )
            anchor_id = duplicate_group.anchor_id
            assert preferred_event_id is not None
            assert google_copy is not None

        response = client.post(
            f"/admin/problems/actions/event/{preferred_event_id}/provider/google",
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == f"/admin/problems#{anchor_id}"

        with _db_session(client) as session:
            refreshed_google = session.get(Event, google_copy.id)
            assert refreshed_google is not None
            assert refreshed_google.event_visibility_state == "active"


def test_problem_page_show_all_action_restores_hidden_duplicates_and_lands_on_stable_anchor(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client)

        with _db_session(client) as session:
            duplicate_group = list_duplicate_groups(session)[0]
            preferred_event_id = duplicate_group.group.preferred_event_id
            anchor_id = duplicate_group.anchor_id
            assert preferred_event_id is not None
            grouped_event_ids = [
                event.id
                for event in session.scalars(
                    select(Event).where(Event.canonical_group_id == duplicate_group.group.id)
                ).all()
            ]

        action_response = client.post(
            f"/admin/problems/actions/event/{preferred_event_id}/show-both",
            follow_redirects=False,
        )

        assert action_response.status_code == 303
        assert action_response.headers["location"] == f"/admin/problems#{anchor_id}"

        page_response = client.get(action_response.headers["location"])
        assert page_response.status_code == 200
        assert f'id="{anchor_id}"' in page_response.text

        with _db_session(client) as session:
            restored_events = [session.get(Event, event_id) for event_id in grouped_event_ids]

        assert restored_events
        assert all(event is not None and event.event_visibility_state == "active" for event in restored_events)


def test_problem_page_links_duplicate_items_to_event_explain_view(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client)
        response = client.get("/admin/problems")

    assert response.status_code == 200
    assert "/admin/events/" in response.text
    assert "Explain this event" in response.text


def _db_session(client: TestClient) -> Session:
    settings = client.app.state.settings
    engine = create_engine(
        settings.database_url,
        future=True,
        connect_args={"check_same_thread": False},
    )
    return Session(engine)
