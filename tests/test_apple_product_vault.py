import tempfile
from pathlib import Path
from uuid import uuid4

from calsync.config import Settings
from calsync.db import _get_engine_for_url, _get_session_factory_for_url
from calsync.models import Base
from calsync.services.appointments import AppointmentService
from calsync.services.channel_tokens import ChannelTokenManager
from calsync.services.operator_settings import OperatorSettingsService
from calsync.services.readiness import ReadinessService


def _settings() -> Settings:
    db_path = Path(tempfile.gettempdir()) / f"calsync-apple-vault-{uuid4()}.db"
    runtime_path = (
        Path(tempfile.gettempdir()) / f"calsync-channel-tokens-{uuid4()}.json"
    )
    settings = Settings.model_construct(
        app_host="0.0.0.0",
        app_port=3080,
        database_url=f"sqlite+pysqlite:///{db_path.as_posix()}",
        encryption_key="unit-test-encryption-key",
        default_timezone="America/Anchorage",
        apple_account_label="",
        apple_username=None,
        apple_app_specific_password=None,
        apple_primary_calendar_url=None,
        apple_primary_calendar_name="",
        cloudflare_account_id=None,
        cloudflare_api_token=None,
        cloudflare_token_kv_namespace_id=None,
        channel_token_runtime_path=str(runtime_path),
        edge_base_url="",
        cloudflare_edge_worker_name="edge-calsync",
    )
    _get_engine_for_url.cache_clear()
    _get_session_factory_for_url.cache_clear()
    Base.metadata.create_all(_get_engine_for_url(settings.database_url))
    return settings


def test_appointment_service_uses_product_vault_apple_settings(monkeypatch) -> None:
    settings = _settings()
    operator_settings = OperatorSettingsService(settings=settings)
    operator_settings.set_apple_calendar_settings(
        account_label="Family",
        username="family@example.com",
        app_specific_password="apple-secret-123",
        primary_calendar_url="https://caldav.icloud.com/family/",
        primary_calendar_name="Family",
    )

    class CapturingAppleClient:
        def __init__(self, config) -> None:
            self.config = config

    monkeypatch.setattr(
        "calsync.services.appointments.AppleCalDAVClient",
        CapturingAppleClient,
    )

    service = AppointmentService(settings=settings)
    client = service._build_apple_client()

    assert client.config.account_label == "Family"
    assert client.config.apple_username == "family@example.com"
    assert client.config.app_specific_password == "apple-secret-123"
    assert client.config.primary_calendar_url == "https://caldav.icloud.com/family/"
    assert client.config.primary_calendar_name == "Family"


def test_readiness_service_uses_product_vault_apple_settings() -> None:
    settings = _settings()
    operator_settings = OperatorSettingsService(settings=settings)
    operator_settings.set_apple_calendar_settings(
        account_label="Family",
        username="family@example.com",
        app_specific_password="apple-secret-123",
        primary_calendar_url="https://caldav.icloud.com/family/",
        primary_calendar_name="Family",
    )

    readiness = ReadinessService(settings=settings).build()

    assert readiness["origin"]["apple_ready"] is True
    assert readiness["origin"]["account_label"] == "Family"
    assert readiness["origin"]["calendar_name"] == "Family"


def test_readiness_service_mentions_saved_desired_alexa_drift() -> None:
    settings = _settings()
    operator_settings = OperatorSettingsService(settings=settings)
    ChannelTokenManager(runtime_path=settings.channel_token_runtime_path).bootstrap_channel(
        "chatgpt"
    )
    operator_settings.set_apple_calendar_settings(
        account_label="Family",
        username="family@example.com",
        app_specific_password="apple-secret-123",
        primary_calendar_url="https://caldav.icloud.com/family/",
        primary_calendar_name="Family",
    )
    operator_settings.set_alexa_account_linking_settings(link_code="Family123")
    operator_settings.set_cloudflare_worker_credentials(
        account_id="acct-123",
        api_token="token-123",
    )
    operator_settings.set_desired_alexa_settings(
        enable_alexa=True,
        allowed_skill_ids=["amzn1.ask.skill.real"],
    )

    readiness = ReadinessService(settings=settings).build()

    assert readiness["desired_alexa"]["saved"] is True
    assert readiness["desired_alexa"]["enable_alexa"] is True
    assert readiness["desired_alexa"]["allowed_skill_ids"] == [
        "amzn1.ask.skill.real"
    ]
    assert "Desired Alexa settings are saved" in readiness["next_action"]


