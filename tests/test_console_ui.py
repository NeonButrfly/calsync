import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from calsync.config import get_settings
from calsync.db import _get_engine_for_url, _get_session_factory_for_url
from calsync.main import create_app
from calsync.models import Base
from calsync.services.appointments import AppointmentService
from calsync.services.apple_caldav import AppleCalDAVError


class FakeAppleClient:
    def create_event(self, **_: object):
        return type(
            "CreateResult",
            (),
            {
                "provider_event_id": "provider-created",
                "href": "https://caldav.icloud.com/calendar/provider-created.ics",
                "etag": '"etag-created"',
            },
        )()

    def update_event(self, **kwargs: object):
        return type(
            "UpdateResult",
            (),
            {
                "provider_event_id": kwargs["provider_event_id"],
                "href": kwargs.get("href")
                or "https://caldav.icloud.com/calendar/provider-created.ics",
                "etag": '"etag-updated"',
            },
        )()

    def cancel_event(self, **_: object) -> None:
        return None


class FailingAppleClient:
    def create_event(self, **_: object):
        raise AppleCalDAVError("Apple/iCloud authentication failed.")


def _configure_test_env(monkeypatch) -> None:
    db_path = Path(tempfile.gettempdir()) / f"calsync-ui-test-{uuid4()}.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("APPLE_ACCOUNT_LABEL", "Family")
    monkeypatch.setenv("APPLE_USERNAME", "family@example.com")
    monkeypatch.setenv("APPLE_APP_SPECIFIC_PASSWORD", "secret")
    monkeypatch.setenv(
        "APPLE_PRIMARY_CALENDAR_URL",
        "https://caldav.icloud.com/calendar/",
    )
    monkeypatch.setenv("APPLE_PRIMARY_CALENDAR_NAME", "Family")
    get_settings.cache_clear()
    _get_engine_for_url.cache_clear()
    _get_session_factory_for_url.cache_clear()
    Base.metadata.create_all(_get_engine_for_url(get_settings().database_url))


def test_console_root_renders_scheduler_surface(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    app = create_app()
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Add to calendars through CalSync" in response.text
    assert "New appointment" in response.text
    assert "What is on the calendar" in response.text


def test_console_create_flow_redirects_and_shows_created_appointment(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: FakeAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/appointments",
        data={
            "title": "Dentist",
            "date_value": "2026-06-01",
            "start_time": "10:00",
            "end_time": "11:00",
            "timezone": "America/Anchorage",
            "location": "Clinic",
            "notes": "Bring insurance card",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Appointment created on your Apple calendar." in response.text
    assert "Dentist" in response.text


def test_console_edit_flow_prefills_and_updates(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: FakeAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    create_response = client.post(
        "/api/appointments",
        json={
            "title": "Dentist",
            "date": "2026-06-01",
            "start_time": "10:00",
            "end_time": "11:00",
            "timezone": "America/Anchorage",
        },
    )
    appointment_id = create_response.json()["appointment_id"]

    edit_page = client.get(f"/appointments/{appointment_id}/edit")
    assert edit_page.status_code == 200
    assert "Update appointment" in edit_page.text
    assert "Dentist" in edit_page.text

    response = client.post(
        f"/appointments/{appointment_id}/edit",
        data={
            "title": "Dentist Follow-up",
            "date_value": "2026-06-01",
            "start_time": "10:30",
            "end_time": "11:30",
            "timezone": "America/Anchorage",
            "location": "",
            "notes": "",
            "attendees_text": "",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Appointment updated on your Apple calendar." in response.text
    assert "Dentist Follow-up" in response.text


def test_console_cancel_flow_marks_appointment_cancelled(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: FakeAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    create_response = client.post(
        "/api/appointments",
        json={
            "title": "Follow-up",
            "date": "2026-06-02",
            "start_time": "09:00",
            "end_time": "09:30",
            "timezone": "America/Anchorage",
        },
    )
    appointment_id = create_response.json()["appointment_id"]

    response = client.post(
        f"/appointments/{appointment_id}/cancel",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Appointment cancelled on your Apple calendar." in response.text
    assert "cancelled" in response.text


def test_console_surfaces_provider_failure(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: FailingAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/appointments",
        data={
            "title": "Dentist",
            "date_value": "2026-06-01",
            "start_time": "10:00",
            "end_time": "11:00",
            "timezone": "America/Anchorage",
        },
    )

    assert response.status_code == 400
    assert "Apple/iCloud authentication failed." in response.text
