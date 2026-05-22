from __future__ import annotations

from datetime import UTC, datetime
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

    assert response.status_code == 200
    assert "Needs attention" in response.text
    assert "Possible duplicates" in response.text
    assert "Orthodontist Appointment" in response.text
    assert "Keep this copy" in response.text


def test_review_page_prefer_action_hides_other_duplicate(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client)

        with _db_session(client) as session:
            groups = list_duplicate_groups(session)
            assert len(groups) == 1
            preferred_id = groups[0].events[-1].id

        response = client.post(
            f"/admin/review/groups/{groups[0].group.id}/prefer/{preferred_id}",
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/review"

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
