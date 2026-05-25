from __future__ import annotations

from datetime import UTC, datetime, timedelta
from contextlib import contextmanager
from pathlib import Path

import pyotp
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from calsync.config import Settings
from calsync.main import create_app
from calsync.models import Base, Event
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


ENCRYPTION_KEY = "review-page-test-key"
SESSION_SECRET = "review-page-session-secret"


@contextmanager
def _build_client(tmp_path: Path):
    database_path = tmp_path / "review-page.sqlite3"
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
        upsert_event(
            session,
            _make_event(
                provider_type="google",
                provider_account_id="g-1",
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
                provider_account_id="i-1",
                provider_calendar_id="icloud-family",
                provider_event_id="evt-icloud",
                title="Orthodontist Appointment",
            ),
        )
        rebuild_duplicate_groups(session)
        session.commit()

    app = create_app(settings)
    app.state.test_totp_secret = totp_secret

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


def test_review_page_requires_authenticated_admin(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        response = client.get("/admin/review", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_review_page_lists_duplicate_groups_and_resolution_actions(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client)

        response = client.get("/admin/review")

    with _db_session(client) as session:
        groups = list_duplicate_groups(session)
        assert len(groups) == 1
        anchor_id = groups[0].anchor_id

    assert response.status_code == 200
    assert "Needs attention" in response.text
    assert "Possible duplicates" in response.text
    assert "Orthodontist Appointment" in response.text
    assert "Keep this copy" in response.text
    assert "CalSync is currently keeping" in response.text
    assert "Why this looks duplicated" in response.text
    assert f'id="{anchor_id}"' in response.text


def test_review_page_prefer_action_hides_other_duplicate(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client)

        with _db_session(client) as session:
            groups = list_duplicate_groups(session)
            assert len(groups) == 1
            preferred_id = groups[0].events[-1].id
            anchor_id = groups[0].anchor_id

        response = client.post(
            f"/admin/review/groups/{groups[0].group.id}/prefer/{preferred_id}",
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == f"/admin/review#{anchor_id}"

        with _db_session(client) as session:
            kept_event = session.get(Event, preferred_id)
            hidden_events = session.scalars(
                select(Event).where(
                    Event.canonical_group_id == groups[0].group.id,
                    Event.id != preferred_id,
                )
            ).all()

            assert kept_event is not None
            assert kept_event.event_visibility_state == "active"
            assert hidden_events
            assert all(event.event_visibility_state == "hidden_duplicate" for event in hidden_events)


def test_review_page_restore_all_action_restores_hidden_duplicates(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client)

        with _db_session(client) as session:
            groups = list_duplicate_groups(session)
            assert len(groups) == 1
            group_id = groups[0].group.id
            anchor_id = groups[0].anchor_id

        response = client.post(
            f"/admin/review/groups/{group_id}/restore-all",
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == f"/admin/review#{anchor_id}"

        with _db_session(client) as session:
            restored_events = session.scalars(
                select(Event).where(Event.canonical_group_id == group_id)
            ).all()

        assert restored_events
        assert all(event.event_visibility_state == "active" for event in restored_events)


def test_review_page_restore_single_duplicate_redirects_to_group_anchor(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client)

        with _db_session(client) as session:
            groups = list_duplicate_groups(session)
            assert len(groups) == 1
            hidden_event = next(
                event for event in groups[0].events if event.event_visibility_state == "hidden_duplicate"
            )
            anchor_id = groups[0].anchor_id

        response = client.post(
            f"/admin/review/events/{hidden_event.id}/restore",
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == f"/admin/review#{anchor_id}"


def test_review_page_ignores_old_duplicate_history_outside_attention_window(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client)

        old_start = datetime.now(UTC) - timedelta(days=120)
        old_end = old_start + timedelta(hours=1)

        with _db_session(client) as session:
            upsert_event(
                session,
                _make_event(
                    provider_type="google",
                    provider_account_id="old-google@example.com",
                    provider_calendar_id="old-google-cal",
                    provider_event_id="evt-old-google",
                    title="Old Cleanup Case",
                    starts_at=old_start,
                    ends_at=old_end,
                ),
            )
            upsert_event(
                session,
                _make_event(
                    provider_type="icloud_caldav",
                    provider_account_id="old-icloud@example.com",
                    provider_calendar_id="old-icloud-cal",
                    provider_event_id="evt-old-icloud",
                    title="Old Cleanup Case",
                    starts_at=old_start,
                    ends_at=old_end,
                ),
            )
            rebuild_duplicate_groups(session)
            session.commit()

        response = client.get("/admin/review")

    assert response.status_code == 200
    assert "Old Cleanup Case" not in response.text


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
