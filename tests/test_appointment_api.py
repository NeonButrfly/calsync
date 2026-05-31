import base64
import hashlib
import tempfile
from pathlib import Path
from uuid import uuid4

from cryptography.fernet import Fernet
from sqlalchemy import select
from fastapi.testclient import TestClient

from calsync.config import get_settings
from calsync.db import _get_engine_for_url, _get_session_factory_for_url
from calsync.main import create_app
from calsync.models import AuditEntry, Base
from calsync.schemas.appointments import AppointmentResponse
from calsync.services.apple_caldav import AppleCalDAVError
from calsync.services.appointments import AppointmentService
from calsync.services.operator_settings import OperatorSettingsService


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


class MultiCalendarSyncingAppleClient(FakeAppleClient):
    def __init__(self, calendar_url: str | None) -> None:
        self.calendar_url = calendar_url or ""

    def list_events(self, **_: object):
        if self.calendar_url.endswith("/school/"):
            return [
                type(
                    "ListedEvent",
                    (),
                    {
                        "provider_event_id": "provider-school",
                        "href": "https://caldav.icloud.com/school/provider-school.ics",
                        "etag": '"etag-school"',
                        "title": "School assembly",
                        "starts_at": "2026-06-12T09:00:00-08:00",
                        "ends_at": "2026-06-12T10:00:00-08:00",
                        "all_day": False,
                        "location": "School gym",
                        "notes": "Arrive early",
                        "status": "confirmed",
                    },
                )()
            ]
        return [
            type(
                "ListedEvent",
                (),
                {
                    "provider_event_id": "provider-family",
                    "href": "https://caldav.icloud.com/family/provider-family.ics",
                    "etag": '"etag-family"',
                    "title": "Family dinner",
                    "starts_at": "2026-06-12T18:00:00-08:00",
                    "ends_at": "2026-06-12T19:00:00-08:00",
                    "all_day": False,
                    "location": "Home",
                    "notes": "Pizza night",
                    "status": "confirmed",
                },
            )()
        ]


class FailingAppleClient:
    def create_event(self, **_: object):
        raise AppleCalDAVError("Apple/iCloud authentication failed.")


class FakeGoogleClient:
    def create_event(self, **kwargs: object):
        calendar_id = str(kwargs.get("calendar_id") or "primary")
        return type(
            "CreateResult",
            (),
            {
                "provider_event_id": "google-created",
                "href": f"google:{calendar_id}:google-created",
                "etag": '"google-etag-created"',
            },
        )()

    def update_event(self, **kwargs: object):
        calendar_id = str(kwargs.get("calendar_id") or "primary")
        provider_event_id = str(kwargs.get("provider_event_id") or "google-created")
        return type(
            "UpdateResult",
            (),
            {
                "provider_event_id": provider_event_id,
                "href": f"google:{calendar_id}:{provider_event_id}",
                "etag": '"google-etag-updated"',
            },
        )()

    def cancel_event(self, **_: object) -> None:
        return None

    def list_events(self, **_: object):
        return [
            type(
                "ListedEvent",
                (),
                {
                    "provider_event_id": "google-existing",
                    "href": "google:primary:google-existing",
                    "etag": '"google-etag-existing"',
                    "title": "Google School Visit",
                    "starts_at": "2026-06-15T11:00:00-08:00",
                    "ends_at": "2026-06-15T12:00:00-08:00",
                    "all_day": False,
                    "location": "Google campus",
                    "notes": "Imported from Google",
                    "status": "confirmed",
                    "attendees_text": "Kay, Teacher",
                },
            )()
        ]


class FakeMicrosoftClient:
    def create_event(self, **kwargs: object):
        calendar_id = str(kwargs.get("calendar_id") or "primary")
        return type(
            "CreateResult",
            (),
            {
                "provider_event_id": "microsoft-created",
                "href": f"microsoft:{calendar_id}:microsoft-created",
                "etag": '"microsoft-etag-created"',
            },
        )()

    def update_event(self, **kwargs: object):
        calendar_id = str(kwargs.get("calendar_id") or "primary")
        provider_event_id = str(kwargs.get("provider_event_id") or "microsoft-created")
        return type(
            "UpdateResult",
            (),
            {
                "provider_event_id": provider_event_id,
                "href": f"microsoft:{calendar_id}:{provider_event_id}",
                "etag": '"microsoft-etag-updated"',
            },
        )()

    def cancel_event(self, **_: object) -> None:
        return None

    def list_events(self, **_: object):
        return [
            type(
                "ListedEvent",
                (),
                {
                    "provider_event_id": "microsoft-existing",
                    "href": "microsoft:primary:microsoft-existing",
                    "etag": '"microsoft-etag-existing"',
                    "title": "Outlook School Visit",
                    "starts_at": "2026-06-16T11:00:00-08:00",
                    "ends_at": "2026-06-16T12:00:00-08:00",
                    "all_day": False,
                    "location": "Microsoft campus",
                    "notes": "Imported from Outlook",
                    "status": "confirmed",
                    "attendees_text": "Kay, Counselor",
                },
            )()
        ]


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


