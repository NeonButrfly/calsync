from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from calsync.config import Settings
from calsync.main import create_app
from calsync.models import Base, Event, ProviderAccount, ProviderCalendar
from calsync.repos.state import set_app_state
from calsync.repos.users import create_admin_user
from calsync.services.auth import (
    generate_recovery_codes,
    hash_password,
    store_recovery_codes,
    store_totp_secret,
)
from calsync.services.sync import discover_calendars, sync_account
from calsync.web.routes import flightboard as flightboard_routes


ENCRYPTION_KEY = "phase1-flightboard-test-key"
SESSION_SECRET = "phase1-flightboard-session-secret"


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    yield from _build_client(tmp_path)


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


def _build_client(tmp_path: Path) -> TestClient:
    database_path = tmp_path / "flightboard.sqlite3"
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
            provider_metadata={"seed": "flightboard"},
        )
        session.add(account)
        session.flush()
        discover_calendars(session, account.id)
        sync_account(session, account.id, trigger="manual")

        disabled_calendar = session.scalar(
            select(ProviderCalendar).where(
                ProviderCalendar.provider_account_pk == account.id,
                ProviderCalendar.provider_calendar_id == "shared",
            )
        )
        assert disabled_calendar is not None
        disabled_calendar.enabled = False
        session.add(disabled_calendar)
        session.flush()

        disabled_event_start = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)
        session.add(
            Event(
                provider_type=account.provider_type,
                provider_account_id=account.provider_account_id,
                provider_calendar_id=disabled_calendar.provider_calendar_id,
                provider_event_id="disabled-local-event",
                provider_account_pk=account.id,
                provider_calendar_pk=disabled_calendar.id,
                title="Disabled Calendar Event",
                description="Should stay hidden from the flightboard.",
                location="Hidden Room",
                starts_at=disabled_event_start,
                ends_at=disabled_event_start + timedelta(hours=1),
                all_day=False,
                status="confirmed",
                source_payload={"calendar": "work", "seed": "disabled-local"},
            )
        )
        session.commit()

    app = create_app(settings)
    app.state.test_totp_secret = totp_secret

    with TestClient(app) as test_client:
        yield test_client


def test_flightboard_requires_authenticated_admin(client: TestClient) -> None:
    response = client.get("/admin/flightboard", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_flightboard_shows_only_enabled_calendar_events(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.get("/admin/flightboard")

    assert response.status_code == 200
    assert "Morning Standup" in response.text
    assert "Disabled Calendar Event" not in response.text


def test_flightboard_renders_calendar_name_location_and_status(
    authenticated_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        flightboard_routes,
        "_flightboard_now",
        lambda: datetime(2026, 5, 15, 1, 30, tzinfo=UTC),
    )
    response = authenticated_client.get("/admin/flightboard")

    assert response.status_code == 200
    assert "Mock Account" in response.text
    assert "Conference Room A" in response.text
    assert "Fri May 15 at 2:00 PM AKDT" in response.text
    assert re.search(
        r"Now\s*</span>\s*<p class=\"flightboard-time\">Thu May 14 at 9:00 AM AKDT</p>"
        r"\s*<div class=\"flightboard-event\">\s*<strong>Sprint Planning</strong>"
        r"\s*<span>Mock Account . Work</span>",
        response.text,
        re.DOTALL,
    )
    assert re.search(
        r"Soon\s*</span>\s*<p class=\"flightboard-time\">Fri May 15 at 2:00 PM AKDT</p>"
        r"\s*<div class=\"flightboard-event\">\s*<strong>Demo Review</strong>",
        response.text,
        re.DOTALL,
    )
