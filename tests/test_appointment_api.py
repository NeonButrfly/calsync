import tempfile
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from fastapi.testclient import TestClient

from calsync.config import get_settings
from calsync.db import _get_engine_for_url, _get_session_factory_for_url
from calsync.main import create_app
from calsync.models import AuditEntry, Base
from calsync.services.apple_caldav import AppleCalDAVError
from calsync.services.appointments import AppointmentService


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


class DuplicateSyncingAppleClient(FakeAppleClient):
    def list_events(self, **_: object):
        event = type(
            "ListedEvent",
            (),
            {
                "provider_event_id": "provider-duplicate",
                "href": "https://caldav.icloud.com/calendar/provider-duplicate.ics",
                "etag": '"etag-duplicate"',
                "title": "Duplicate Provider Event",
                "starts_at": "2026-06-11T09:00:00-08:00",
                "ends_at": "2026-06-11T09:45:00-08:00",
                "all_day": False,
                "location": "School office",
                "notes": "Should only appear once",
                "status": "confirmed",
            },
        )()
        return [event, event]


class FailingAppleClient:
    def create_event(self, **_: object):
        raise AppleCalDAVError("Apple/iCloud authentication failed.")


def _configure_test_env(monkeypatch) -> None:
    db_path = Path(tempfile.gettempdir()) / f"calsync-test-{uuid4()}.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path.as_posix()}")
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


def test_create_appointment_returns_local_id(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: FakeAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/appointments",
        json={
            "title": "Dentist",
            "date": "2026-06-01",
            "start_time": "10:00",
            "end_time": "11:00",
            "timezone": "America/Anchorage",
            "all_day": False,
            "location": "Clinic",
            "notes": "Bring insurance card",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "active"
    assert body["appointment_id"]
    assert body["provider_event_id"] == "provider-created"


def test_list_appointments_returns_matching_date_window(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: FakeAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    client.post(
        "/api/appointments",
        json={
            "title": "Dentist",
            "date": "2026-06-01",
            "start_time": "10:00",
            "end_time": "11:00",
            "timezone": "America/Anchorage",
            "all_day": False,
        },
    )
    response = client.get(
        "/api/appointments?date_from=2026-06-01&date_to=2026-06-02"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    assert body["items"][0]["title"] == "Dentist"


def test_list_appointments_uses_appointment_local_date_window(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: FakeAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    client.post(
        "/api/appointments",
        json={
            "title": "Evening Visit",
            "date": "2026-06-01",
            "start_time": "18:00",
            "end_time": "19:00",
            "timezone": "America/Anchorage",
            "all_day": False,
        },
    )

    response = client.get(
        "/api/appointments?date_from=2026-06-01&date_to=2026-06-01"
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["title"] for item in body["items"]] == ["Evening Visit"]


def test_list_appointments_syncs_existing_apple_events(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: SyncingAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    response = client.get(
        "/api/appointments?date_from=2026-06-10&date_to=2026-06-10"
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["title"] for item in body["items"]] == ["Existing School Visit"]
    assert body["items"][0]["location"] == "School office"


def test_list_appointments_deduplicates_provider_events_within_sync_response(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: DuplicateSyncingAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    response = client.get(
        "/api/appointments?date_from=2026-06-11&date_to=2026-06-11"
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["provider_event_id"] for item in body["items"]] == [
        "provider-duplicate"
    ]


def test_create_appointment_uses_forwarded_channel_as_actor(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: FakeAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/appointments",
        headers={"X-CalSync-Channel": "chatgpt"},
        json={
            "title": "Therapy",
            "date": "2026-06-03",
            "start_time": "09:00",
            "end_time": "10:00",
            "timezone": "America/Anchorage",
        },
    )

    assert response.status_code == 201
    session_factory = _get_session_factory_for_url(get_settings().database_url)
    with session_factory() as session:
        audit_entry = session.scalar(
            select(AuditEntry).order_by(AuditEntry.created_at.desc())
        )
    assert audit_entry is not None
    assert audit_entry.actor == "worker:chatgpt"


def test_get_appointment_returns_detail_and_audit_trail(monkeypatch) -> None:
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
            "title": "Speech Evaluation",
            "date": "2026-06-04",
            "start_time": "14:00",
            "end_time": "15:00",
            "timezone": "America/Anchorage",
            "location": "School",
        },
    )
    appointment_id = create_response.json()["appointment_id"]

    response = client.get(f"/api/appointments/{appointment_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["appointment_id"] == appointment_id
    assert body["calendar_name"] == "Family"
    assert body["provider_type"] == "icloud_caldav"
    assert body["audit_entries"][0]["action"] == "create_appointment"


def test_cancel_appointment_marks_status_cancelled(monkeypatch) -> None:
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
            "all_day": False,
        },
    )
    appointment_id = create_response.json()["appointment_id"]

    cancel_response = client.post(f"/api/appointments/{appointment_id}/cancel")

    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"


def test_list_appointments_hides_cancelled_by_default_but_can_include_them(monkeypatch) -> None:
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
            "title": "Family follow-up",
            "date": "2026-06-02",
            "start_time": "09:00",
            "end_time": "09:30",
            "timezone": "America/Anchorage",
            "all_day": False,
        },
    )
    appointment_id = create_response.json()["appointment_id"]
    cancel_response = client.post(f"/api/appointments/{appointment_id}/cancel")

    assert cancel_response.status_code == 200

    hidden_response = client.get(
        "/api/appointments?date_from=2026-06-02&date_to=2026-06-02"
    )
    assert hidden_response.status_code == 200
    assert hidden_response.json()["items"] == []

    included_response = client.get(
        "/api/appointments?date_from=2026-06-02&date_to=2026-06-02&include_cancelled=true"
    )
    assert included_response.status_code == 200
    assert [item["title"] for item in included_response.json()["items"]] == [
        "Family follow-up"
    ]
    assert included_response.json()["items"][0]["status"] == "cancelled"


def test_cancel_appointment_can_target_synced_apple_event(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: SyncingAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    sync_response = client.get(
        "/api/appointments?date_from=2026-06-10&date_to=2026-06-10"
    )
    appointment_id = sync_response.json()["items"][0]["appointment_id"]

    cancel_response = client.post(f"/api/appointments/{appointment_id}/cancel")

    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"
    detail_response = client.get(f"/api/appointments/{appointment_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["status"] == "cancelled"


def test_update_and_cancel_use_forwarded_channel_as_actor(monkeypatch) -> None:
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

    update_response = client.patch(
        f"/api/appointments/{appointment_id}",
        headers={"X-CalSync-Channel": "alexa"},
        json={"location": "Downtown clinic"},
    )
    cancel_response = client.post(
        f"/api/appointments/{appointment_id}/cancel",
        headers={"X-CalSync-Channel": "shortcuts"},
    )

    assert update_response.status_code == 200
    assert cancel_response.status_code == 200

    session_factory = _get_session_factory_for_url(get_settings().database_url)
    with session_factory() as session:
        audit_entries = list(
            session.scalars(select(AuditEntry).order_by(AuditEntry.created_at.asc()))
        )

    assert [entry.actor for entry in audit_entries] == [
        "api",
        "worker:alexa",
        "worker:shortcuts",
    ]


def test_create_appointment_surfaces_provider_failure(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: FailingAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/appointments",
        json={
            "title": "Dentist",
            "date": "2026-06-01",
            "start_time": "10:00",
            "end_time": "11:00",
            "timezone": "America/Anchorage",
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Apple/iCloud authentication failed."
