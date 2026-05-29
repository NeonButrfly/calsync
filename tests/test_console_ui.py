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


class SyncingAppleClient(FakeAppleClient):
    def list_events(self, **_: object):
        return [
            type(
                "ListedEvent",
                (),
                {
                    "provider_event_id": "provider-existing",
                    "href": "https://caldav.icloud.com/calendar/provider-existing.ics",
                    "etag": '"etag-existing"',
                    "title": "Existing School Visit",
                    "starts_at": "2026-06-10T09:00:00-08:00",
                    "ends_at": "2026-06-10T09:45:00-08:00",
                    "all_day": False,
                    "location": "School office",
                    "notes": "Already on the family calendar",
                    "status": "confirmed",
                },
            )()
        ]


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
    assert "See the household schedule clearly" in response.text
    assert "New appointment" in response.text
    assert "Calendar view" in response.text
    assert "Details that actually help" in response.text
    assert "System readiness" in response.text


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
    assert "Activity trail" in response.text


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
    assert "Today" in edit_page.text

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
    assert "Follow-up" not in response.text


def test_console_hides_cancelled_by_default_but_can_show_them_for_reference(monkeypatch) -> None:
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
            "title": "Cancelled consult",
            "date": "2026-06-03",
            "start_time": "11:00",
            "end_time": "11:30",
            "timezone": "America/Anchorage",
        },
    )
    appointment_id = create_response.json()["appointment_id"]
    client.post(f"/api/appointments/{appointment_id}/cancel")

    active_response = client.get("/?view=month")
    assert active_response.status_code == 200
    assert "Cancelled consult" not in active_response.text

    reference_response = client.get("/?view=month&show_cancelled=1")
    assert reference_response.status_code == 200
    assert "Cancelled consult" in reference_response.text
    assert "Showing cancelled appointments for reference." in reference_response.text


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


def test_public_policy_pages_render(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    app = create_app()
    client = TestClient(app)

    privacy_response = client.get("/privacy")
    terms_response = client.get("/terms")

    assert privacy_response.status_code == 200
    assert "Privacy Policy" in privacy_response.text
    assert "shared scheduling workspace" in privacy_response.text

    assert terms_response.status_code == 200
    assert "Terms of Use" in terms_response.text
    assert "shared brain" in terms_response.text


def test_alexa_setup_page_renders_operator_steps(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    app = create_app()
    client = TestClient(app)

    response = client.get("/alexa/setup")

    assert response.status_code == 200
    assert "Alexa setup" in response.text
    assert "Download skill package" in response.text
    assert "https://edge-calsync.neonbutterfly.net/alexa" in response.text


def test_console_supports_window_filters_and_selected_detail(monkeypatch) -> None:
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
            "title": "Summer camp intake",
            "date": "2026-06-12",
            "start_time": "08:30",
            "end_time": "09:15",
            "timezone": "America/Anchorage",
            "notes": "Bring forms",
        },
    )
    appointment_id = create_response.json()["appointment_id"]

    response = client.get(f"/?view=month&appointment_id={appointment_id}")

    assert response.status_code == 200
    assert "Next 30 days" in response.text
    assert "Summer camp intake" in response.text
    assert "What CalSync has done with this appointment" in response.text
    assert "Bring forms" in response.text


def test_console_root_shows_existing_synced_apple_events(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: SyncingAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    response = client.get("/?view=month")

    assert response.status_code == 200
    assert "Existing School Visit" in response.text
    assert "School office" in response.text
