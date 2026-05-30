import json
import tempfile
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4
from zipfile import ZipFile
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from calsync.config import get_settings
from calsync.db import _get_engine_for_url, _get_session_factory_for_url
from calsync.main import create_app
from calsync.models import Base
from calsync.services.appointments import AppointmentService
from calsync.services.apple_caldav import AppleCalDAVError
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


def _legacy_backup_payload() -> bytes:
    sql = (
        "COPY public.provider_accounts (id, provider_type, provider_account_id, display_name, access_token_encrypted, refresh_token_encrypted, provider_metadata, created_at, updated_at, credential_secret_encrypted, auth_mode, can_read, can_write, requires_reconnect) FROM stdin;\n"
        "apple-account\ticloud_caldav\tkaymayers9@gmail.com\tkaymayers9@gmail.com\t\\\\N\t\\\\N\t{\"auth_status\": \"connected\", \"principal_url\": \"https://caldav.icloud.com/112135872/principal/\", \"calendar_home_url\": \"https://p52-caldav.icloud.com:443/112135872/calendars/\"}\t2026-05-14 19:47:44.895745+00\t2026-05-26 05:02:56.813761+00\tsecret\tcaldav\tt\tt\tf\n"
        "\\.\n"
        "COPY public.provider_calendars (id, provider_account_pk, provider_calendar_id, name, timezone, enabled, provider_metadata, created_at, updated_at, calendar_role) FROM stdin;\n"
        "family-cal\tapple-account\thttps://p52-caldav.icloud.com:443/112135872/calendars/06810ae4-a07b-49d9-9541-98123e74c806/\tFamily\t\\\\N\tf\t{\"href\": \"https://p52-caldav.icloud.com:443/112135872/calendars/06810ae4-a07b-49d9-9541-98123e74c806/\"}\t2026-05-14 19:47:45.997212+00\t2026-05-14 20:03:09.020352+00\twritable_booking_target\n"
        "calendar-cal\tapple-account\thttps://p52-caldav.icloud.com:443/112135872/calendars/6824BCB8-8CEE-4733-9208-4741C62E266C/\tCalendar\t\\\\N\tt\t{\"href\": \"https://p52-caldav.icloud.com:443/112135872/calendars/6824BCB8-8CEE-4733-9208-4741C62E266C/\"}\t2026-05-14 19:47:45.997212+00\t2026-05-14 20:03:09.020352+00\tpersonal_reference\n"
        "\\.\n"
    ).encode("utf-8")
    payload = BytesIO()
    with ZipFile(payload, "w") as archive:
        archive.writestr("calsync-db-backup.sql", sql)
    return payload.getvalue()


def test_console_root_renders_scheduler_surface(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    app = create_app()
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "See the household schedule clearly" in response.text
    assert "New appointment" in response.text
    assert "Week board" in response.text
    assert "Details that actually help" in response.text
    assert "System readiness" in response.text
    assert "Connections" in response.text
    assert "Apple setup" in response.text
    assert "Google setup" in response.text
    assert "Find open time" in response.text
    assert "See the next seven days in parallel so it feels like real calendar planning." in response.text
    assert "built-in method copy of dict object" not in response.text
    assert "Google write path is built and waiting for setup" in response.text
    assert "Microsoft write path is built and waiting for setup" in response.text
    assert "Preview Alexa through the setup flow and simulator before live turn-on" in response.text


def test_console_root_explains_blocked_create_state_when_no_calendar_is_connected(
    monkeypatch,
) -> None:
    db_path = Path(tempfile.gettempdir()) / f"calsync-ui-test-{uuid4()}.db"
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
    app = create_app()
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Calendar setup still needed" in response.text
    assert "Read existing Apple calendar events" not in response.text
    assert "Write to connected Apple calendars" not in response.text
    assert "Connect a writable calendar to unlock create, edit, and cancel appointments." in response.text
    assert "Connect a writable calendar before creating appointments from the schedule workspace." in response.text
    assert 'name="target_calendar_url" disabled' in response.text
    assert '<button type="submit" disabled>Create appointment</button>' in response.text
    assert "Open Connections" in response.text


def test_console_root_points_to_restore_when_non_provider_settings_exist(
    monkeypatch,
) -> None:
    db_path = Path(tempfile.gettempdir()) / f"calsync-ui-test-{uuid4()}.db"
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
    operator_settings.set_public_booking_settings(
        page_title="Book time with CalSync",
        page_description="Claim an open slot.",
        duration_minutes=45,
        search_window_days=21,
        success_message="Booking confirmed.",
        target_calendar_url="",
        booking_weekdays=[0, 1, 2, 3, 4],
        day_start_time="09:00",
        day_end_time="15:00",
    )
    app = create_app()
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert (
        "Restore an encrypted backup from Connections or add an Apple calendar so CalSync can read and write a real connected calendar."
        in response.text
    )


def test_console_root_points_to_apple_reconnect_when_legacy_hints_exist(
    monkeypatch,
) -> None:
    db_path = Path(tempfile.gettempdir()) / f"calsync-ui-test-{uuid4()}.db"
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
            "recommended_calendar_name": "Calendar",
            "recommended_calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/6824BCB8-8CEE-4733-9208-4741C62E266C/",
            "calendar_count": 1,
            "calendars": [
                {
                    "calendar_name": "Calendar",
                    "calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/6824BCB8-8CEE-4733-9208-4741C62E266C/",
                    "calendar_role": "writable_booking_target",
                    "enabled": True,
                    "is_writable_hint": True,
                }
            ],
        }
    )
    app = create_app()
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert (
        "Open Apple setup, confirm the loaded recovered Apple calendar, and save a fresh app-specific password so CalSync can reconnect the real household calendar."
        in response.text
    )


def test_console_root_explains_blocked_schedule_state_when_no_calendar_is_connected(
    monkeypatch,
) -> None:
    db_path = Path(tempfile.gettempdir()) / f"calsync-ui-test-{uuid4()}.db"
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
    app = create_app()
    client = TestClient(app)

    day_response = client.get("/?view=day")
    week_response = client.get("/?view=week")
    month_response = client.get("/?view=month")

    assert day_response.status_code == 200
    assert "Calendar setup still blocks live schedule sync." in day_response.text
    assert "Connect a writable calendar before CalSync can show a real live schedule window." in day_response.text
    assert "Choose a calendar connection before expecting appointment detail or activity here." in day_response.text
    assert "Live schedule" in day_response.text
    assert "Blocked" in day_response.text
    assert "Writable calendar" in day_response.text
    assert "Needed" in day_response.text
    assert "Reconnect Apple first" in day_response.text
    assert "Nothing scheduled yet" not in day_response.text
    assert "Select an appointment" not in day_response.text
    assert "Show cancelled for reference" not in day_response.text

    assert week_response.status_code == 200
    assert "Calendar setup still blocks live schedule sync." in week_response.text
    assert "Connect a writable calendar before CalSync can show a real live schedule window." in week_response.text
    assert "Nothing scheduled yet" not in week_response.text
    assert "Show cancelled for reference" not in week_response.text

    assert month_response.status_code == 200
    assert "Calendar setup still blocks live schedule sync." in month_response.text
    assert "Connect a writable calendar before CalSync can show a real live schedule window." in month_response.text
    assert ">Open<" not in month_response.text
    assert "Show cancelled for reference" not in month_response.text


def test_console_root_hides_stale_stats_and_selected_detail_when_calendar_disconnects(
    monkeypatch,
) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: FakeAppleClient(),
    )
    connected_app = create_app()
    connected_client = TestClient(connected_app)

    create_response = connected_client.post(
        "/api/appointments",
        json={
            "title": "Stale school reminder",
            "date": "2026-06-12",
            "start_time": "08:30",
            "end_time": "09:15",
            "timezone": "America/Anchorage",
            "notes": "Should not appear once disconnected",
        },
    )
    assert create_response.status_code == 201

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

    disconnected_app = create_app()
    disconnected_client = TestClient(disconnected_app)

    response = disconnected_client.get("/")

    assert response.status_code == 200
    assert "Calendar setup still blocks live schedule sync." in response.text
    assert "Stale school reminder" not in response.text
    assert "Should not appear once disconnected" not in response.text
    assert "What CalSync has done with this appointment" not in response.text
    assert "Edit appointment" not in response.text
    assert "Cancel appointment" not in response.text
    assert "No appointments in this window yet." not in response.text
    assert "Reconnect Apple first" in response.text