def _configure_google_settings() -> None:
    service = OperatorSettingsService(settings=get_settings())
    service.set_google_oauth_settings(
        client_id="google-client-id",
        client_secret="google-client-secret",
    )
    service.set_google_account_settings(
        account_label="Kay Google",
        account_email="kay@example.com",
        refresh_token="google-refresh-token",
    )
    service.set_google_calendar_catalog(
        [
            {
                "calendar_name": "Primary",
                "calendar_id": "primary",
                "is_default": True,
            }
        ]
    )


def _configure_multiple_google_accounts() -> None:
    service = OperatorSettingsService(settings=get_settings())
    service.set_google_oauth_settings(
        client_id="google-client-id",
        client_secret="google-client-secret",
    )
    service.upsert_google_account(
        account_label="Kay Google",
        account_email="kay@example.com",
        refresh_token="kay-refresh-token",
        calendars=[
            {
                "calendar_name": "Primary",
                "calendar_id": "primary",
                "is_default": True,
            }
        ],
    )
    service.upsert_google_account(
        account_label="Work Google",
        account_email="work@example.com",
        refresh_token="work-refresh-token",
        calendars=[
            {
                "calendar_name": "Work",
                "calendar_id": "work",
                "is_default": True,
            }
        ],
    )


def _configure_microsoft_settings() -> None:
    service = OperatorSettingsService(settings=get_settings())
    service.set_microsoft_oauth_settings(
        client_id="microsoft-client-id",
        client_secret="microsoft-client-secret",
    )
    service.set_microsoft_account_settings(
        account_label="Kay Microsoft",
        account_email="kay@example.com",
        refresh_token="microsoft-refresh-token",
    )
    service.set_microsoft_calendar_catalog(
        [
            {
                "calendar_name": "Calendar",
                "calendar_id": "primary",
                "is_default": True,
            }
        ]
    )


def _configure_duplicate_named_provider_targets() -> None:
    service = OperatorSettingsService(settings=get_settings())
    service.set_apple_calendar_catalog(
        [
            {
                "calendar_name": "Family",
                "calendar_url": "https://caldav.icloud.com/family/",
                "is_default": True,
            }
        ]
    )
    service.set_google_oauth_settings(
        client_id="google-client-id",
        client_secret="google-client-secret",
    )
    service.upsert_google_account(
        account_label="Kay Google",
        account_email="kay@example.com",
        refresh_token="google-refresh-token",
        calendars=[
            {
                "calendar_name": "Family",
                "calendar_id": "family-google",
                "is_default": True,
            }
        ],
    )
    service.set_microsoft_oauth_settings(
        client_id="microsoft-client-id",
        client_secret="microsoft-client-secret",
    )
    service.upsert_microsoft_account(
        account_label="Kay Microsoft",
        account_email="kay@example.com",
        refresh_token="microsoft-refresh-token",
        calendars=[
            {
                "calendar_name": "Family",
                "calendar_id": "family-microsoft",
                "is_default": True,
            }
        ],
    )


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