def test_readiness_service_points_to_account_linking_and_cloudflare_before_edge_enablement() -> None:
    settings = _settings()
    operator_settings = OperatorSettingsService(settings=settings)
    ChannelTokenManager(runtime_path=settings.channel_token_runtime_path).bootstrap_channel(
        "chatgpt"
    )
    operator_settings.set_apple_calendar_settings(
        account_label="Family",
        username="family@example.com",
        app_specific_password="apple-secret-123",
        primary_calendar_url="https://caldav.icloud.com/family/",
        primary_calendar_name="Family",
    )

    readiness = ReadinessService(settings=settings).build()

    assert readiness["origin"]["any_calendar_ready"] is True
    assert (
        readiness["next_action"]
        == "Save a household link code and Cloudflare Worker access so CalSync can finish Alexa account linking and live edge turn-on."
    )


def test_readiness_service_points_to_saved_desired_plan_before_cloudflare_once_account_linking_is_ready() -> None:
    settings = _settings()
    operator_settings = OperatorSettingsService(settings=settings)
    ChannelTokenManager(runtime_path=settings.channel_token_runtime_path).bootstrap_channel(
        "chatgpt"
    )
    operator_settings.set_apple_calendar_settings(
        account_label="Family",
        username="family@example.com",
        app_specific_password="apple-secret-123",
        primary_calendar_url="https://caldav.icloud.com/family/",
        primary_calendar_name="Family",
    )
    operator_settings.set_alexa_account_linking_settings(link_code="Family123")

    readiness = ReadinessService(settings=settings).build()

    assert readiness["origin"]["any_calendar_ready"] is True
    assert readiness["desired_alexa"]["saved"] is False
    assert (
        readiness["next_action"]
        == "Save the Alexa plan and your real skill ID, then save Cloudflare Worker access so CalSync can turn on the live Alexa route and skill allowlist from the product."
    )


def test_readiness_service_keeps_skill_id_guidance_after_blank_default_alexa_save() -> None:
    settings = _settings()
    operator_settings = OperatorSettingsService(settings=settings)
    ChannelTokenManager(runtime_path=settings.channel_token_runtime_path).bootstrap_channel(
        "chatgpt"
    )
    operator_settings.set_apple_calendar_settings(
        account_label="Family",
        username="family@example.com",
        app_specific_password="apple-secret-123",
        primary_calendar_url="https://caldav.icloud.com/family/",
        primary_calendar_name="Family",
    )
    operator_settings.set_alexa_account_linking_settings(link_code="Family123")
    operator_settings.set_desired_alexa_settings(
        enable_alexa=False,
        allowed_skill_ids=[],
    )

    readiness = ReadinessService(settings=settings).build()

    assert readiness["origin"]["any_calendar_ready"] is True
    assert readiness["desired_alexa"]["saved"] is False
    assert (
        readiness["next_action"]
        == "Save the Alexa plan and your real skill ID, then save Cloudflare Worker access so CalSync can turn on the live Alexa route and skill allowlist from the product."
    )


def test_readiness_service_keeps_skill_id_guidance_when_alexa_enabled_without_skill_id() -> None:
    settings = _settings()
    operator_settings = OperatorSettingsService(settings=settings)
    ChannelTokenManager(runtime_path=settings.channel_token_runtime_path).bootstrap_channel(
        "chatgpt"
    )
    operator_settings.set_apple_calendar_settings(
        account_label="Family",
        username="family@example.com",
        app_specific_password="apple-secret-123",
        primary_calendar_url="https://caldav.icloud.com/family/",
        primary_calendar_name="Family",
    )
    operator_settings.set_alexa_account_linking_settings(link_code="Family123")
    operator_settings.set_desired_alexa_settings(
        enable_alexa=True,
        allowed_skill_ids=[],
    )

    readiness = ReadinessService(settings=settings).build()

    assert readiness["origin"]["any_calendar_ready"] is True
    assert readiness["desired_alexa"]["saved"] is False
    assert (
        readiness["next_action"]
        == "Save the Alexa plan and your real skill ID, then save Cloudflare Worker access so CalSync can turn on the live Alexa route and skill allowlist from the product."
    )


def test_readiness_service_points_to_restore_when_non_provider_settings_exist() -> None:
    settings = _settings()
    operator_settings = OperatorSettingsService(settings=settings)
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

    readiness = ReadinessService(settings=settings).build()

    assert readiness["origin"]["any_calendar_ready"] is False
    assert (
        readiness["next_action"]
        == "Restore an encrypted backup from Connections or add an Apple calendar so CalSync can read and write a real connected calendar."
    )