def test_booking_page_renders_public_surface_with_open_slots(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: FakeAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    response = client.get("/book")

    assert response.status_code == 200
    assert "Book time with CalSync" in response.text
    assert "Available times" in response.text
    assert "Your name" in response.text
    assert "How should we reach you?" in response.text
    assert "Request this time" in response.text


def test_booking_page_blocks_availability_refresh_when_no_calendar_is_connected(
    monkeypatch,
) -> None:
    db_path = Path(tempfile.gettempdir()) / f"calsync-ui-test-{uuid4()}.db"
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
    app = create_app()
    client = TestClient(app)

    response = client.get("/book")

    assert response.status_code == 200
    assert "Public booking is not ready yet" in response.text
    assert "Connect a writable calendar before public booking can search for open time." in response.text
    assert '<button type="submit" disabled>Refresh open time</button>' in response.text
    assert "No writable calendar is connected yet." in response.text


def test_booking_setup_page_blocks_configuration_when_no_calendar_is_connected(
    monkeypatch,
) -> None:
    _configure_test_env(monkeypatch)
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
    app = create_app()
    client = TestClient(app)

    response = client.get("/booking/setup")

    assert response.status_code == 200
    assert "Booking setup still needs a calendar" in response.text
    assert "Connect a writable calendar before configuring public booking settings or creating shareable booking types." in response.text
    assert '<button type="submit" disabled>Save booking settings</button>' in response.text
    assert '<button type="submit" disabled>Create booking type</button>' in response.text
    assert 'name="target_calendar_url" disabled' in response.text
    assert "No writable calendars connected yet" in response.text
    assert "No writable target yet" in response.text


def test_booking_setup_rejects_save_when_no_calendar_is_connected(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
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
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/booking/setup",
        data={
            "page_title": "Book time with Kayra",
            "page_description": "Choose a calm household scheduling slot.",
            "duration_minutes": "45",
            "search_window_days": "28",
            "success_message": "You're booked.",
            "target_calendar_url": "",
            "booking_weekdays": ["0", "1", "2", "3", "4"],
            "day_start_time": "09:00",
            "day_end_time": "15:00",
        },
    )

    assert response.status_code == 400
    assert "Connect a writable calendar before saving public booking settings." in response.text
    assert "Public booking settings saved securely." not in response.text


def test_booking_setup_rejects_new_type_when_no_calendar_is_connected(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
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
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/booking/setup/types",
        data={
            "new_page_title": "Therapy intake",
            "new_booking_slug": "therapy-intake",
        },
    )

    assert response.status_code == 400
    assert "Connect a writable calendar before creating public booking types." in response.text
    assert "Public booking type saved securely." not in response.text


def test_booking_setup_page_round_trips_public_booking_settings(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/booking/setup",
        data={
            "page_title": "Book time with Kayra",
            "page_description": "Choose a calm household scheduling slot.",
            "duration_minutes": "45",
            "search_window_days": "28",
            "success_message": "You're booked.",
            "target_calendar_url": "https://caldav.icloud.com/calendar/",
            "booking_weekdays": ["0", "1", "2", "3", "4"],
            "day_start_time": "09:00",
            "day_end_time": "15:00",
        },
    )

    assert response.status_code == 200
    assert "Public booking settings saved securely." in response.text
    assert "Book time with Kayra" in response.text
    assert "Monday to Friday" in response.text
    assert "9:00 AM to 3:00 PM" in response.text

    booking_page = client.get("/book")
    assert booking_page.status_code == 200
    assert "Book time with Kayra" in booking_page.text
    assert "Choose a calm household scheduling slot." in booking_page.text
    assert 'value="45"' in booking_page.text
    assert 'value="09:00"' in response.text
    assert 'value="15:00"' in response.text


def test_booking_page_respects_saved_public_availability_rules(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    operator_settings = OperatorSettingsService(settings=get_settings())
    operator_settings.set_public_booking_settings(
        page_title="Book time with Kayra",
        page_description="Choose a calm household scheduling slot.",
        duration_minutes=60,
        search_window_days=14,
        success_message="You're booked.",
        target_calendar_url="https://caldav.icloud.com/calendar/",
        booking_weekdays=[0],
        day_start_time="09:00",
        day_end_time="12:00",
    )
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: FakeAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    response = client.get(
        "/book?availability_date_from=2026-06-01&availability_date_to=2026-06-02&availability_duration_minutes=60"
    )

    assert response.status_code == 200
    assert "Monday, Jun 1" in response.text
    assert "Tuesday, Jun 2" not in response.text
    assert "9:00 AM - 10:00 AM" in response.text
    assert "10:00 AM - 11:00 AM" in response.text
    assert "11:00 AM - 12:00 PM" in response.text
    assert "8:00 AM - 9:00 AM" not in response.text
    assert "12:00 PM - 1:00 PM" not in response.text


def test_booking_setup_and_public_routes_support_multiple_booking_types(
    monkeypatch,
) -> None:
    _configure_test_env(monkeypatch)
    operator_settings = OperatorSettingsService(settings=get_settings())
    operator_settings.set_public_booking_settings(
        page_title="Book time with Kayra",
        page_description="Choose a calm household scheduling slot.",
        duration_minutes=45,
        search_window_days=28,
        success_message="You're booked.",
        target_calendar_url="https://caldav.icloud.com/calendar/",
        booking_weekdays=[0, 1, 2, 3, 4],
        day_start_time="09:00",
        day_end_time="15:00",
    )
    operator_settings.upsert_public_booking_type(
        slug="school-intake",
        page_title="School intake call",
        page_description="Claim a school planning slot.",
        duration_minutes=30,
        search_window_days=21,
        success_message="School intake booked.",
        target_calendar_url="https://caldav.icloud.com/school/",
        booking_weekdays=[0, 2, 4],
        day_start_time="10:00",
        day_end_time="14:00",
        set_as_default=False,
    )
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: FakeAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    setup_response = client.get("/booking/setup?booking_slug=school-intake")

    assert setup_response.status_code == 200
    assert "School intake call" in setup_response.text
    assert "/book/school-intake" in setup_response.text

    booking_response = client.get(
        "/book/school-intake?availability_date_from=2026-06-01&availability_date_to=2026-06-02&availability_duration_minutes=30"
    )

    assert booking_response.status_code == 200
    assert "School intake call" in booking_response.text
    assert "Claim a school planning slot." in booking_response.text
    assert 'value="30"' in booking_response.text
    assert 'action="/book/school-intake"' in booking_response.text


def test_booking_setup_can_create_a_new_booking_type_from_current_defaults(
    monkeypatch,
) -> None:
    _configure_test_env(monkeypatch)
    operator_settings = OperatorSettingsService(settings=get_settings())
    operator_settings.set_public_booking_settings(
        page_title="Book time with Kayra",
        page_description="Choose a calm household scheduling slot.",
        duration_minutes=45,
        search_window_days=28,
        success_message="You're booked.",
        target_calendar_url="https://caldav.icloud.com/calendar/",
        booking_weekdays=[0, 1, 2, 3, 4],
        day_start_time="09:00",
        day_end_time="15:00",
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/booking/setup/types",
        data={
            "new_page_title": "Therapy intake",
            "new_booking_slug": "therapy-intake",
        },
    )

    assert response.status_code == 200
    assert "Public booking type saved securely." in response.text
    assert "Therapy intake" in response.text
    assert "/book/therapy-intake" in response.text


def test_public_booking_root_shows_a_catalog_when_multiple_types_exist(
    monkeypatch,
) -> None:
    _configure_test_env(monkeypatch)
    operator_settings = OperatorSettingsService(settings=get_settings())
    operator_settings.set_public_booking_settings(
        page_title="Book time with Kayra",
        page_description="Choose a calm household scheduling slot.",
        duration_minutes=45,
        search_window_days=28,
        success_message="You're booked.",
        target_calendar_url="https://caldav.icloud.com/calendar/",
        booking_weekdays=[0, 1, 2, 3, 4],
        day_start_time="09:00",
        day_end_time="15:00",
    )
    operator_settings.upsert_public_booking_type(
        slug="school-intake",
        page_title="School intake call",
        page_description="Claim a school planning slot.",
        duration_minutes=30,
        search_window_days=21,
        success_message="School intake booked.",
        target_calendar_url="https://caldav.icloud.com/school/",
        booking_weekdays=[0, 2, 4],
        day_start_time="10:00",
        day_end_time="14:00",
        set_as_default=False,
    )
    operator_settings.upsert_public_booking_type(
        slug="family-follow-up",
        page_title="Family follow-up",
        page_description="Book a longer family follow-up.",
        duration_minutes=60,
        search_window_days=14,
        success_message="Family follow-up booked.",
        target_calendar_url="https://caldav.icloud.com/family/",
        booking_weekdays=[1, 3],
        day_start_time="11:00",
        day_end_time="16:00",
        set_as_default=True,
    )
    app = create_app()
    client = TestClient(app)

    response = client.get("/book")

    assert response.status_code == 200
    assert "Choose a booking type" in response.text
    assert "School intake call" in response.text
    assert "Family follow-up" in response.text
    assert "/book/school-intake" in response.text
    assert "/book/family-follow-up" in response.text
    assert 'action="/book"' not in response.text


def test_booking_setup_can_make_an_existing_type_the_default(
    monkeypatch,
) -> None:
    _configure_test_env(monkeypatch)
    operator_settings = OperatorSettingsService(settings=get_settings())
    operator_settings.set_public_booking_settings(
        page_title="Book time with Kayra",
        page_description="Choose a calm household scheduling slot.",
        duration_minutes=45,
        search_window_days=28,
        success_message="You're booked.",
        target_calendar_url="https://caldav.icloud.com/calendar/",
        booking_weekdays=[0, 1, 2, 3, 4],
        day_start_time="09:00",
        day_end_time="15:00",
    )
    operator_settings.upsert_public_booking_type(
        slug="school-intake",
        page_title="School intake call",
        page_description="Claim a school planning slot.",
        duration_minutes=30,
        search_window_days=21,
        success_message="School intake booked.",
        target_calendar_url="https://caldav.icloud.com/school/",
        booking_weekdays=[0, 2, 4],
        day_start_time="10:00",
        day_end_time="14:00",
        set_as_default=False,
    )
    operator_settings.upsert_public_booking_type(
        slug="family-follow-up",
        page_title="Family follow-up",
        page_description="Book a longer family follow-up.",
        duration_minutes=60,
        search_window_days=14,
        success_message="Family follow-up booked.",
        target_calendar_url="https://caldav.icloud.com/family/",
        booking_weekdays=[1, 3],
        day_start_time="11:00",
        day_end_time="16:00",
        set_as_default=True,
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/booking/setup/types/default",
        data={"booking_slug": "school-intake"},
    )

    assert response.status_code == 200
    assert "Default booking type updated." in response.text
    assert 'href="/booking/setup?booking_slug=school-intake"' in response.text
    assert "Default type" in response.text

    booking_types = operator_settings.describe_public_booking_types()
    school_type = next(item for item in booking_types if item["slug"] == "school-intake")
    family_type = next(
        item for item in booking_types if item["slug"] == "family-follow-up"
    )
    assert school_type["is_default"] is True
    assert family_type["is_default"] is False


def test_booking_setup_can_delete_an_existing_booking_type(
    monkeypatch,
) -> None:
    _configure_test_env(monkeypatch)
    operator_settings = OperatorSettingsService(settings=get_settings())
    operator_settings.set_public_booking_settings(
        page_title="Book time with Kayra",
        page_description="Choose a calm household scheduling slot.",
        duration_minutes=45,
        search_window_days=28,
        success_message="You're booked.",
        target_calendar_url="https://caldav.icloud.com/calendar/",
        booking_weekdays=[0, 1, 2, 3, 4],
        day_start_time="09:00",
        day_end_time="15:00",
    )
    operator_settings.upsert_public_booking_type(
        slug="school-intake",
        page_title="School intake call",
        page_description="Claim a school planning slot.",
        duration_minutes=30,
        search_window_days=21,
        success_message="School intake booked.",
        target_calendar_url="https://caldav.icloud.com/school/",
        booking_weekdays=[0, 2, 4],
        day_start_time="10:00",
        day_end_time="14:00",
        set_as_default=False,
    )
    operator_settings.upsert_public_booking_type(
        slug="family-follow-up",
        page_title="Family follow-up",
        page_description="Book a longer family follow-up.",
        duration_minutes=60,
        search_window_days=14,
        success_message="Family follow-up booked.",
        target_calendar_url="https://caldav.icloud.com/family/",
        booking_weekdays=[1, 3],
        day_start_time="11:00",
        day_end_time="16:00",
        set_as_default=True,
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/booking/setup/types/delete",
        data={"booking_slug": "school-intake"},
    )

    assert response.status_code == 200
    assert "Booking type deleted." in response.text
    assert 'href="/booking/setup?booking_slug=school-intake"' not in response.text
    assert "/book/school-intake" not in response.text
    assert "Family follow-up" in response.text

    booking_types = operator_settings.describe_public_booking_types()
    assert [item["slug"] for item in booking_types] == ["family-follow-up"]


def test_connections_page_renders_provider_summary(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
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
    app = create_app()
    client = TestClient(app)

    response = client.get("/connections")

    assert response.status_code == 200
    assert "Connections" in response.text
    assert "Household calendar path" in response.text
    assert "Browser-connected Google path" in response.text
    assert "Open Apple setup" in response.text
    assert "Open Google setup" in response.text
    assert 'href="/auth/google/start"' in response.text
    assert '<button type="button" disabled>Connect Microsoft account</button>' in response.text
    assert "Save the shared Microsoft OAuth app before browser account connect is available." in response.text
    assert 'href="/auth/microsoft/start"' not in response.text


def test_connections_page_shows_apple_recovery_guidance_when_legacy_hints_exist(
    monkeypatch,
) -> None:
    db_path = Path(tempfile.gettempdir()) / f"calsync-ui-test-{uuid4()}.db"
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
    service = OperatorSettingsService(settings=get_settings())
    service.set_legacy_apple_recovery_hints(
        {
            "source_filename": "calsync-db-backup.zip",
            "account_label": "kaymayers9@gmail.com",
            "account_username": "kaymayers9@gmail.com",
            "calendar_home_url": "https://p52-caldav.icloud.com:443/112135872/calendars/",
            "principal_url": "https://caldav.icloud.com/112135872/principal/",
            "recommended_calendar_name": "Calendar",
            "recommended_calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/6824BCB8-8CEE-4733-9208-4741C62E266C/",
            "calendar_count": 1,
            "calendars": [
                {
                    "calendar_name": "Calendar",
                    "calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/6824BCB8-8CEE-4733-9208-4741C62E266C/",
                    "calendar_role": "writable_booking_target",
                    "enabled": True,
                    "is_writable_hint": True,
                }
            ],
        }
    )
    app = create_app()
    client = TestClient(app)

    response = client.get("/connections")

    assert response.status_code == 200
    assert "Recovered Apple hints are ready. Apple setup already opens with the recommended calendar loaded, so add a fresh app-specific password and save." in response.text
    assert "Recovery hint available" in response.text
    assert "Recovered account: kaymayers9@gmail.com" in response.text
    assert "Open Apple setup" in response.text
    assert "Load recovered Apple hint" not in response.text
    assert "open Apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password" in response.text


def test_connections_page_shows_checklist_and_verification_state(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
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
    service.record_calendar_write_verification(
        target_value="https://caldav.icloud.com/family/",
        provider_type="apple",
        provider_label="Apple Calendar",
        account_label="Family",
        calendar_name="Family",
        passed=True,
        message="Write test passed for Family on Apple Calendar (Family).",
        checked_at="2026-05-29T22:30:00+00:00",
    )
    app = create_app()
    client = TestClient(app)

    response = client.get("/connections")

    assert response.status_code == 200
    assert "Setup checklist" in response.text
    assert "Verification center" in response.text
    assert "Last write proof" in response.text
    assert "Write test passed for Family on Apple Calendar (Family)." in response.text
    assert "Run write test" in response.text


def test_connections_page_shows_multiple_google_accounts(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
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
    app = create_app()
    client = TestClient(app)

    response = client.get("/connections")

    assert response.status_code == 200
    assert "2 connected accounts" in response.text
    assert "kay@example.com" in response.text
    assert "work@example.com" in response.text


def test_connections_page_renders_microsoft_summary(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
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
    app = create_app()
    client = TestClient(app)

    response = client.get("/connections")

    assert response.status_code == 200
    assert "Browser-connected Outlook path" in response.text
    assert "Open Microsoft setup" in response.text


def test_connections_page_shows_direct_provider_control_actions(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
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
    service.set_microsoft_oauth_settings(
        client_id="microsoft-client-id",
        client_secret="microsoft-client-secret",
    )
    service.set_microsoft_account_settings(
        account_label="Kay Microsoft",
        account_email="kay@outlook.com",
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
    app = create_app()
    client = TestClient(app)

    response = client.get("/connections")

    assert response.status_code == 200
    assert "Connect another Google account" in response.text
    assert 'href="/auth/google/start"' in response.text
    assert "Refresh Google calendars" in response.text
    assert "Disconnect Google account" in response.text
    assert "Connect another Microsoft account" in response.text
    assert 'href="/auth/microsoft/start"' in response.text
    assert "Refresh Microsoft calendars" in response.text
    assert "Disconnect Microsoft account" in response.text


def test_connections_page_shows_alexa_turn_on_controls(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())
    service.set_desired_alexa_settings(
        enable_alexa=True,
        allowed_skill_ids=["amzn1.ask.skill.saved"],
    )

    class FakeCloudflareWorkerConfigService:
        def get_alexa_settings(self):
            return {
                "worker_name": "edge-calsync",
                "enable_alexa": False,
                "allowed_skill_ids": [],
                "manageable": True,
                "credential_source": "product_vault",
                "message": "Ready to configure the edge Worker from the product.",
            }

    monkeypatch.setattr(
        "calsync.web.routes.console.CloudflareWorkerConfigService",
        FakeCloudflareWorkerConfigService,
    )
    app = create_app()
    client = TestClient(app)

    response = client.get("/connections")

    assert response.status_code == 200
    assert "Last-mile turn-on" in response.text
    assert "Apply Alexa settings" in response.text
    assert (
        "This will save the desired Alexa plan in CalSync and update the live edge Worker now."
        in response.text
    )
    assert "Writable calendar" in response.text
    assert "Ready" in response.text
    assert "Alexa already has a real writable calendar path behind the shared scheduling brain." in response.text
    assert "Desired settings" in response.text
    assert "Saved" in response.text
    assert "Saved plan: enable Alexa." in response.text
    assert "Open Alexa setup" in response.text
    assert "Open Alexa simulator" in response.text
    assert "amzn1.ask.skill.saved" in response.text
    assert "Desired Alexa settings differ from the live Worker and still need to be applied." in response.text
    assert "Account linking" in response.text
    assert "Save a household link code so Alexa can link the live skill to this CalSync household." in response.text


def test_connections_page_shows_ready_account_linking_state(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())
    service.set_alexa_account_linking_settings(link_code="Family123")

    class FakeCloudflareWorkerConfigService:
        def get_alexa_settings(self):
            return {
                "worker_name": "edge-calsync",
                "enable_alexa": False,
                "allowed_skill_ids": [],
                "manageable": True,
                "credential_source": "product_vault",
                "message": "Ready to configure the edge Worker from the product.",
            }

    monkeypatch.setattr(
        "calsync.web.routes.console.CloudflareWorkerConfigService",
        FakeCloudflareWorkerConfigService,
    )
    app = create_app()
    client = TestClient(app)

    response = client.get("/connections")

    assert response.status_code == 200
    assert "Account linking" in response.text
    assert "Ready" in response.text
    assert "A household link code and bearer token are already saved for the live skill." in response.text


def test_connections_page_can_save_desired_alexa_settings(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())

    class FakeCloudflareWorkerConfigService:
        def __init__(self):
            self.called = False

        def get_alexa_settings(self):
            return {
                "worker_name": "edge-calsync",
                "enable_alexa": False,
                "allowed_skill_ids": [],
                "manageable": True,
                "credential_source": "product_vault",
                "message": "Ready to configure the edge Worker from the product.",
            }

        def update_alexa_settings(self, *, enable_alexa: bool, allowed_skill_ids: list[str]):
            assert enable_alexa is True
            assert allowed_skill_ids == ["amzn1.ask.skill.real"]
            self.called = True

    fake_service = FakeCloudflareWorkerConfigService()
    monkeypatch.setattr(
        "calsync.web.routes.console.CloudflareWorkerConfigService",
        lambda: fake_service,
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/connections/alexa",
        data={
            "enable_alexa": "true",
            "allowed_skill_ids": "amzn1.ask.skill.real",
        },
    )

    assert response.status_code == 200
    assert fake_service.called is True
    assert "Desired Alexa settings saved and edge Worker updated." in response.text
    assert service.get_desired_alexa_settings() == {
        "enable_alexa": True,
        "allowed_skill_ids": ["amzn1.ask.skill.real"],
    }


def test_connections_page_can_save_desired_alexa_settings_without_manageable_worker(
    monkeypatch,
) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())

    class FakeCloudflareWorkerConfigService:
        def get_alexa_settings(self):
            return {
                "worker_name": "edge-calsync",
                "enable_alexa": False,
                "allowed_skill_ids": [],
                "manageable": False,
                "credential_source": "missing",
                "message": "Cloudflare worker management is not configured for this deployment.",
            }

        def update_alexa_settings(self, *, enable_alexa: bool, allowed_skill_ids: list[str]):
            raise ValueError(
                "Cloudflare worker management is not configured for this deployment."
            )

    monkeypatch.setattr(
        "calsync.web.routes.console.CloudflareWorkerConfigService",
        FakeCloudflareWorkerConfigService,
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/connections/alexa",
        data={
            "enable_alexa": "true",
            "allowed_skill_ids": "amzn1.ask.skill.saved",
        },
    )

    assert response.status_code == 200
    assert "Desired Alexa settings saved securely." in response.text
    assert "Cloudflare worker management is not configured for this deployment." in response.text
    assert "Save desired Alexa settings" in response.text
    assert (
        "Cloudflare Worker access is still missing, so this will save the desired Alexa plan in CalSync until live edge updates are available."
        in response.text
    )
    assert service.get_desired_alexa_settings() == {
        "enable_alexa": True,
        "allowed_skill_ids": ["amzn1.ask.skill.saved"],
    }


def test_alexa_setup_page_shows_voice_specific_next_guidance(monkeypatch) -> None:
    db_path = Path(tempfile.gettempdir()) / f"calsync-ui-test-{uuid4()}.db"
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
    app = create_app()
    client = TestClient(app)

    response = client.get("/alexa/setup")

    assert response.status_code == 200
    assert (
        "Connect at least one writable calendar, then save a household link code and Cloudflare Worker access so CalSync can finish Alexa account linking and live edge turn-on."
        in response.text
    )
    assert (
        "Add an Apple calendar or finish Google or Microsoft setup so CalSync can read and write a real connected calendar."
        not in response.text
    )


def test_connections_page_shows_voice_specific_alexa_guidance(monkeypatch) -> None:
    db_path = Path(tempfile.gettempdir()) / f"calsync-ui-test-{uuid4()}.db"
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
    app = create_app()
    client = TestClient(app)

    response = client.get("/connections")

    assert response.status_code == 200
    assert "Alexa voice path" in response.text
    assert "Writable calendar" in response.text
    assert "Needs setup" in response.text
    assert "Connect a writable calendar so Alexa has a real household schedule to read and write." in response.text
    assert "Desired settings" in response.text
    assert "Not saved yet" in response.text
    assert "No desired Alexa edge state has been saved in the product yet." in response.text
    assert (
        "Connect at least one writable calendar, then save a household link code and Cloudflare Worker access so CalSync can finish Alexa account linking and live edge turn-on."
        in response.text
    )
    assert "Account linking" in response.text


def test_connections_page_can_download_encrypted_settings_backup(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())
    service.set_apple_calendar_settings(
        account_label="Family",
        username="family@example.com",
        app_specific_password="secret",
        primary_calendar_url="https://caldav.icloud.com/family/",
        primary_calendar_name="Family",
    )
    app = create_app()
    client = TestClient(app)

    response = client.get("/connections/settings-backup")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    payload = json.loads(response.text)
    assert payload["kind"] == "calsync_operator_settings_backup"
    assert payload["setting_count"] >= 5
    assert "encrypted_payload" in payload
    assert "family@example.com" not in response.text


def test_connections_page_can_restore_encrypted_settings_backup(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())
    service.set_apple_calendar_settings(
        account_label="Family",
        username="family@example.com",
        app_specific_password="secret",
        primary_calendar_url="https://caldav.icloud.com/family/",
        primary_calendar_name="Family",
    )
    backup_payload = service.export_operator_settings_backup()["backup_json"].encode(
        "utf-8"
    )
    for key in (
        "apple_account_label",
        "apple_username",
        "apple_app_specific_password",
        "apple_primary_calendar_url",
        "apple_primary_calendar_name",
    ):
        service.delete_value(key)

    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/connections/settings-restore",
        files={
            "backup_file": (
                "calsync-operator-settings-backup.json",
                backup_payload,
                "application/json",
            )
        },
    )

    assert response.status_code == 200
    assert "Operator settings restored from encrypted backup." in response.text
    assert service.get_apple_calendar_settings()["username"] == "family@example.com"


def test_connections_page_can_import_legacy_backup_apple_hints(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/connections/legacy-backup/import",
        files={
            "backup_file": (
                "calsync-db-backup.zip",
                _legacy_backup_payload(),
                "application/zip",
            )
        },
    )

    assert response.status_code == 200
    assert "Legacy Apple recovery hints imported from backup." in response.text

    service = OperatorSettingsService(settings=get_settings())
    described = service.describe_legacy_apple_recovery_hints()
    assert described["account_username"] == "kaymayers9@gmail.com"
    assert described["recommended_calendar_name"] == "Family"


def test_connections_google_refresh_updates_live_calendar_catalog(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())
    service.set_google_oauth_settings(
        client_id="google-client-id",
        client_secret="google-client-secret",
    )
    service.upsert_google_account(
        account_label="Old Label",
        account_email="old@example.com",
        refresh_token="google-refresh-token",
        calendars=[
            {
                "calendar_name": "Old Primary",
                "calendar_id": "old-primary",
                "is_default": True,
            }
        ],
    )

    class FakeGoogleCalendarClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def current_user_email(self, *, access_token: str | None = None) -> str:
            assert access_token is None
            return "kay@example.com"

        def list_calendars(self, *, access_token: str | None = None):
            assert access_token is None
            return [
                {
                    "calendar_name": "Primary",
                    "calendar_id": "primary",
                    "is_default": True,
                }
            ]

    monkeypatch.setattr(
        "calsync.web.routes.console.GoogleCalendarClient",
        FakeGoogleCalendarClient,
    )
    app = create_app()
    client = TestClient(app)

    response = client.post("/connections/google/refresh?account_email=old@example.com")

    assert response.status_code == 200
    assert "Connections" in response.text
    assert "Google calendars refreshed from the live account." in response.text
    assert "kay@example.com" in response.text


def test_connections_microsoft_disconnect_clears_account_and_stays_on_connections(
    monkeypatch,
) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())
    service.set_microsoft_oauth_settings(
        client_id="microsoft-client-id",
        client_secret="microsoft-client-secret",
    )
    service.set_microsoft_account_settings(
        account_label="Kay Microsoft",
        account_email="kay@outlook.com",
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
    app = create_app()
    client = TestClient(app)

    response = client.post("/connections/microsoft/disconnect?account_email=kay@outlook.com")

    assert response.status_code == 200
    assert "Connections" in response.text
    assert "Microsoft account disconnected. The shared OAuth app is still saved." in response.text
    assert service.get_microsoft_account_settings() == {
        "account_label": None,
        "account_email": None,
        "refresh_token": None,
    }


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
    assert "Appointment created on the connected calendar." in response.text
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
    assert "Appointment updated on the connected calendar." in response.text
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
    assert "Appointment cancelled on the connected calendar." in response.text
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


def test_google_setup_page_renders_oauth_connect_surface(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    app = create_app()
    client = TestClient(app)

    response = client.get("/google/setup")

    assert response.status_code == 200
    assert "Google setup" in response.text
    assert "Save Google OAuth setup" in response.text
    assert "Connect Google account" in response.text
    assert '<button type="button" disabled>Connect Google account</button>' in response.text
    assert "Save the shared Google OAuth app before connecting a Google account." in response.text
    assert 'href="/auth/google/start"' not in response.text


def test_google_setup_page_shows_refresh_and_disconnect_for_connected_account(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
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
    app = create_app()
    client = TestClient(app)

    response = client.get("/google/setup")

    assert response.status_code == 200
    assert "Connect another Google account" in response.text
    assert 'href="/auth/google/start"' in response.text
    assert "Refresh calendars" in response.text
    assert "Disconnect this account" in response.text


def test_google_oauth_start_redirects_with_saved_state(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())
    service.set_google_oauth_settings(
        client_id="google-client-id",
        client_secret="google-client-secret",
    )
    app = create_app()
    client = TestClient(app)

    response = client.get("/auth/google/start", follow_redirects=False)

    assert response.status_code == 302
    redirect_target = response.headers["location"]
    parsed = urlparse(redirect_target)
    query = parse_qs(parsed.query)
    assert parsed.netloc == "accounts.google.com"
    assert query["client_id"] == ["google-client-id"]
    assert query["scope"] == [
        "openid email profile https://www.googleapis.com/auth/calendar"
    ]
    saved_state = service.get_google_oauth_state()
    assert saved_state
    assert query["state"] == [saved_state]


def test_google_oauth_callback_saves_account_and_clears_state(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())
    service.set_google_oauth_settings(
        client_id="google-client-id",
        client_secret="google-client-secret",
    )
    service.set_google_oauth_state("state-123")

    class FakeGoogleCalendarClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def exchange_code(self, *, code: str, redirect_uri: str):
            assert code == "real-code"
            assert redirect_uri.endswith("/auth/google/callback")
            return {
                "refresh_token": "google-refresh-token",
                "access_token": "google-access-token",
            }

        def current_user_email(self, *, access_token: str | None = None) -> str:
            assert access_token == "google-access-token"
            return "kay@example.com"

        def list_calendars(self, *, access_token: str | None = None):
            assert access_token == "google-access-token"
            return [
                {
                    "calendar_name": "Primary",
                    "calendar_id": "primary",
                    "is_default": True,
                }
            ]

    monkeypatch.setattr(
        "calsync.web.routes.console.GoogleCalendarClient",
        FakeGoogleCalendarClient,
    )
    app = create_app()
    client = TestClient(app)

    response = client.get("/auth/google/callback?state=state-123&code=real-code")

    assert response.status_code == 200
    assert "Google account connected and calendars discovered." in response.text
    assert service.get_google_oauth_state() is None
    assert service.get_google_account_settings() == {
        "account_label": "kay@example.com",
        "account_email": "kay@example.com",
        "refresh_token": "google-refresh-token",
    }
    assert service.get_google_calendar_catalog() == [
        {
            "calendar_name": "Primary",
            "calendar_id": "primary",
            "is_default": True,
        }
    ]


def test_google_oauth_callback_can_append_another_google_account(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())
    service.set_google_oauth_settings(
        client_id="google-client-id",
        client_secret="google-client-secret",
    )
    service.upsert_google_account(
        account_label="kay@example.com",
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
    service.set_google_oauth_state("state-456")

    class FakeGoogleCalendarClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def exchange_code(self, *, code: str, redirect_uri: str):
            assert code == "work-code"
            assert redirect_uri.endswith("/auth/google/callback")
            return {
                "refresh_token": "work-refresh-token",
                "access_token": "work-access-token",
            }

        def current_user_email(self, *, access_token: str | None = None) -> str:
            assert access_token == "work-access-token"
            return "work@example.com"

        def list_calendars(self, *, access_token: str | None = None):
            assert access_token == "work-access-token"
            return [
                {
                    "calendar_name": "Work",
                    "calendar_id": "work",
                    "is_default": True,
                }
            ]

    monkeypatch.setattr(
        "calsync.web.routes.console.GoogleCalendarClient",
        FakeGoogleCalendarClient,
    )
    app = create_app()
    client = TestClient(app)

    response = client.get("/auth/google/callback?state=state-456&code=work-code")

    assert response.status_code == 200
    assert "Google account connected and calendars discovered." in response.text
    assert "Connected Google accounts" in response.text
    assert "kay@example.com" in response.text
    assert "work@example.com" in response.text
    assert service.get_google_accounts() == [
        {
            "account_label": "kay@example.com",
            "account_email": "kay@example.com",
            "refresh_token": "kay-refresh-token",
            "calendars": [
                {
                    "calendar_name": "Primary",
                    "calendar_id": "primary",
                    "is_default": True,
                }
            ],
        },
        {
            "account_label": "work@example.com",
            "account_email": "work@example.com",
            "refresh_token": "work-refresh-token",
            "calendars": [
                {
                    "calendar_name": "Work",
                    "calendar_id": "work",
                    "is_default": True,
                }
            ],
        },
    ]


def test_google_setup_refresh_updates_live_calendar_catalog(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())
    service.set_google_oauth_settings(
        client_id="google-client-id",
        client_secret="google-client-secret",
    )
    service.set_google_account_settings(
        account_label="Old Label",
        account_email="old@example.com",
        refresh_token="google-refresh-token",
    )
    service.set_google_calendar_catalog(
        [
            {
                "calendar_name": "Old Primary",
                "calendar_id": "old-primary",
                "is_default": True,
            }
        ]
    )

    class FakeGoogleCalendarClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def current_user_email(self, *, access_token: str | None = None) -> str:
            assert access_token is None
            return "kay@example.com"

        def list_calendars(self, *, access_token: str | None = None):
            assert access_token is None
            return [
                {
                    "calendar_name": "Primary",
                    "calendar_id": "primary",
                    "is_default": True,
                },
                {
                    "calendar_name": "Work",
                    "calendar_id": "work",
                    "is_default": False,
                },
            ]

    monkeypatch.setattr(
        "calsync.web.routes.console.GoogleCalendarClient",
        FakeGoogleCalendarClient,
    )
    app = create_app()
    client = TestClient(app)

    response = client.post("/google/setup/refresh")

    assert response.status_code == 200
    assert "Google calendars refreshed from the live account." in response.text
    assert service.get_google_account_settings() == {
        "account_label": "kay@example.com",
        "account_email": "kay@example.com",
        "refresh_token": "google-refresh-token",
    }
    assert service.get_google_calendar_catalog() == [
        {
            "calendar_name": "Primary",
            "calendar_id": "primary",
            "is_default": True,
        },
        {
            "calendar_name": "Work",
            "calendar_id": "work",
            "is_default": False,
        },
    ]


def test_google_setup_disconnect_clears_account_but_keeps_oauth_app(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
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
    app = create_app()
    client = TestClient(app)

    response = client.post("/google/setup/disconnect")

    assert response.status_code == 200
    assert "Google account disconnected. The shared OAuth app is still saved." in response.text
    assert service.get_google_oauth_settings() == {
        "client_id": "google-client-id",
        "client_secret": "google-client-secret",
    }
    assert service.get_google_account_settings() == {
        "account_label": None,
        "account_email": None,
        "refresh_token": None,
    }
    assert service.get_google_calendar_catalog() == []


def test_microsoft_setup_page_renders_oauth_connect_surface(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    app = create_app()
    client = TestClient(app)

    response = client.get("/microsoft/setup")

    assert response.status_code == 200
    assert "Microsoft setup" in response.text
    assert "Save Microsoft OAuth setup" in response.text
    assert "Connect Microsoft account" in response.text
    assert '<button type="button" disabled>Connect Microsoft account</button>' in response.text
    assert "Save the shared Microsoft OAuth app before connecting a Microsoft account." in response.text
    assert 'href="/auth/microsoft/start"' not in response.text


def test_microsoft_setup_page_shows_connect_link_when_oauth_app_is_saved(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())
    service.set_microsoft_oauth_settings(
        client_id="microsoft-client-id",
        client_secret="microsoft-client-secret",
    )
    app = create_app()
    client = TestClient(app)

    response = client.get("/microsoft/setup")

    assert response.status_code == 200
    assert "Connect Microsoft account" in response.text
    assert 'href="/auth/microsoft/start"' in response.text


def test_microsoft_oauth_start_redirects_with_saved_state(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())
    service.set_microsoft_oauth_settings(
        client_id="microsoft-client-id",
        client_secret="microsoft-client-secret",
    )
    app = create_app()
    client = TestClient(app)

    response = client.get("/auth/microsoft/start", follow_redirects=False)

    assert response.status_code == 302
    redirect_target = response.headers["location"]
    parsed = urlparse(redirect_target)
    query = parse_qs(parsed.query)
    assert parsed.netloc == "login.microsoftonline.com"
    assert query["client_id"] == ["microsoft-client-id"]
    assert query["scope"] == ["offline_access openid User.Read Calendars.ReadWrite"]
    saved_state = service.get_microsoft_oauth_state()
    assert saved_state
    assert query["state"] == [saved_state]


def test_microsoft_oauth_callback_saves_account_and_clears_state(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())
    service.set_microsoft_oauth_settings(
        client_id="microsoft-client-id",
        client_secret="microsoft-client-secret",
    )
    service.set_microsoft_oauth_state("microsoft-state-123")

    class FakeMicrosoftCalendarClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def exchange_code(self, *, code: str, redirect_uri: str):
            assert code == "real-code"
            assert redirect_uri.endswith("/auth/microsoft/callback")
            return {
                "refresh_token": "microsoft-refresh-token",
                "access_token": "microsoft-access-token",
            }

        def current_user_email(self, *, access_token: str | None = None) -> str:
            assert access_token == "microsoft-access-token"
            return "kay@example.com"

        def list_calendars(self, *, access_token: str | None = None):
            assert access_token == "microsoft-access-token"
            return [
                {
                    "calendar_name": "Calendar",
                    "calendar_id": "primary",
                    "is_default": True,
                }
            ]

    monkeypatch.setattr(
        "calsync.web.routes.console.MicrosoftCalendarClient",
        FakeMicrosoftCalendarClient,
    )
    app = create_app()
    client = TestClient(app)

    response = client.get("/auth/microsoft/callback?state=microsoft-state-123&code=real-code")

    assert response.status_code == 200
    assert "Microsoft account connected and calendars discovered." in response.text
    assert service.get_microsoft_oauth_state() is None
    assert service.get_microsoft_account_settings() == {
        "account_label": "kay@example.com",
        "account_email": "kay@example.com",
        "refresh_token": "microsoft-refresh-token",
    }
    assert service.get_microsoft_calendar_catalog() == [
        {
            "calendar_name": "Calendar",
            "calendar_id": "primary",
            "is_default": True,
        }
    ]


def test_microsoft_setup_disconnect_clears_account_but_keeps_oauth_app(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
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
    app = create_app()
    client = TestClient(app)

    response = client.post("/microsoft/setup/disconnect")

    assert response.status_code == 200
    assert "Microsoft account disconnected. The shared OAuth app is still saved." in response.text
    assert service.get_microsoft_oauth_settings() == {
        "client_id": "microsoft-client-id",
        "client_secret": "microsoft-client-secret",
    }
    assert service.get_microsoft_account_settings() == {
        "account_label": None,
        "account_email": None,
        "refresh_token": None,
    }
    assert service.get_microsoft_calendar_catalog() == []


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
    service = OperatorSettingsService(settings=get_settings())
    service.set_desired_alexa_settings(
        enable_alexa=True,
        allowed_skill_ids=["amzn1.ask.skill.saved"],
    )

    class FakeCloudflareWorkerConfigService:
        def get_alexa_settings(self):
            return {
                "worker_name": "edge-calsync",
                "enable_alexa": False,
                "allowed_skill_ids": [],
                "manageable": True,
                "credential_source": "product_vault",
                "message": "Ready to configure the edge Worker from the product.",
            }

    monkeypatch.setattr(
        "calsync.web.routes.console.CloudflareWorkerConfigService",
        FakeCloudflareWorkerConfigService,
    )
    app = create_app()
    client = TestClient(app)

    response = client.get("/alexa/setup")

    assert response.status_code == 200
    assert "Alexa setup" in response.text
    assert "Download skill package" in response.text
    assert "https://edge-calsync.neonbutterfly.net/alexa" in response.text
    assert "/alexa/simulator" in response.text
    assert "/calendar/setup" in response.text
    assert "Edge Worker controls" in response.text
    assert 'name="cloudflare_account_id"' in response.text
    assert 'name="cloudflare_api_token"' in response.text
    assert "Cloudflare worker access" in response.text
    assert 'name="allowed_skill_ids"' in response.text
    assert "Apply edge settings" in response.text
    assert (
        "This will save the desired Alexa plan in CalSync and update the live edge Worker now."
        in response.text
    )
    assert "Desired Alexa settings" in response.text
    assert "Pending edge changes" in response.text
    assert "amzn1.ask.skill.saved" in response.text
    assert "Writable calendar connected:" in response.text
    assert "Cloudflare Worker access configured:" in response.text
    assert "Desired Alexa settings saved:" in response.text
    assert "Desired Alexa settings saved:</strong>\n                  Yes" in response.text
    assert ">No<" in response.text
    assert "Account linking configured:" in response.text
    assert ">No<" in response.text


def test_alexa_setup_page_shows_cloudflare_permission_error(monkeypatch) -> None:
    _configure_test_env(monkeypatch)

    class FakeCloudflareWorkerConfigService:
        def get_alexa_settings(self):
            return {
                "worker_name": "edge-calsync",
                "enable_alexa": False,
                "allowed_skill_ids": [],
                "manageable": False,
                "credential_source": "missing",
                "message": "Cloudflare API token needs Workers Scripts permission.",
            }

    monkeypatch.setattr(
        "calsync.web.routes.console.CloudflareWorkerConfigService",
        FakeCloudflareWorkerConfigService,
    )
    app = create_app()
    client = TestClient(app)

    response = client.get("/alexa/setup")

    assert response.status_code == 200
    assert "Cloudflare API token needs Workers Scripts permission." in response.text
    assert "Save desired Alexa settings" in response.text
    assert (
        "Cloudflare Worker access is still missing, so this will save the desired Alexa plan in CalSync until live edge updates are available."
        in response.text
    )


def test_alexa_setup_page_updates_edge_settings(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())

    class FakeCloudflareWorkerConfigService:
        def __init__(self):
            self.called = False

        def get_alexa_settings(self):
            return {
                "worker_name": "edge-calsync",
                "enable_alexa": False,
                "allowed_skill_ids": [],
                "manageable": True,
                "credential_source": "product_vault",
                "message": "Ready to configure the edge Worker from the product.",
            }

        def update_alexa_settings(self, *, enable_alexa: bool, allowed_skill_ids: list[str]):
            assert enable_alexa is True
            assert allowed_skill_ids == ["amzn1.ask.skill.real"]
            self.called = True

    fake_service = FakeCloudflareWorkerConfigService()
    monkeypatch.setattr(
        "calsync.web.routes.console.CloudflareWorkerConfigService",
        lambda: fake_service,
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/alexa/setup",
        data={
            "enable_alexa": "true",
            "allowed_skill_ids": "amzn1.ask.skill.real",
        },
    )

    assert response.status_code == 200
    assert fake_service.called is True
    assert "Desired Alexa settings saved and edge Worker updated." in response.text
    assert service.get_desired_alexa_settings() == {
        "enable_alexa": True,
        "allowed_skill_ids": ["amzn1.ask.skill.real"],
    }


def test_alexa_setup_page_saves_desired_settings_even_when_worker_is_not_manageable(
    monkeypatch,
) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())

    class FakeCloudflareWorkerConfigService:
        def get_alexa_settings(self):
            return {
                "worker_name": "edge-calsync",
                "enable_alexa": False,
                "allowed_skill_ids": [],
                "manageable": False,
                "credential_source": "missing",
                "message": "Cloudflare worker management is not configured for this deployment.",
            }

        def update_alexa_settings(self, *, enable_alexa: bool, allowed_skill_ids: list[str]):
            raise ValueError(
                "Cloudflare worker management is not configured for this deployment."
            )

    monkeypatch.setattr(
        "calsync.web.routes.console.CloudflareWorkerConfigService",
        FakeCloudflareWorkerConfigService,
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/alexa/setup",
        data={
            "enable_alexa": "true",
            "allowed_skill_ids": "amzn1.ask.skill.saved",
        },
    )

    assert response.status_code == 200
    assert "Desired Alexa settings saved securely." in response.text
    assert "Cloudflare worker management is not configured for this deployment." in response.text
    assert "Save desired Alexa settings" in response.text
    assert (
        "Cloudflare Worker access is still missing, so this will save the desired Alexa plan in CalSync until live edge updates are available."
        in response.text
    )
    assert service.get_desired_alexa_settings() == {
        "enable_alexa": True,
        "allowed_skill_ids": ["amzn1.ask.skill.saved"],
    }


def test_alexa_setup_page_saves_cloudflare_credentials(monkeypatch) -> None:
    _configure_test_env(monkeypatch)

    class FakeCloudflareWorkerConfigService:
        def get_alexa_settings(self):
            return {
                "worker_name": "edge-calsync",
                "enable_alexa": False,
                "allowed_skill_ids": [],
                "manageable": True,
                "credential_source": "product_vault",
                "message": "Ready to configure the edge Worker from the product.",
            }

    monkeypatch.setattr(
        "calsync.web.routes.console.CloudflareWorkerConfigService",
        FakeCloudflareWorkerConfigService,
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/alexa/setup/cloudflare",
        data={
            "cloudflare_account_id": "acct-123",
            "cloudflare_api_token": "token-123",
        },
    )

    assert response.status_code == 200
    assert "Cloudflare Worker credentials saved securely." in response.text

    service = OperatorSettingsService(settings=get_settings())
    assert service.get_cloudflare_worker_credentials() == {
        "account_id": "acct-123",
        "api_token": "token-123",
    }


def test_alexa_setup_page_shows_account_linking_controls(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())
    service.set_alexa_account_linking_settings(link_code="Family123")

    class FakeCloudflareWorkerConfigService:
        def get_alexa_settings(self):
            return {
                "worker_name": "edge-calsync",
                "enable_alexa": False,
                "allowed_skill_ids": [],
                "manageable": True,
                "credential_source": "product_vault",
                "message": "Ready to configure the edge Worker from the product.",
            }

    monkeypatch.setattr(
        "calsync.web.routes.console.CloudflareWorkerConfigService",
        FakeCloudflareWorkerConfigService,
    )
    app = create_app()
    client = TestClient(app)

    response = client.get("/alexa/setup")

    assert response.status_code == 200
    assert "Account linking" in response.text
    assert "/alexa/account-linking/authorize" in response.text
    assert "calsync-alexa-household" in response.text
    assert "Save account linking setup" in response.text
    assert "Link code saved" in response.text
    assert "Writable calendar connected:" in response.text
    assert "Cloudflare Worker access configured:" in response.text
    assert (
        "Writable calendar connected:</strong>\n                  Yes"
        in response.text
    )
    assert (
        "Cloudflare Worker access configured:</strong>\n                  No"
        in response.text
    )
    assert "Account linking configured:" in response.text
    assert "Account linking configured:</strong>\n                  Yes" in response.text


def test_alexa_setup_page_shows_no_writable_calendar_in_step_four(monkeypatch) -> None:
    db_path = Path(tempfile.gettempdir()) / f"calsync-ui-test-{uuid4()}.db"
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
    app = create_app()
    client = TestClient(app)

    response = client.get("/alexa/setup")

    assert response.status_code == 200
    assert "Writable calendar connected:" in response.text
    assert "Cloudflare Worker access configured:" in response.text
    assert "Desired Alexa settings saved:" in response.text
    assert "Desired Alexa settings saved:</strong>\n                  No" in response.text
    assert ">No<" in response.text


def test_alexa_setup_page_shows_cloudflare_access_in_step_four(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())
    service.set_cloudflare_worker_credentials(
        account_id="acct-123",
        api_token="token-123",
    )

    class FakeCloudflareWorkerConfigService:
        def get_alexa_settings(self):
            return {
                "worker_name": "edge-calsync",
                "enable_alexa": False,
                "allowed_skill_ids": [],
                "manageable": True,
                "credential_source": "product_vault",
                "message": "Ready to configure the edge Worker from the product.",
            }

    monkeypatch.setattr(
        "calsync.web.routes.console.CloudflareWorkerConfigService",
        FakeCloudflareWorkerConfigService,
    )
    app = create_app()
    client = TestClient(app)

    response = client.get("/alexa/setup")

    assert response.status_code == 200
    assert "Cloudflare Worker access configured:" in response.text
    assert (
        "Cloudflare Worker access configured:</strong>\n                  Yes"
        in response.text
    )


def test_alexa_setup_page_can_save_account_linking_settings(monkeypatch) -> None:
    _configure_test_env(monkeypatch)

    class FakeCloudflareWorkerConfigService:
        def get_alexa_settings(self):
            return {
                "worker_name": "edge-calsync",
                "enable_alexa": False,
                "allowed_skill_ids": [],
                "manageable": True,
                "credential_source": "product_vault",
                "message": "Ready to configure the edge Worker from the product.",
            }

    monkeypatch.setattr(
        "calsync.web.routes.console.CloudflareWorkerConfigService",
        FakeCloudflareWorkerConfigService,
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/alexa/setup/account-linking",
        data={
            "link_code": "Family123",
        },
    )

    assert response.status_code == 200
    assert "Alexa account linking is ready." in response.text
    service = OperatorSettingsService(settings=get_settings())
    assert service.get_alexa_account_linking_settings()["link_code"] == "FAMILY123"


def test_alexa_account_linking_authorize_redirects_with_access_token(
    monkeypatch,
) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())
    service.set_alexa_account_linking_settings(link_code="Family123")
    app = create_app()
    client = TestClient(app)

    authorize_response = client.post(
        "/alexa/account-linking/authorize",
        data={
            "client_id": "calsync-alexa-household",
            "redirect_uri": "https://pitangui.amazon.com/spa/skill/account-linking-status.html?vendorId=test",
            "response_type": "token",
            "state": "abc123",
            "scope": "calendar:read calendar:write",
            "link_code": "Family123",
        },
        follow_redirects=False,
    )

    assert authorize_response.status_code == 302
    location = authorize_response.headers["location"]
    assert location.startswith(
        "https://pitangui.amazon.com/spa/skill/account-linking-status.html"
    )
    parsed = urlparse(location)
    fragment = parse_qs(parsed.fragment)
    assert fragment["state"] == ["abc123"]
    assert fragment["token_type"] == ["Bearer"]
    assert fragment["access_token"] == [
        service.get_alexa_account_linking_settings()["access_token"]
    ]


def test_alexa_account_linking_validate_endpoint_reports_linked_status(
    monkeypatch,
) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())
    service.set_alexa_account_linking_settings(link_code="Family123")
    access_token = service.get_alexa_account_linking_settings()["access_token"]
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/alexa/account-linking/validate",
        json={"access_token": access_token},
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "account_linking_configured": True,
        "linked": True,
    }


def test_calendar_setup_page_can_run_write_test(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
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

    def fake_run_write_smoke_test(self, *, target_calendar_url: str, actor: str = "console"):
        assert target_calendar_url == "https://caldav.icloud.com/family/"
        assert actor == "console"
        return {
            "calendar_name": "Family",
            "provider_label": "Apple Calendar",
            "account_label": "Family",
        }

    monkeypatch.setattr(
        AppointmentService,
        "run_write_smoke_test",
        fake_run_write_smoke_test,
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/calendar/setup/test",
        data={"target_calendar_url": "https://caldav.icloud.com/family/"},
    )

    assert response.status_code == 200
    assert "Write test passed for Family on Apple Calendar (Family)." in response.text


def test_google_setup_page_can_run_write_test(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())
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
                "calendar_name": "Primary",
                "calendar_id": "primary",
                "is_default": True,
            }
        ],
    )

    def fake_run_write_smoke_test(self, *, target_calendar_url: str, actor: str = "console"):
        assert target_calendar_url == "google:kay@example.com:primary"
        assert actor == "console"
        return {
            "calendar_name": "Primary",
            "provider_label": "Google Calendar",
            "account_label": "Kay Google",
        }

    monkeypatch.setattr(
        AppointmentService,
        "run_write_smoke_test",
        fake_run_write_smoke_test,
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/google/setup/test",
        data={"target_calendar_url": "google:kay@example.com:primary"},
    )

    assert response.status_code == 200
    assert "Write test passed for Primary on Google Calendar (Kay Google)." in response.text


def test_microsoft_setup_page_can_run_write_test(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())
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
                "calendar_name": "Calendar",
                "calendar_id": "primary",
                "is_default": True,
            }
        ],
    )

    def fake_run_write_smoke_test(self, *, target_calendar_url: str, actor: str = "console"):
        assert target_calendar_url == "microsoft:kay@example.com:primary"
        assert actor == "console"
        return {
            "calendar_name": "Calendar",
            "provider_label": "Microsoft Calendar",
            "account_label": "Kay Microsoft",
        }

    monkeypatch.setattr(
        AppointmentService,
        "run_write_smoke_test",
        fake_run_write_smoke_test,
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/microsoft/setup/test",
        data={"target_calendar_url": "microsoft:kay@example.com:primary"},
    )

    assert response.status_code == 200
    assert "Write test passed for Calendar on Microsoft Calendar (Kay Microsoft)." in response.text


def test_connections_page_can_run_write_test_and_persist_result(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
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

    def fake_run_write_smoke_test(self, *, target_calendar_url: str, actor: str = "console"):
        assert target_calendar_url == "https://caldav.icloud.com/family/"
        assert actor == "console"
        return {
            "calendar_name": "Family",
            "provider_label": "Apple Calendar",
            "provider_type": "apple",
            "account_label": "Family",
            "target_value": "https://caldav.icloud.com/family/",
        }

    monkeypatch.setattr(
        AppointmentService,
        "run_write_smoke_test",
        fake_run_write_smoke_test,
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/connections/test",
        data={"target_calendar_url": "https://caldav.icloud.com/family/"},
    )

    assert response.status_code == 200
    assert "Write test passed for Family on Apple Calendar (Family)." in response.text
    verification = service.get_calendar_write_verification(
        "https://caldav.icloud.com/family/"
    )
    assert verification is not None
    assert verification["status"] == "passed"


def test_calendar_setup_page_renders_operator_fields(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    app = create_app()
    client = TestClient(app)

    response = client.get("/calendar/setup")

    assert response.status_code == 200
    assert "Calendar setup" in response.text
    assert 'name="apple_account_label"' in response.text
    assert 'name="apple_username"' in response.text
    assert 'name="apple_app_specific_password"' in response.text
    assert 'name="apple_primary_calendar_url"' in response.text
    assert 'name="apple_primary_calendar_name"' in response.text


def test_calendar_setup_page_explains_no_connected_apple_account_truthfully(
    monkeypatch,
) -> None:
    db_path = Path(tempfile.gettempdir()) / f"calsync-ui-test-{uuid4()}.db"
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
    app = create_app()
    client = TestClient(app)

    response = client.get("/calendar/setup")

    assert response.status_code == 200
    assert "Apple calendar setup is still incomplete." in response.text
    assert "No Apple account connected yet" in response.text
    assert "Save the first Apple account above before expecting a live household calendar path inside CalSync." in response.text
    assert "No writable Apple target yet" in response.text
    assert "Save the first Apple account above before adding writable calendar targets." in response.text
    assert "<strong>Family</strong>" not in response.text
    assert "Used across the workspace and audit detail." not in response.text
    assert "Add another calendar" not in response.text


def test_calendar_setup_page_shows_recovered_legacy_apple_hints(monkeypatch) -> None:
    db_path = Path(tempfile.gettempdir()) / f"calsync-ui-test-{uuid4()}.db"
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
            "recommended_calendar_name": "Calendar",
            "recommended_calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/6824BCB8-8CEE-4733-9208-4741C62E266C/",
            "calendar_count": 2,
            "calendars": [
                {
                    "calendar_name": "Calendar",
                    "calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/6824BCB8-8CEE-4733-9208-4741C62E266C/",
                    "calendar_role": "writable_booking_target",
                    "enabled": True,
                    "is_writable_hint": True,
                },
                    {
                        "calendar_name": "Family",
                        "calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/06810ae4-a07b-49d9-9541-98123e74c806/",
                        "calendar_role": "writable_booking_target",
                        "enabled": False,
                        "is_writable_hint": True,
                    },
                ],
            }
        )
    app = create_app()
    client = TestClient(app)

    response = client.get("/calendar/setup")

    assert response.status_code == 200
    assert "Recovered from legacy backup" in response.text
    assert "Recovered hint loaded" in response.text
    assert "The recommended recovered Apple calendar is already loaded into setup. Add a fresh app-specific password to reconnect." in response.text
    assert "kaymayers9@gmail.com" in response.text
    assert "Use these recovered Apple details to finish setup with a fresh app-specific password." in response.text
    assert "Calendar" in response.text
    assert "Recommended writable hint" in response.text
    assert "Recovered writable hint" in response.text
    assert "Recommended hint already loaded below." in response.text
    assert "The recommended recovered Apple account and calendar hint are already loaded below." in response.text
    assert 'value="https://p52-caldav.icloud.com:443/112135872/calendars/6824BCB8-8CEE-4733-9208-4741C62E266C/"' in response.text
    assert "Load this calendar into setup form" in response.text


def test_calendar_setup_page_can_prefill_form_from_recovered_legacy_hint(monkeypatch) -> None:
    db_path = Path(tempfile.gettempdir()) / f"calsync-ui-test-{uuid4()}.db"
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
            "recommended_calendar_name": "Calendar",
            "recommended_calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/6824BCB8-8CEE-4733-9208-4741C62E266C/",
            "calendar_count": 2,
            "calendars": [
                {
                    "calendar_name": "Calendar",
                    "calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/6824BCB8-8CEE-4733-9208-4741C62E266C/",
                    "calendar_role": "personal_reference",
                    "enabled": True,
                    "is_writable_hint": True,
                },
                {
                    "calendar_name": "Family",
                    "calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/e53367e6-75d4-42a0-b7bf-eaeb12f233f8/",
                    "calendar_role": "writable_booking_target",
                    "enabled": False,
                    "is_writable_hint": True,
                },
            ],
        }
    )
    app = create_app()
    client = TestClient(app)

    response = client.get(
        "/calendar/setup",
        params={
            "recovered_calendar_url": "https://p52-caldav.icloud.com:443/112135872/calendars/e53367e6-75d4-42a0-b7bf-eaeb12f233f8/"
        },
    )

    assert response.status_code == 200
    assert "Recovered Apple details loaded into the setup form." in response.text
    assert 'value="kaymayers9@gmail.com"' in response.text
    assert (
        'value="https://p52-caldav.icloud.com:443/112135872/calendars/e53367e6-75d4-42a0-b7bf-eaeb12f233f8/"'
        in response.text
    )
    assert 'value="Family"' in response.text
    assert "Add a fresh app-specific password, then save to reconnect this calendar path for real." in response.text


def test_calendar_setup_page_saves_apple_settings(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/calendar/setup",
        data={
            "apple_account_label": "Household",
            "apple_username": "household@example.com",
            "apple_app_specific_password": "apple-secret-123",
            "apple_primary_calendar_url": "https://caldav.icloud.com/household/",
            "apple_primary_calendar_name": "Household",
        },
    )

    assert response.status_code == 200
    assert "Apple calendar settings saved securely." in response.text

    service = OperatorSettingsService(settings=get_settings())
    assert service.get_apple_calendar_settings() == {
        "account_label": "Household",
        "username": "household@example.com",
        "app_specific_password": "apple-secret-123",
        "primary_calendar_url": "https://caldav.icloud.com/household/",
        "primary_calendar_name": "Household",
    }


def test_calendar_setup_page_shows_validate_action(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    app = create_app()
    client = TestClient(app)

    response = client.get("/calendar/setup")

    assert response.status_code == 200
    assert "Validate Apple connection" in response.text
    assert 'formaction="/calendar/setup/validate"' in response.text


def test_calendar_setup_page_can_validate_pending_apple_settings_without_saving(
    monkeypatch,
) -> None:
    _configure_test_env(monkeypatch)
    validated: dict[str, str] = {}

    def fake_validate(self) -> None:
        validated["account_label"] = self.config.account_label
        validated["username"] = self.config.apple_username
        validated["calendar_url"] = self.config.primary_calendar_url
        validated["calendar_name"] = self.config.primary_calendar_name
        validated["password"] = self.config.app_specific_password

    monkeypatch.setattr(
        "calsync.services.apple_caldav.AppleCalDAVClient.validate_calendar_access",
        fake_validate,
        raising=False,
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/calendar/setup/validate",
        data={
            "apple_account_label": "Household",
            "apple_username": "household@example.com",
            "apple_app_specific_password": "fresh-secret",
            "apple_primary_calendar_url": "https://caldav.icloud.com/household/",
            "apple_primary_calendar_name": "Household",
        },
    )

    assert response.status_code == 200
    assert "Apple calendar credentials validated successfully. Nothing has been saved yet." in response.text
    assert validated == {
        "account_label": "Household",
        "username": "household@example.com",
        "calendar_url": "https://caldav.icloud.com/household/",
        "calendar_name": "Household",
        "password": "fresh-secret",
    }

    service = OperatorSettingsService(settings=get_settings())
    assert service.describe_apple_calendar_settings()["source"] == "missing"
    assert service.get_apple_accounts() == []


def test_calendar_setup_page_validation_failure_does_not_save_settings(monkeypatch) -> None:
    _configure_test_env(monkeypatch)

    def fake_validate(self) -> None:
        raise AppleCalDAVError("Apple/iCloud authentication failed.")

    monkeypatch.setattr(
        "calsync.services.apple_caldav.AppleCalDAVClient.validate_calendar_access",
        fake_validate,
        raising=False,
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/calendar/setup/validate",
        data={
            "apple_account_label": "Household",
            "apple_username": "household@example.com",
            "apple_app_specific_password": "wrong-secret",
            "apple_primary_calendar_url": "https://caldav.icloud.com/household/",
            "apple_primary_calendar_name": "Household",
        },
    )

    assert response.status_code == 400
    assert "Apple/iCloud authentication failed." in response.text

    service = OperatorSettingsService(settings=get_settings())
    assert service.describe_apple_calendar_settings()["source"] == "missing"
    assert service.get_apple_accounts() == []


def test_calendar_setup_page_can_add_another_apple_account(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    app = create_app()
    client = TestClient(app)

    client.post(
        "/calendar/setup",
        data={
            "apple_account_label": "Family",
            "apple_username": "family@example.com",
            "apple_app_specific_password": "family-secret",
            "apple_primary_calendar_url": "https://caldav.icloud.com/family/",
            "apple_primary_calendar_name": "Family",
        },
    )
    response = client.post(
        "/calendar/setup",
        data={
            "apple_account_label": "Work",
            "apple_username": "work@example.com",
            "apple_app_specific_password": "work-secret",
            "apple_primary_calendar_url": "https://caldav.icloud.com/work/",
            "apple_primary_calendar_name": "Work",
        },
    )

    assert response.status_code == 200
    assert "Connected Apple accounts" in response.text
    assert "family@example.com" in response.text
    assert "work@example.com" in response.text

    service = OperatorSettingsService(settings=get_settings())
    accounts_by_username = {
        account["username"]: account for account in service.get_apple_accounts()
    }
    assert accounts_by_username == {
        "family@example.com": {
            "account_label": "Family",
            "username": "family@example.com",
            "app_specific_password": "family-secret",
            "calendars": [
                {
                    "calendar_name": "Family",
                    "calendar_url": "https://caldav.icloud.com/family/",
                    "is_default": True,
                }
            ],
        },
        "work@example.com": {
            "account_label": "Work",
            "username": "work@example.com",
            "app_specific_password": "work-secret",
            "calendars": [
                {
                    "calendar_name": "Work",
                    "calendar_url": "https://caldav.icloud.com/work/",
                    "is_default": True,
                }
            ],
        },
    }


def test_calendar_setup_page_can_add_another_calendar_target(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    app = create_app()
    client = TestClient(app)

    client.post(
        "/calendar/setup",
        data={
            "apple_account_label": "Household",
            "apple_username": "household@example.com",
            "apple_app_specific_password": "apple-secret-123",
            "apple_primary_calendar_url": "https://caldav.icloud.com/household/",
            "apple_primary_calendar_name": "Household",
        },
    )
    response = client.post(
        "/calendar/setup/calendars",
        data={
            "account_username": "household@example.com",
            "calendar_name": "School",
            "calendar_url": "https://caldav.icloud.com/school/",
            "is_default": "false",
        },
    )

    assert response.status_code == 200
    assert "Apple calendar target added." in response.text
    assert "School" in response.text

    service = OperatorSettingsService(settings=get_settings())
    assert service.get_apple_calendar_catalog() == [
        {
            "calendar_name": "Household",
            "calendar_url": "https://caldav.icloud.com/household/",
            "is_default": True,
        },
        {
            "calendar_name": "School",
            "calendar_url": "https://caldav.icloud.com/school/",
            "is_default": False,
        },
    ]


def test_calendar_setup_add_calendar_preserves_existing_runtime_target_when_catalog_is_empty(
    monkeypatch,
) -> None:
    _configure_test_env(monkeypatch)
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/calendar/setup/calendars",
        data={
            "calendar_name": "School",
            "calendar_url": "https://caldav.icloud.com/school/",
            "is_default": "false",
        },
    )

    assert response.status_code == 200
    service = OperatorSettingsService(settings=get_settings())
    assert service.get_apple_calendar_catalog() == [
        {
            "calendar_name": "Family",
            "calendar_url": "https://caldav.icloud.com/calendar/",
            "is_default": True,
        },
        {
            "calendar_name": "School",
            "calendar_url": "https://caldav.icloud.com/school/",
            "is_default": False,
        },
    ]


def test_calendar_setup_can_add_calendar_to_specific_apple_account(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    app = create_app()
    client = TestClient(app)

    client.post(
        "/calendar/setup",
        data={
            "apple_account_label": "Family",
            "apple_username": "family@example.com",
            "apple_app_specific_password": "family-secret",
            "apple_primary_calendar_url": "https://caldav.icloud.com/family/",
            "apple_primary_calendar_name": "Family",
        },
    )
    client.post(
        "/calendar/setup",
        data={
            "apple_account_label": "Work",
            "apple_username": "work@example.com",
            "apple_app_specific_password": "work-secret",
            "apple_primary_calendar_url": "https://caldav.icloud.com/work/",
            "apple_primary_calendar_name": "Work",
        },
    )
    response = client.post(
        "/calendar/setup/calendars",
        data={
            "account_username": "work@example.com",
            "calendar_name": "Travel",
            "calendar_url": "https://caldav.icloud.com/travel/",
            "is_default": "false",
        },
    )

    assert response.status_code == 200
    assert "Apple calendar target added." in response.text
    assert "Travel" in response.text

    service = OperatorSettingsService(settings=get_settings())
    work_account = next(
        account
        for account in service.get_apple_accounts()
        if account["username"] == "work@example.com"
    )
    assert work_account["calendars"] == [
        {
            "calendar_name": "Work",
            "calendar_url": "https://caldav.icloud.com/work/",
            "is_default": True,
        },
        {
            "calendar_name": "Travel",
            "calendar_url": "https://caldav.icloud.com/travel/",
            "is_default": False,
        },
    ]


def test_console_create_form_surfaces_multiple_saved_calendar_targets(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())
    service.set_apple_calendar_catalog(
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

    response = client.get("/")

    assert response.status_code == 200
    assert 'name="target_calendar_url"' in response.text
    assert "Family" in response.text
    assert "School" in response.text


def test_console_edit_flow_can_move_appointment_to_another_saved_calendar(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self, calendar_url=None: FakeAppleClient(),
    )
    service = OperatorSettingsService(settings=get_settings())
    service.set_apple_calendar_catalog(
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

    response = client.post(
        f"/appointments/{appointment_id}/edit",
        data={
            "title": "Reading assessment",
            "date_value": "2026-06-07",
            "start_time": "09:00",
            "end_time": "10:00",
            "timezone": "America/Anchorage",
            "location": "",
            "notes": "",
            "attendees_text": "",
            "target_calendar_url": "https://caldav.icloud.com/school/",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Appointment updated on the connected calendar." in response.text
    assert "School" in response.text


def test_alexa_simulator_page_renders_voice_test_surface(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    service = OperatorSettingsService(settings=get_settings())
    service.set_apple_calendar_catalog(
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
    service.set_google_oauth_settings(
        client_id="google-client-id",
        client_secret="google-client-secret",
    )
    service.upsert_google_account(
        account_label="Work Google",
        account_email="work@example.com",
        refresh_token="work-google-refresh",
        calendars=[
            {
                "calendar_name": "Work",
                "calendar_id": "work",
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
        refresh_token="microsoft-refresh",
        calendars=[
            {
                "calendar_name": "Calendar",
                "calendar_id": "primary",
                "is_default": True,
            }
        ],
    )
    app = create_app()
    client = TestClient(app)

    response = client.get("/alexa/simulator")

    assert response.status_code == 200
    assert "Alexa simulator" in response.text
    assert "Simulator readiness" in response.text
    assert "CreateAppointmentIntent" in response.text
    assert "Target calendar" in response.text
    assert "School" in response.text
    assert "Work · Google Calendar · Work Google" in response.text
    assert "Calendar · Microsoft Calendar · Kay Microsoft" in response.text
    assert "Run simulation" in response.text


def test_alexa_simulator_page_explains_missing_calendar_readiness(monkeypatch) -> None:
    db_path = Path(tempfile.gettempdir()) / f"calsync-ui-test-{uuid4()}.db"
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
    app = create_app()
    client = TestClient(app)

    response = client.get("/alexa/simulator")

    assert response.status_code == 200
    assert "Simulator readiness" in response.text
    assert "Calendar setup still blocks meaningful scheduling tests" in response.text
    assert "No writable calendar is connected yet." in response.text
    assert "LaunchRequest and copy checks" in response.text
    assert "Named calendar targeting will appear here after Apple, Google, or Microsoft setup is connected." in response.text
    assert "Reschedule moves can target a named calendar after a writable calendar path is connected." in response.text


def test_alexa_simulator_page_shows_simulated_response(monkeypatch) -> None:
    _configure_test_env(monkeypatch)

    class FakeAlexaSimulatorService:
        def simulate(self, *, request_type: str, intent_name: str | None, slots: dict[str, str]):
            assert request_type == "IntentRequest"
            assert intent_name == "CreateAppointmentIntent"
            assert slots["title"] == "Dentist"
            assert slots["calendar_name"] == "School"
            return {
                "ok": True,
                "speech": "I added Dentist to the School calendar for Monday, June 1, 2026 at 10:00 AM.",
                "card_type": "Simple",
                "should_end_session": True,
                "raw_response": {
                    "version": "1.0",
                    "response": {
                        "outputSpeech": {
                            "type": "PlainText",
                            "text": "I added Dentist to the School calendar for Monday, June 1, 2026 at 10:00 AM.",
                        }
                    },
                },
            }

    monkeypatch.setattr(
        "calsync.web.routes.console.AlexaSimulatorService",
        FakeAlexaSimulatorService,
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/alexa/simulator",
        data={
            "request_type": "IntentRequest",
            "intent_name": "CreateAppointmentIntent",
            "title": "Dentist",
            "date": "2026-06-01",
            "start_time": "10:00",
            "end_time": "11:00",
            "calendar_name": "School",
        },
    )

    assert response.status_code == 200
    assert "I added Dentist to the School calendar for Monday, June 1, 2026 at 10:00 AM." in response.text
    assert '"outputSpeech"' in response.text


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


def test_console_root_renders_distinct_planner_boards_for_day_week_and_month(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: FakeAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    today = datetime.now(UTC).astimezone(ZoneInfo("America/Anchorage")).date()
    schedule = (
        ("Today visit", today),
        ("Week check-in", today + timedelta(days=2)),
        ("Month planning", today + timedelta(days=12)),
    )
    for title, appointment_day in schedule:
        create_response = client.post(
            "/api/appointments",
            json={
                "title": title,
                "date": appointment_day.isoformat(),
                "start_time": "09:00",
                "end_time": "10:00",
                "timezone": "America/Anchorage",
            },
        )
        assert create_response.status_code == 201

    day_response = client.get("/?view=day")
    assert day_response.status_code == 200
    assert "Day board" in day_response.text
    assert "schedule-board schedule-board--day" in day_response.text
    assert "Today visit" in day_response.text
    assert "Week check-in" not in day_response.text

    week_response = client.get("/?view=week")
    assert week_response.status_code == 200
    assert "Week board" in week_response.text
    assert "schedule-board schedule-board--week" in week_response.text
    assert "Today visit" in week_response.text
    assert "Week check-in" in week_response.text
    assert "Month planning" not in week_response.text

    month_response = client.get("/?view=month")
    assert month_response.status_code == 200
    assert "Month board" in month_response.text
    assert "schedule-board schedule-board--month" in month_response.text
    assert "Today visit" in month_response.text
    assert "Week check-in" in month_response.text
    assert "Month planning" in month_response.text


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


def test_console_root_shows_availability_results(monkeypatch) -> None:
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
            },
        )
        assert create_response.status_code == 201

    response = client.get(
        "/?view=week&availability_date_from=2026-06-01&availability_date_to=2026-06-01&availability_duration_minutes=60"
    )

    assert response.status_code == 200
    assert "Open windows" in response.text
    assert "Monday, Jun 1" in response.text
    assert "8:00 AM - 9:00 AM" in response.text
    assert "10:00 AM - 11:00 AM" in response.text


def test_console_root_blocks_availability_search_when_no_calendar_is_connected(
    monkeypatch,
) -> None:
    db_path = Path(tempfile.gettempdir()) / f"calsync-ui-test-{uuid4()}.db"
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
    app = create_app()
    client = TestClient(app)

    response = client.get(
        "/?view=week&availability_date_from=2026-06-01&availability_date_to=2026-06-07&availability_duration_minutes=60"
    )

    assert response.status_code == 200
    assert "Availability setup still blocked" in response.text
    assert "Connect a writable calendar before searching for open time from the schedule workspace." in response.text
    assert '<button type="submit" disabled>Find open time</button>' in response.text
    assert "No writable calendars connected yet" in response.text
    assert "No open windows found" not in response.text


def test_booking_page_can_create_appointment_from_selected_slot(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: FakeAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/book",
        data={
            "requester_name": "Morgan",
            "requester_contact": "morgan@example.com",
            "title": "School intake call",
            "attendees_text": "Kayra",
            "location": "Phone",
            "notes": "Public booking flow",
            "slot_value": "2026-06-01|10:00|11:00|America/Anchorage",
        },
    )

    assert response.status_code == 200
    assert "Booking confirmed" in response.text
    assert "School intake call" in response.text
    assert "Kayra" in response.text
    assert "Morgan" in response.text
    assert "morgan@example.com" in response.text

    api_response = client.get("/api/appointments?date_from=2026-06-01&date_to=2026-06-01")
    items = api_response.json()["items"]
    created = next(item for item in items if item["title"] == "School intake call")
    assert "Requested by: Morgan" in (created["notes"] or "")
    assert "Contact: morgan@example.com" in (created["notes"] or "")


def test_booking_page_uses_custom_success_message(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    operator_settings = OperatorSettingsService(settings=get_settings())
    operator_settings.set_public_booking_settings(
        page_title="Book time with Kayra",
        page_description="Choose a calm household scheduling slot.",
        duration_minutes=30,
        search_window_days=21,
        success_message="You're booked.",
        target_calendar_url="https://caldav.icloud.com/calendar/",
    )
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: FakeAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/book",
        data={
            "requester_name": "Morgan",
            "requester_contact": "morgan@example.com",
            "title": "Therapy intake",
            "attendees_text": "Kayra",
            "location": "Phone",
            "notes": "Configured success message",
            "slot_value": "2026-06-01|10:00|10:30|America/Anchorage",
            "availability_date_from": "2026-06-01",
            "availability_date_to": "2026-06-21",
            "availability_duration_minutes": "30",
        },
    )

    assert response.status_code == 200
    assert "You&#39;re booked." in response.text


def test_alexa_simulator_supports_find_availability_intent(monkeypatch) -> None:
    _configure_test_env(monkeypatch)

    class FakeAlexaSimulatorService:
        def simulate(self, *, request_type: str, intent_name: str | None, slots: dict[str, str]):
            assert request_type == "IntentRequest"
            assert intent_name == "FindAvailabilityIntent"
            assert slots["date"] == "2026-06-01"
            assert slots["duration_minutes"] == "60"
            return {
                "ok": True,
                "speech": "I found openings on Monday, June 1, 2026 at 10:00 AM and 11:00 AM.",
                "card_type": "Simple",
                "should_end_session": True,
                "raw_response": {
                    "version": "1.0",
                    "response": {
                        "outputSpeech": {
                            "type": "PlainText",
                            "text": "I found openings on Monday, June 1, 2026 at 10:00 AM and 11:00 AM.",
                        }
                    },
                },
            }

    monkeypatch.setattr(
        "calsync.web.routes.console.AlexaSimulatorService",
        FakeAlexaSimulatorService,
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/alexa/simulator",
        data={
            "request_type": "IntentRequest",
            "intent_name": "FindAvailabilityIntent",
            "date": "2026-06-01",
            "duration_minutes": "60",
        },
    )

    assert response.status_code == 200
    assert "I found openings on Monday, June 1, 2026 at 10:00 AM and 11:00 AM." in response.text
    assert '"outputSpeech"' in response.text