def test_create_appointment_can_target_google_calendar(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    _configure_google_settings()
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: FakeAppleClient(),
    )
    monkeypatch.setattr(
        AppointmentService,
        "_build_google_client",
        lambda self: FakeGoogleClient(),
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/appointments",
        json={
            "title": "Google Dentist",
            "date": "2026-06-05",
            "start_time": "10:00",
            "end_time": "11:00",
            "timezone": "America/Anchorage",
            "target_calendar_url": "google:primary",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["provider_event_id"] == "google-created"

    detail_response = client.get(f"/api/appointments/{body['appointment_id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["provider_type"] == "google_calendar"
    assert detail_response.json()["calendar_name"] == "Primary"


def test_create_appointment_can_target_a_specific_google_account_calendar(
    monkeypatch,
) -> None:
    _configure_test_env(monkeypatch)
    _configure_multiple_google_accounts()
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: FakeAppleClient(),
    )
    monkeypatch.setattr(
        AppointmentService,
        "_build_google_client",
        lambda self, calendar_id=None, account_email=None, calendar_name=None: FakeGoogleClient(),
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/appointments",
        json={
            "title": "Work planning",
            "date": "2026-06-05",
            "start_time": "15:00",
            "end_time": "16:00",
            "timezone": "America/Anchorage",
            "target_calendar_url": "google:work@example.com:work",
        },
    )

    assert response.status_code == 201
    detail_response = client.get(f"/api/appointments/{response.json()['appointment_id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["provider_type"] == "google_calendar"
    assert detail_response.json()["calendar_name"] == "Work"
    assert detail_response.json()["account_label"] == "Work Google"


def test_list_appointments_syncs_google_calendar_events(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    _configure_google_settings()
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: FakeAppleClient(),
    )
    monkeypatch.setattr(
        AppointmentService,
        "_build_google_client",
        lambda self: FakeGoogleClient(),
    )
    app = create_app()
    client = TestClient(app)

    response = client.get(
        "/api/appointments?date_from=2026-06-15&date_to=2026-06-15"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    assert body["items"][0]["title"] == "Google School Visit"
    assert body["items"][0]["provider_event_id"] == "google-existing"


def test_create_appointment_can_target_microsoft_calendar(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    _configure_microsoft_settings()
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: FakeAppleClient(),
    )
    monkeypatch.setattr(
        AppointmentService,
        "_build_microsoft_client",
        lambda self, calendar_id=None, account_email=None, calendar_name=None: FakeMicrosoftClient(),
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/appointments",
        json={
            "title": "Outlook Dentist",
            "date": "2026-06-05",
            "start_time": "10:00",
            "end_time": "11:00",
            "timezone": "America/Anchorage",
            "target_calendar_url": "microsoft:kay@example.com:primary",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["provider_event_id"] == "microsoft-created"

    detail_response = client.get(f"/api/appointments/{body['appointment_id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["provider_type"] == "microsoft_calendar"
    assert detail_response.json()["calendar_name"] == "Calendar"


def test_list_appointments_syncs_microsoft_calendar_events(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    _configure_microsoft_settings()
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: FakeAppleClient(),
    )
    monkeypatch.setattr(
        AppointmentService,
        "_build_microsoft_client",
        lambda self, calendar_id=None, account_email=None, calendar_name=None: FakeMicrosoftClient(),
    )
    app = create_app()
    client = TestClient(app)

    response = client.get(
        "/api/appointments?date_from=2026-06-16&date_to=2026-06-16"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    assert body["items"][0]["title"] == "Outlook School Visit"
    assert body["items"][0]["provider_event_id"] == "microsoft-existing"


def test_availability_returns_open_slots_in_working_hours(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: FakeAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    for title, start_time, end_time in (
        ("Morning dentist", "09:00", "10:00"),
        ("Lunch consult", "13:00", "14:00"),
    ):
        create_response = client.post(
            "/api/appointments",
            json={
                "title": title,
                "date": "2026-06-01",
                "start_time": start_time,
                "end_time": end_time,
                "timezone": "America/Anchorage",
                "all_day": False,
            },
        )
        assert create_response.status_code == 201

    response = client.get(
        "/api/availability?date_from=2026-06-01&date_to=2026-06-01&duration_minutes=60&max_results=4"
    )

    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "date": "2026-06-01",
            "start_time": "08:00",
            "end_time": "09:00",
            "timezone": "America/Anchorage",
        },
        {
            "date": "2026-06-01",
            "start_time": "10:00",
            "end_time": "11:00",
            "timezone": "America/Anchorage",
        },
        {
            "date": "2026-06-01",
            "start_time": "11:00",
            "end_time": "12:00",
            "timezone": "America/Anchorage",
        },
        {
            "date": "2026-06-01",
            "start_time": "12:00",
            "end_time": "13:00",
            "timezone": "America/Anchorage",
        },
    ]


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


def test_list_appointments_syncs_from_multiple_saved_apple_calendars(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self, calendar_url=None: MultiCalendarSyncingAppleClient(calendar_url),
    )
    service = AppointmentService(settings=get_settings())
    service.apple_runtime_config._operator_settings().set_apple_calendar_catalog(
        [
            {
                "calendar_name": "Family",
                "calendar_url": "https://caldav.icloud.com/family/",
                "is_default": True,
            },
            {
                "calendar_name": "School",
                "calendar_url": "https://caldav.icloud.com/school/",
                "is_default": False,
            },
        ]
    )
    app = create_app()
    client = TestClient(app)

    response = client.get(
        "/api/appointments?date_from=2026-06-12&date_to=2026-06-12"
    )

    assert response.status_code == 200
    assert [item["title"] for item in response.json()["items"]] == [
        "School assembly",
        "Family dinner",
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


def test_create_appointment_can_target_a_specific_saved_apple_calendar(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self, calendar_url=None: FakeAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    service = AppointmentService(settings=get_settings())
    service.apple_runtime_config._operator_settings().set_apple_calendar_catalog(
        [
            {
                "calendar_name": "Family",
                "calendar_url": "https://caldav.icloud.com/family/",
                "is_default": True,
            },
            {
                "calendar_name": "School",
                "calendar_url": "https://caldav.icloud.com/school/",
                "is_default": False,
            },
        ]
    )

    response = client.post(
        "/api/appointments",
        json={
            "title": "School meeting",
            "date": "2026-06-05",
            "start_time": "13:00",
            "end_time": "14:00",
            "timezone": "America/Anchorage",
            "target_calendar_url": "https://caldav.icloud.com/school/",
        },
    )

    assert response.status_code == 201
    detail = client.get(f"/api/appointments/{response.json()['appointment_id']}")
    assert detail.status_code == 200
    assert detail.json()["calendar_name"] == "School"


def test_create_appointment_can_target_a_saved_apple_calendar_by_name(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self, calendar_url=None: FakeAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    service = AppointmentService(settings=get_settings())
    service.apple_runtime_config._operator_settings().set_apple_calendar_catalog(
        [
            {
                "calendar_name": "Family",
                "calendar_url": "https://caldav.icloud.com/family/",
                "is_default": True,
            },
            {
                "calendar_name": "School",
                "calendar_url": "https://caldav.icloud.com/school/",
                "is_default": False,
            },
        ]
    )

    response = client.post(
        "/api/appointments",
        json={
            "title": "School meeting",
            "date": "2026-06-05",
            "start_time": "13:00",
            "end_time": "14:00",
            "timezone": "America/Anchorage",
            "target_calendar_name": "School",
        },
    )

    assert response.status_code == 201
    detail = client.get(f"/api/appointments/{response.json()['appointment_id']}")
    assert detail.status_code == 200
    assert detail.json()["calendar_name"] == "School"


def test_update_appointment_can_move_to_a_saved_apple_calendar_by_name(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self, calendar_url=None: FakeAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    service = AppointmentService(settings=get_settings())
    service.apple_runtime_config._operator_settings().set_apple_calendar_catalog(
        [
            {
                "calendar_name": "Family",
                "calendar_url": "https://caldav.icloud.com/family/",
                "is_default": True,
            },
            {
                "calendar_name": "School",
                "calendar_url": "https://caldav.icloud.com/school/",
                "is_default": False,
            },
        ]
    )

    create_response = client.post(
        "/api/appointments",
        json={
            "title": "Reading assessment",
            "date": "2026-06-07",
            "start_time": "09:00",
            "end_time": "10:00",
            "timezone": "America/Anchorage",
        },
    )
    appointment_id = create_response.json()["appointment_id"]

    update_response = client.patch(
        f"/api/appointments/{appointment_id}",
        json={
            "target_calendar_name": "School",
        },
    )

    assert update_response.status_code == 200
    detail = client.get(f"/api/appointments/{appointment_id}")
    assert detail.status_code == 200
    assert detail.json()["calendar_name"] == "School"


def test_create_appointment_can_target_google_calendar_by_provider_aware_name(
    monkeypatch,
) -> None:
    _configure_test_env(monkeypatch)
    _configure_duplicate_named_provider_targets()
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self, calendar_url=None: FakeAppleClient(),
    )
    monkeypatch.setattr(
        AppointmentService,
        "_build_google_client",
        lambda self, calendar_id=None, account_email=None, calendar_name=None: FakeGoogleClient(),
    )
    monkeypatch.setattr(
        AppointmentService,
        "_build_microsoft_client",
        lambda self, calendar_id=None, account_email=None, calendar_name=None: FakeMicrosoftClient(),
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/appointments",
        json={
            "title": "Google family event",
            "date": "2026-06-08",
            "start_time": "13:00",
            "end_time": "14:00",
            "timezone": "America/Anchorage",
            "target_calendar_name": "Family on Google",
        },
    )

    assert response.status_code == 201
    detail = client.get(f"/api/appointments/{response.json()['appointment_id']}")
    assert detail.status_code == 200
    assert detail.json()["provider_type"] == "google_calendar"
    assert detail.json()["calendar_name"] == "Family"
    assert detail.json()["account_label"] == "Kay Google"


def test_create_appointment_can_target_microsoft_calendar_by_provider_aware_name(
    monkeypatch,
) -> None:
    _configure_test_env(monkeypatch)
    _configure_duplicate_named_provider_targets()
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self, calendar_url=None: FakeAppleClient(),
    )
    monkeypatch.setattr(
        AppointmentService,
        "_build_google_client",
        lambda self, calendar_id=None, account_email=None, calendar_name=None: FakeGoogleClient(),
    )
    monkeypatch.setattr(
        AppointmentService,
        "_build_microsoft_client",
        lambda self, calendar_id=None, account_email=None, calendar_name=None: FakeMicrosoftClient(),
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/appointments",
        json={
            "title": "Microsoft family event",
            "date": "2026-06-09",
            "start_time": "15:00",
            "end_time": "16:00",
            "timezone": "America/Anchorage",
            "target_calendar_name": "Family on Microsoft",
        },
    )

    assert response.status_code == 201
    detail = client.get(f"/api/appointments/{response.json()['appointment_id']}")
    assert detail.status_code == 200
    assert detail.json()["provider_type"] == "microsoft_calendar"
    assert detail.json()["calendar_name"] == "Family"
    assert detail.json()["account_label"] == "Kay Microsoft"


def test_create_appointment_rejects_ambiguous_calendar_name_across_providers(
    monkeypatch,
) -> None:
    _configure_test_env(monkeypatch)
    _configure_duplicate_named_provider_targets()
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self, calendar_url=None: FakeAppleClient(),
    )
    monkeypatch.setattr(
        AppointmentService,
        "_build_google_client",
        lambda self, calendar_id=None, account_email=None, calendar_name=None: FakeGoogleClient(),
    )
    monkeypatch.setattr(
        AppointmentService,
        "_build_microsoft_client",
        lambda self, calendar_id=None, account_email=None, calendar_name=None: FakeMicrosoftClient(),
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/appointments",
        json={
            "title": "Ambiguous family event",
            "date": "2026-06-10",
            "start_time": "11:00",
            "end_time": "12:00",
            "timezone": "America/Anchorage",
            "target_calendar_name": "Family",
        },
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "ambiguous" in detail.lower()
    assert "Family · Apple Calendar · Family" in detail
    assert "Family · Google Calendar · Kay Google" in detail
    assert "Family · Microsoft Calendar · Kay Microsoft" in detail


def test_run_write_smoke_test_performs_create_update_cancel(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    service = AppointmentService(settings=get_settings())
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        service,
        "_describe_target_calendar",
        lambda target_calendar_url: {
            "calendar_name": "Family",
            "provider_label": "Google Calendar",
            "account_label": "Kay Google",
        },
    )

    def fake_create(payload, actor: str = "api"):
        calls.append(("create", actor))
        return AppointmentResponse(
            appointment_id="appt-1",
            status="active",
            provider_event_id="provider-created",
            message="Appointment created.",
        )

    def fake_update(appointment_id: str, payload, actor: str = "api"):
        calls.append(("update", actor))
        assert appointment_id == "appt-1"
        return AppointmentResponse(
            appointment_id=appointment_id,
            status="active",
            provider_event_id="provider-created",
            message="Appointment updated.",
        )

    def fake_cancel(appointment_id: str, actor: str = "api"):
        calls.append(("cancel", actor))
        assert appointment_id == "appt-1"
        return AppointmentResponse(
            appointment_id=appointment_id,
            status="cancelled",
            provider_event_id="provider-created",
            message="Appointment cancelled.",
        )

    monkeypatch.setattr(service, "create", fake_create)
    monkeypatch.setattr(service, "update", fake_update)
    monkeypatch.setattr(service, "cancel", fake_cancel)

    result = service.run_write_smoke_test(
        target_calendar_url="google:kay@example.com:primary",
        actor="console",
    )

    assert result == {
        "calendar_name": "Family",
        "provider_label": "Google Calendar",
        "provider_type": "",
        "account_label": "Kay Google",
        "target_value": "google:kay@example.com:primary",
    }
    assert calls == [
        ("create", "console:write_smoke_test"),
        ("update", "console:write_smoke_test"),
        ("cancel", "console:write_smoke_test"),
    ]


def test_run_write_smoke_test_attempts_cleanup_on_failure(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    service = AppointmentService(settings=get_settings())
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        service,
        "_describe_target_calendar",
        lambda target_calendar_url: {
            "calendar_name": "Family",
            "provider_label": "Apple Calendar",
            "account_label": "Family",
        },
    )

    def fake_create(payload, actor: str = "api"):
        calls.append(("create", actor))
        return AppointmentResponse(
            appointment_id="appt-2",
            status="active",
            provider_event_id="provider-created",
            message="Appointment created.",
        )

    def fake_update(appointment_id: str, payload, actor: str = "api"):
        calls.append(("update", actor))
        raise ValueError("Update failed")

    def fake_cancel(appointment_id: str, actor: str = "api"):
        calls.append(("cancel", actor))
        return AppointmentResponse(
            appointment_id=appointment_id,
            status="cancelled",
            provider_event_id="provider-created",
            message="Appointment cancelled.",
        )

    monkeypatch.setattr(service, "create", fake_create)
    monkeypatch.setattr(service, "update", fake_update)
    monkeypatch.setattr(service, "cancel", fake_cancel)

    try:
        service.run_write_smoke_test(
            target_calendar_url="https://caldav.icloud.com/family/",
            actor="console",
        )
    except ValueError as exc:
        assert str(exc) == "Update failed"
    else:
        assert False, "Expected write smoke test to propagate the failure."

    assert calls == [
        ("create", "console:write_smoke_test"),
        ("update", "console:write_smoke_test"),
        ("cancel", "console:write_smoke_test_cleanup"),
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


def test_create_appointment_points_to_apple_reconnect_when_recovery_hints_exist(
    monkeypatch,
) -> None:
    db_path = Path(tempfile.gettempdir()) / f"calsync-api-test-{uuid4()}.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path.as_posix()}")
    for key in (
        "APPLE_ACCOUNT_LABEL",
        "APPLE_USERNAME",
        "APPLE_APP_SPECIFIC_PASSWORD",
        "APPLE_PRIMARY_CALENDAR_URL",
        "APPLE_PRIMARY_CALENDAR_NAME",
    ):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    _get_engine_for_url.cache_clear()
    _get_session_factory_for_url.cache_clear()
    Base.metadata.create_all(_get_engine_for_url(get_settings().database_url))
    operator_settings = OperatorSettingsService(settings=get_settings())
    operator_settings.set_legacy_apple_recovery_hints(
        {
            "source_filename": "calsync-db-backup.zip",
            "account_label": "kaymayers9@gmail.com",
            "account_username": "kaymayers9@gmail.com",
            "calendar_home_url": "https://p52-caldav.icloud.com:443/112135872/calendars/",
            "principal_url": "https://caldav.icloud.com/112135872/principal/",
            "recommended_calendar_name": "Family",
            "recommended_calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/e53367e6-75d4-42a0-b7bf-eaeb12f233f8/",
            "calendar_count": 1,
            "calendars": [
                {
                    "calendar_name": "Family",
                    "calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/e53367e6-75d4-42a0-b7bf-eaeb12f233f8/",
                    "calendar_role": "writable_booking_target",
                    "enabled": True,
                    "is_writable_hint": True,
                }
            ],
        }
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

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Apple reconnect still needs one more step. Open Apple setup in CalSync, confirm the loaded recovered calendar, and save a fresh app-specific password before I can help with the household calendar."
    )


def test_list_appointments_points_to_apple_reconnect_when_recovery_hints_exist(
    monkeypatch,
) -> None:
    db_path = Path(tempfile.gettempdir()) / f"calsync-api-test-{uuid4()}.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path.as_posix()}")
    for key in (
        "APPLE_ACCOUNT_LABEL",
        "APPLE_USERNAME",
        "APPLE_APP_SPECIFIC_PASSWORD",
        "APPLE_PRIMARY_CALENDAR_URL",
        "APPLE_PRIMARY_CALENDAR_NAME",
    ):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    _get_engine_for_url.cache_clear()
    _get_session_factory_for_url.cache_clear()
    Base.metadata.create_all(_get_engine_for_url(get_settings().database_url))
    operator_settings = OperatorSettingsService(settings=get_settings())
    operator_settings.set_legacy_apple_recovery_hints(
        {
            "source_filename": "calsync-db-backup.zip",
            "account_label": "kaymayers9@gmail.com",
            "account_username": "kaymayers9@gmail.com",
            "calendar_home_url": "https://p52-caldav.icloud.com:443/112135872/calendars/",
            "principal_url": "https://caldav.icloud.com/112135872/principal/",
            "recommended_calendar_name": "Family",
            "recommended_calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/e53367e6-75d4-42a0-b7bf-eaeb12f233f8/",
            "calendar_count": 1,
            "calendars": [
                {
                    "calendar_name": "Family",
                    "calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/e53367e6-75d4-42a0-b7bf-eaeb12f233f8/",
                    "calendar_role": "writable_booking_target",
                    "enabled": True,
                    "is_writable_hint": True,
                }
            ],
        }
    )
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/appointments?date_from=2026-06-01&date_to=2026-06-01")

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Apple reconnect still needs one more step. Open Apple setup in CalSync, confirm the loaded recovered calendar, and save a fresh app-specific password before I can help with the household calendar."
    )


def test_availability_points_to_apple_reconnect_when_recovery_hints_exist(
    monkeypatch,
) -> None:
    db_path = Path(tempfile.gettempdir()) / f"calsync-api-test-{uuid4()}.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path.as_posix()}")
    for key in (
        "APPLE_ACCOUNT_LABEL",
        "APPLE_USERNAME",
        "APPLE_APP_SPECIFIC_PASSWORD",
        "APPLE_PRIMARY_CALENDAR_URL",
        "APPLE_PRIMARY_CALENDAR_NAME",
    ):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    _get_engine_for_url.cache_clear()
    _get_session_factory_for_url.cache_clear()
    Base.metadata.create_all(_get_engine_for_url(get_settings().database_url))
    operator_settings = OperatorSettingsService(settings=get_settings())
    operator_settings.set_legacy_apple_recovery_hints(
        {
            "source_filename": "calsync-db-backup.zip",
            "account_label": "kaymayers9@gmail.com",
            "account_username": "kaymayers9@gmail.com",
            "calendar_home_url": "https://p52-caldav.icloud.com:443/112135872/calendars/",
            "principal_url": "https://caldav.icloud.com/112135872/principal/",
            "recommended_calendar_name": "Family",
            "recommended_calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/e53367e6-75d4-42a0-b7bf-eaeb12f233f8/",
            "calendar_count": 1,
            "calendars": [
                {
                    "calendar_name": "Family",
                    "calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/e53367e6-75d4-42a0-b7bf-eaeb12f233f8/",
                    "calendar_role": "writable_booking_target",
                    "enabled": True,
                    "is_writable_hint": True,
                }
            ],
        }
    )
    monkeypatch.setattr(
        AppointmentService,
        "find_availability",
        lambda self, **kwargs: (_ for _ in ()).throw(
            ValueError("Primary Apple/iCloud calendar is not configured.")
        ),
    )
    app = create_app()
    client = TestClient(app)

    response = client.get(
        "/api/availability?date_from=2026-06-01&date_to=2026-06-01&duration_minutes=60"
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Apple reconnect still needs one more step. Open Apple setup in CalSync, confirm the loaded recovered calendar, and save a fresh app-specific password before I can help with the household calendar."
    )


def test_get_appointment_points_to_apple_reconnect_when_recovery_hints_exist(
    monkeypatch,
) -> None:
    db_path = Path(tempfile.gettempdir()) / f"calsync-api-test-{uuid4()}.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path.as_posix()}")
    for key in (
        "APPLE_ACCOUNT_LABEL",
        "APPLE_USERNAME",
        "APPLE_APP_SPECIFIC_PASSWORD",
        "APPLE_PRIMARY_CALENDAR_URL",
        "APPLE_PRIMARY_CALENDAR_NAME",
    ):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    _get_engine_for_url.cache_clear()
    _get_session_factory_for_url.cache_clear()
    Base.metadata.create_all(_get_engine_for_url(get_settings().database_url))
    operator_settings = OperatorSettingsService(settings=get_settings())
    operator_settings.set_legacy_apple_recovery_hints(
        {
            "source_filename": "calsync-db-backup.zip",
            "account_label": "kaymayers9@gmail.com",
            "account_username": "kaymayers9@gmail.com",
            "calendar_home_url": "https://p52-caldav.icloud.com:443/112135872/calendars/",
            "principal_url": "https://caldav.icloud.com/112135872/principal/",
            "recommended_calendar_name": "Family",
            "recommended_calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/e53367e6-75d4-42a0-b7bf-eaeb12f233f8/",
            "calendar_count": 1,
            "calendars": [
                {
                    "calendar_name": "Family",
                    "calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/e53367e6-75d4-42a0-b7bf-eaeb12f233f8/",
                    "calendar_role": "writable_booking_target",
                    "enabled": True,
                    "is_writable_hint": True,
                }
            ],
        }
    )
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/appointments/example-appointment")

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Apple reconnect still needs one more step. Open Apple setup in CalSync, confirm the loaded recovered calendar, and save a fresh app-specific password before I can help with the household calendar."
    )


def test_update_appointment_points_to_apple_reconnect_when_recovery_hints_exist(
    monkeypatch,
) -> None:
    _configure_test_env(monkeypatch)
    original_builder = AppointmentService._build_apple_client
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self, calendar_url=None: FakeAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    create_response = client.post(
        "/api/appointments",
        json={
            "title": "Telemedicine Post-Op",
            "date": "2026-12-09",
            "start_time": "12:40",
            "end_time": "13:10",
            "timezone": "America/Anchorage",
        },
    )
    appointment_id = create_response.json()["appointment_id"]

    monkeypatch.setattr(AppointmentService, "_build_apple_client", original_builder)
    for key in (
        "APPLE_ACCOUNT_LABEL",
        "APPLE_USERNAME",
        "APPLE_APP_SPECIFIC_PASSWORD",
        "APPLE_PRIMARY_CALENDAR_URL",
        "APPLE_PRIMARY_CALENDAR_NAME",
    ):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    _get_engine_for_url.cache_clear()
    _get_session_factory_for_url.cache_clear()
    operator_settings = OperatorSettingsService(settings=get_settings())
    operator_settings.set_legacy_apple_recovery_hints(
        {
            "source_filename": "calsync-db-backup.zip",
            "account_label": "kaymayers9@gmail.com",
            "account_username": "kaymayers9@gmail.com",
            "calendar_home_url": "https://p52-caldav.icloud.com:443/112135872/calendars/",
            "principal_url": "https://caldav.icloud.com/112135872/principal/",
            "recommended_calendar_name": "Family",
            "recommended_calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/e53367e6-75d4-42a0-b7bf-eaeb12f233f8/",
            "calendar_count": 1,
            "calendars": [
                {
                    "calendar_name": "Family",
                    "calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/e53367e6-75d4-42a0-b7bf-eaeb12f233f8/",
                    "calendar_role": "writable_booking_target",
                    "enabled": True,
                    "is_writable_hint": True,
                }
            ],
        }
    )
    recovery_app = create_app()
    recovery_client = TestClient(recovery_app)

    response = recovery_client.patch(
        f"/api/appointments/{appointment_id}",
        json={"title": "Telemedicine Post-Op updated"},
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Apple reconnect still needs one more step. Open Apple setup in CalSync, confirm the loaded recovered calendar, and save a fresh app-specific password before I can help with the household calendar."
    )
    assert response.json()["detail"] != "Apple calendar target URL was not found."


def test_cancel_appointment_points_to_apple_reconnect_when_recovery_hints_exist(
    monkeypatch,
) -> None:
    _configure_test_env(monkeypatch)
    original_builder = AppointmentService._build_apple_client
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self, calendar_url=None: FakeAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    create_response = client.post(
        "/api/appointments",
        json={
            "title": "Telemedicine Post-Op",
            "date": "2026-12-09",
            "start_time": "12:40",
            "end_time": "13:10",
            "timezone": "America/Anchorage",
        },
    )
    appointment_id = create_response.json()["appointment_id"]

    monkeypatch.setattr(AppointmentService, "_build_apple_client", original_builder)
    for key in (
        "APPLE_ACCOUNT_LABEL",
        "APPLE_USERNAME",
        "APPLE_APP_SPECIFIC_PASSWORD",
        "APPLE_PRIMARY_CALENDAR_URL",
        "APPLE_PRIMARY_CALENDAR_NAME",
    ):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    _get_engine_for_url.cache_clear()
    _get_session_factory_for_url.cache_clear()
    operator_settings = OperatorSettingsService(settings=get_settings())
    operator_settings.set_legacy_apple_recovery_hints(
        {
            "source_filename": "calsync-db-backup.zip",
            "account_label": "kaymayers9@gmail.com",
            "account_username": "kaymayers9@gmail.com",
            "calendar_home_url": "https://p52-caldav.icloud.com:443/112135872/calendars/",
            "principal_url": "https://caldav.icloud.com/112135872/principal/",
            "recommended_calendar_name": "Family",
            "recommended_calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/e53367e6-75d4-42a0-b7bf-eaeb12f233f8/",
            "calendar_count": 1,
            "calendars": [
                {
                    "calendar_name": "Family",
                    "calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/e53367e6-75d4-42a0-b7bf-eaeb12f233f8/",
                    "calendar_role": "writable_booking_target",
                    "enabled": True,
                    "is_writable_hint": True,
                }
            ],
        }
    )
    recovery_app = create_app()
    recovery_client = TestClient(recovery_app)

    response = recovery_client.post(f"/api/appointments/{appointment_id}/cancel")

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Apple reconnect still needs one more step. Open Apple setup in CalSync, confirm the loaded recovered calendar, and save a fresh app-specific password before I can help with the household calendar."
    )
    assert response.json()["detail"] != "Apple calendar target URL was not found."


def test_create_appointment_points_to_original_key_recovery_when_preserved_secret_needs_old_key(
    monkeypatch,
) -> None:
    db_path = Path(tempfile.gettempdir()) / f"calsync-api-test-{uuid4()}.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path.as_posix()}")
    for key in (
        "APPLE_ACCOUNT_LABEL",
        "APPLE_USERNAME",
        "APPLE_APP_SPECIFIC_PASSWORD",
        "APPLE_PRIMARY_CALENDAR_URL",
        "APPLE_PRIMARY_CALENDAR_NAME",
    ):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    _get_engine_for_url.cache_clear()
    _get_session_factory_for_url.cache_clear()
    Base.metadata.create_all(_get_engine_for_url(get_settings().database_url))
    operator_settings = OperatorSettingsService(settings=get_settings())
    mismatched_secret = Fernet(
        base64.urlsafe_b64encode(hashlib.sha256(b"different-test-key").digest())
    ).encrypt(b"apple-secret-123").decode("utf-8")
    operator_settings.set_legacy_apple_recovery_hints(
        {
            "source_filename": "calsync-db-backup.zip",
            "account_label": "kaymayers9@gmail.com",
            "account_username": "kaymayers9@gmail.com",
            "calendar_home_url": "https://p52-caldav.icloud.com:443/112135872/calendars/",
            "principal_url": "https://caldav.icloud.com/112135872/principal/",
            "credential_secret_encrypted": mismatched_secret,
            "recommended_calendar_name": "Family",
            "recommended_calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/e53367e6-75d4-42a0-b7bf-eaeb12f233f8/",
            "calendar_count": 1,
            "calendars": [
                {
                    "calendar_name": "Family",
                    "calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/e53367e6-75d4-42a0-b7bf-eaeb12f233f8/",
                    "calendar_role": "writable_booking_target",
                    "enabled": True,
                    "is_writable_hint": True,
                }
            ],
        }
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

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Apple reconnect still needs one more step. Open Apple setup in CalSync, then either restore the original CalSync encryption key or save a fresh app-specific password before I can help with the household calendar."
    )