def test_readiness_service_points_to_apple_reconnect_when_legacy_hints_exist() -> None:
    settings = _settings()
    operator_settings = OperatorSettingsService(settings=settings)
    operator_settings.set_legacy_apple_recovery_hints(
        {
            "source_filename": "calsync-db-backup.zip",
            "account_label": "kaymayers9@gmail.com",
            "account_username": "kaymayers9@gmail.com",
            "principal_url": "https://caldav.icloud.com/112135872/principal/",
            "calendar_home_url": "https://p52-caldav.icloud.com:443/112135872/calendars/",
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

    readiness = ReadinessService(settings=settings).build()

    assert readiness["origin"]["apple_ready"] is False
    assert readiness["origin"]["recovery_mode"] is True
    assert (
        readiness["next_action"]
        == "Open Apple setup, confirm the loaded recovered Apple calendar, and save a fresh app-specific password so CalSync can reconnect the real household calendar."
    )


def test_readiness_service_mentions_reusable_legacy_apple_secret() -> None:
    settings = _settings()
    operator_settings = OperatorSettingsService(settings=settings)
    recovered_secret = operator_settings._fernet.encrypt(b"apple-secret-123").decode(
        "utf-8"
    )
    operator_settings.set_legacy_apple_recovery_hints(
        {
            "source_filename": "calsync-db-backup.zip",
            "account_label": "kaymayers9@gmail.com",
            "account_username": "kaymayers9@gmail.com",
            "principal_url": "https://caldav.icloud.com/112135872/principal/",
            "calendar_home_url": "https://p52-caldav.icloud.com:443/112135872/calendars/",
            "credential_secret_encrypted": recovered_secret,
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

    readiness = ReadinessService(settings=settings).build()

    assert (
        readiness["next_action"]
        == "Open Apple setup and save the loaded recovered Apple calendar. The preserved Apple app-specific password is reusable with the current CalSync encryption key."
    )


def test_readiness_service_mentions_original_key_when_legacy_secret_mismatches() -> None:
    settings = _settings()
    operator_settings = OperatorSettingsService(settings=settings)
    other_settings = settings.model_copy(update={"encryption_key": "different-test-key"})
    encrypted_with_other_key = OperatorSettingsService(
        settings=other_settings
    )._fernet.encrypt(b"apple-secret-123").decode("utf-8")
    operator_settings.set_legacy_apple_recovery_hints(
        {
            "source_filename": "calsync-db-backup.zip",
            "account_label": "kaymayers9@gmail.com",
            "account_username": "kaymayers9@gmail.com",
            "principal_url": "https://caldav.icloud.com/112135872/principal/",
            "calendar_home_url": "https://p52-caldav.icloud.com:443/112135872/calendars/",
            "credential_secret_encrypted": encrypted_with_other_key,
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

    readiness = ReadinessService(settings=settings).build()

    assert (
        readiness["next_action"]
        == "Open Apple setup, then either enter the original CalSync encryption key there or save a fresh app-specific password so CalSync can reconnect the real household calendar."
    )


def test_appointment_service_uses_matching_apple_account_for_selected_calendar(
    monkeypatch,
) -> None:
    settings = _settings()
    operator_settings = OperatorSettingsService(settings=settings)
    operator_settings.upsert_apple_account(
        account_label="Family",
        username="family@example.com",
        app_specific_password="family-secret",
        calendars=[
            {
                "calendar_name": "Family",
                "calendar_url": "https://caldav.icloud.com/family/",
                "is_default": True,
            }
        ],
    )
    operator_settings.upsert_apple_account(
        account_label="Work",
        username="work@example.com",
        app_specific_password="work-secret",
        calendars=[
            {
                "calendar_name": "Work",
                "calendar_url": "https://caldav.icloud.com/work/",
                "is_default": True,
            }
        ],
    )

    class CapturingAppleClient:
        def __init__(self, config) -> None:
            self.config = config

    monkeypatch.setattr(
        "calsync.services.appointments.AppleCalDAVClient",
        CapturingAppleClient,
    )

    service = AppointmentService(settings=settings)
    client = service._build_apple_client(calendar_url="https://caldav.icloud.com/work/")

    assert client.config.account_label == "Work"
    assert client.config.apple_username == "work@example.com"
    assert client.config.app_specific_password == "work-secret"
    assert client.config.primary_calendar_url == "https://caldav.icloud.com/work/"
    assert client.config.primary_calendar_name == "Work"
