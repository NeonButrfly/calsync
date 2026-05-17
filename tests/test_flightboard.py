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

        enabled_calendar = session.scalar(
            select(ProviderCalendar).where(
                ProviderCalendar.provider_account_pk == account.id,
                ProviderCalendar.provider_calendar_id == "work",
            )
        )
        assert enabled_calendar is not None

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
        session.add_all(
            [
                Event(
                    provider_type=account.provider_type,
                    provider_account_id=account.provider_account_id,
                    provider_calendar_id=enabled_calendar.provider_calendar_id,
                    provider_event_id="passed-local-event",
                    provider_account_pk=account.id,
                    provider_calendar_pk=enabled_calendar.id,
                    title="Past Incident Review",
                    description="Should stay hidden once it has ended.",
                    location="Archive Room",
                    starts_at=datetime(2026, 5, 14, 15, 0, tzinfo=UTC),
                    ends_at=datetime(2026, 5, 14, 16, 0, tzinfo=UTC),
                    all_day=False,
                    status="confirmed",
                    source_payload={"calendar": "work", "seed": "past-local"},
                ),
                Event(
                    provider_type=account.provider_type,
                    provider_account_id=account.provider_account_id,
                    provider_calendar_id=enabled_calendar.provider_calendar_id,
                    provider_event_id="day-local-event",
                    provider_account_pk=account.id,
                    provider_calendar_pk=enabled_calendar.id,
                    title="Today Dispatch Briefing",
                    description="Same-day event for the day board.",
                    location="North Ramp",
                    starts_at=datetime(2026, 5, 15, 18, 0, tzinfo=UTC),
                    ends_at=datetime(2026, 5, 15, 19, 0, tzinfo=UTC),
                    all_day=False,
                    status="confirmed",
                    source_payload={"calendar": "work", "seed": "day-local"},
                ),
                Event(
                    provider_type=account.provider_type,
                    provider_account_id=account.provider_account_id,
                    provider_calendar_id=enabled_calendar.provider_calendar_id,
                    provider_event_id="week-local-event",
                    provider_account_pk=account.id,
                    provider_calendar_pk=enabled_calendar.id,
                    title="Week Planning Window",
                    description="Inside the weekly horizon.",
                    location="Hangar West",
                    starts_at=datetime(2026, 5, 20, 18, 0, tzinfo=UTC),
                    ends_at=datetime(2026, 5, 20, 19, 0, tzinfo=UTC),
                    all_day=False,
                    status="confirmed",
                    source_payload={"calendar": "work", "seed": "week-local"},
                ),
                Event(
                    provider_type=account.provider_type,
                    provider_account_id=account.provider_account_id,
                    provider_calendar_id=enabled_calendar.provider_calendar_id,
                    provider_event_id="month-local-event",
                    provider_account_pk=account.id,
                    provider_calendar_pk=enabled_calendar.id,
                    title="Month Launch Rehearsal",
                    description="Inside the monthly horizon.",
                    location="South Deck",
                    starts_at=datetime(2026, 6, 5, 18, 0, tzinfo=UTC),
                    ends_at=datetime(2026, 6, 5, 19, 0, tzinfo=UTC),
                    all_day=False,
                    status="confirmed",
                    source_payload={"calendar": "work", "seed": "month-local"},
                ),
                Event(
                    provider_type=account.provider_type,
                    provider_account_id=account.provider_account_id,
                    provider_calendar_id=enabled_calendar.provider_calendar_id,
                    provider_event_id="far-local-event",
                    provider_account_pk=account.id,
                    provider_calendar_pk=enabled_calendar.id,
                    title="Far Future Checkpoint",
                    description="Outside the monthly horizon.",
                    location="Remote Dock",
                    starts_at=datetime(2026, 7, 1, 18, 0, tzinfo=UTC),
                    ends_at=datetime(2026, 7, 1, 19, 0, tzinfo=UTC),
                    all_day=False,
                    status="confirmed",
                    source_payload={"calendar": "work", "seed": "far-local"},
                ),
            ]
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        flightboard_routes,
        "_flightboard_now",
        lambda: datetime(2026, 5, 15, 12, 0, tzinfo=UTC),
    )
    response = authenticated_client.get("/admin/flightboard")

    assert response.status_code == 200
    assert "Today Dispatch Briefing" in response.text
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
    assert "North Ramp" in response.text
    assert "Fri May 15 at 10:00 AM AKST" in response.text
    assert re.search(
        r"Soon\s*</span>\s*<p class=\"flightboard-time\">Fri May 15 at 10:00 AM AKST</p>"
        r"\s*<div class=\"flightboard-event\">\s*<strong>Today Dispatch Briefing</strong>"
        r"\s*<span>Mock Account . Work</span>",
        response.text,
        re.DOTALL,
    )
    assert re.search(
        r"Later\s*</span>\s*<p class=\"flightboard-time\">Wed May 20 at 10:00 AM AKST</p>"
        r"\s*<div class=\"flightboard-event\">\s*<strong>Week Planning Window</strong>",
        response.text,
        re.DOTALL,
    )


