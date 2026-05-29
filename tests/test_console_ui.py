import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

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
    assert "Apple setup" in response.text
    assert "Google setup" in response.text
    assert "Find open time" in response.text


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
    assert "Reconnect Google account" in response.text
    assert "Refresh Google calendars" in response.text
    assert "Disconnect Google account" in response.text


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


def test_alexa_setup_page_updates_edge_settings(monkeypatch) -> None:
    _configure_test_env(monkeypatch)

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
    assert "Edge Worker settings updated." in response.text


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
    app = create_app()
    client = TestClient(app)

    response = client.get("/alexa/simulator")

    assert response.status_code == 200
    assert "Alexa simulator" in response.text
    assert "CreateAppointmentIntent" in response.text
    assert "Target calendar" in response.text
    assert "School" in response.text
    assert "Run simulation" in response.text


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