def test_flightboard_excludes_events_that_have_already_ended(
    authenticated_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        flightboard_routes,
        "_flightboard_now",
        lambda: datetime(2026, 5, 15, 12, 0, tzinfo=UTC),
    )

    response = authenticated_client.get("/admin/flightboard")

    assert response.status_code == 200
    assert "Past Incident Review" not in response.text
    assert "Today Dispatch Briefing" in response.text


def test_flightboard_converts_utc_calendar_times_to_alaska_display(
    authenticated_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Session(
        create_engine(
            authenticated_client.app.state.settings.database_url,
            future=True,
            connect_args={"check_same_thread": False},
        )
    ) as session:
        shared_calendar = session.scalar(
            select(ProviderCalendar).where(
                ProviderCalendar.provider_calendar_id == "shared",
            )
        )
        assert shared_calendar is not None
        shared_calendar.enabled = True
        session.commit()

    monkeypatch.setattr(
        flightboard_routes,
        "_flightboard_now",
        lambda: datetime(2026, 5, 15, 12, 0, tzinfo=UTC),
    )

    response = authenticated_client.get("/admin/flightboard?view=week")

    assert response.status_code == 200
    assert "Community Game Night" in response.text
    assert "Fri May 15 at 6:00 PM AKST" in response.text
    assert "UTC" not in response.text


def test_flightboard_day_week_and_month_views_filter_the_horizon(
    authenticated_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        flightboard_routes,
        "_flightboard_now",
        lambda: datetime(2026, 5, 15, 12, 0, tzinfo=UTC),
    )

    day_response = authenticated_client.get("/admin/flightboard?view=day")
    week_response = authenticated_client.get("/admin/flightboard?view=week")
    month_response = authenticated_client.get("/admin/flightboard?view=month")

    assert day_response.status_code == 200
    assert "Today Dispatch Briefing" in day_response.text
    assert "Week Planning Window" not in day_response.text
    assert "Month Launch Rehearsal" not in day_response.text

    assert week_response.status_code == 200
    assert "Today Dispatch Briefing" in week_response.text
    assert "Week Planning Window" in week_response.text
    assert "Month Launch Rehearsal" not in week_response.text

    assert month_response.status_code == 200
    assert "Today Dispatch Briefing" in month_response.text
    assert "Week Planning Window" in month_response.text
    assert "Month Launch Rehearsal" in month_response.text
    assert "Far Future Checkpoint" not in month_response.text


def test_flightboard_renders_view_controls_and_autoscroll_hook(
    authenticated_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        flightboard_routes,
        "_flightboard_now",
        lambda: datetime(2026, 5, 15, 12, 0, tzinfo=UTC),
    )

    response = authenticated_client.get("/admin/flightboard?view=month")

    assert response.status_code == 200
    assert 'href="/admin/flightboard?view=day"' in response.text
    assert 'href="/admin/flightboard?view=week"' in response.text
    assert 'href="/admin/flightboard?view=month"' in response.text
    assert 'flightboard-view-toggle--active' in response.text
    assert 'data-flightboard-autoscroll="true"' in response.text
    assert 'data-flightboard-clone="true"' in response.text
    assert "prefers-reduced-motion" not in response.text
