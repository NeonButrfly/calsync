import json
import tempfile
from pathlib import Path
from uuid import uuid4

from calsync.config import Settings
from calsync.db import _get_engine_for_url, _get_session_factory_for_url
from calsync.models import Base
from calsync.models.operator_settings import OperatorSetting
from calsync.services.operator_settings import OperatorSettingsService


def _settings() -> Settings:
    db_path = Path(tempfile.gettempdir()) / f"calsync-operator-settings-{uuid4()}.db"
    settings = Settings.model_construct(
        app_host="0.0.0.0",
        app_port=3080,
        database_url=f"sqlite+pysqlite:///{db_path.as_posix()}",
        default_timezone="America/Anchorage",
        apple_account_label="Family",
        apple_username="family@example.com",
        apple_app_specific_password="secret",
        apple_primary_calendar_url="https://caldav.icloud.com/calendar/",
        apple_primary_calendar_name="Family",
        channel_token_runtime_path=".runtime/channel-tokens.json",
        edge_base_url="https://edge-calsync.neonbutterfly.net",
        cloudflare_edge_worker_name="edge-calsync",
        encryption_key="unit-test-encryption-key",
    )
    _get_engine_for_url.cache_clear()
    _get_session_factory_for_url.cache_clear()
    Base.metadata.create_all(_get_engine_for_url(settings.database_url))
    return settings


def test_operator_settings_encrypts_values_at_rest() -> None:
    settings = _settings()
    service = OperatorSettingsService(settings=settings)

    service.set_cloudflare_worker_credentials(
        account_id="acct-123",
        api_token="api-token-123",
    )

    credential_state = service.describe_cloudflare_worker_credentials()
    assert credential_state["account_id"] == "acct-123"
    assert credential_state["api_token_saved"] is True
    assert credential_state["source"] == "product_vault"

    session_factory = _get_session_factory_for_url(settings.database_url)
    with session_factory() as session:
        stored_rows = {
            row.key: row.value_encrypted
            for row in session.query(OperatorSetting).all()
        }

    assert stored_rows["cloudflare_account_id"] != "acct-123"
    assert stored_rows["cloudflare_api_token"] != "api-token-123"


def test_operator_settings_keeps_existing_token_when_blank_update() -> None:
    settings = _settings()
    service = OperatorSettingsService(settings=settings)

    service.set_cloudflare_worker_credentials(
        account_id="acct-123",
        api_token="api-token-123",
    )
    service.set_cloudflare_worker_credentials(
        account_id="acct-456",
        api_token="",
        preserve_existing_token=True,
    )

    credential_state = service.describe_cloudflare_worker_credentials()
    assert credential_state["account_id"] == "acct-456"
    assert credential_state["api_token_saved"] is True
    assert service.get_cloudflare_worker_credentials() == {
        "account_id": "acct-456",
        "api_token": "api-token-123",
    }


def test_operator_settings_can_store_desired_alexa_settings() -> None:
    settings = _settings()
    service = OperatorSettingsService(settings=settings)

    service.set_desired_alexa_settings(
        enable_alexa=True,
        allowed_skill_ids=["amzn1.ask.skill.one", "amzn1.ask.skill.two"],
    )

    assert service.get_desired_alexa_settings() == {
        "enable_alexa": True,
        "allowed_skill_ids": ["amzn1.ask.skill.one", "amzn1.ask.skill.two"],
    }
    described = service.describe_desired_alexa_settings()
    assert described["enable_alexa"] is True
    assert described["allowed_skill_ids"] == [
        "amzn1.ask.skill.one",
        "amzn1.ask.skill.two",
    ]
    assert described["saved"] is True
    assert described["source"] == "product_vault"


def test_operator_settings_can_store_alexa_account_linking_settings() -> None:
    settings = _settings()
    service = OperatorSettingsService(settings=settings)

    service.set_alexa_account_linking_settings(
        link_code="Household-123",
    )

    stored = service.get_alexa_account_linking_settings()
    assert stored["client_id"] == "calsync-alexa-household"
    assert stored["link_code"] == "HOUSEHOLD123"
    assert isinstance(stored["access_token"], str)
    assert len(stored["access_token"]) >= 24

    described = service.describe_alexa_account_linking_settings()
    assert described["configured"] is True
    assert described["client_id"] == "calsync-alexa-household"
    assert described["link_code_saved"] is True
    assert described["access_token_ready"] is True
    assert described["authorization_url"].endswith(
        "/alexa/account-linking/authorize"
    )


def test_operator_settings_can_export_and_restore_encrypted_backup() -> None:
    settings = _settings()
    service = OperatorSettingsService(settings=settings)

    service.set_apple_calendar_settings(
        account_label="Family",
        username="family@example.com",
        app_specific_password="apple-secret-123",
        primary_calendar_url="https://caldav.icloud.com/family/",
        primary_calendar_name="Family",
    )
    service.set_desired_alexa_settings(
        enable_alexa=True,
        allowed_skill_ids=["amzn1.ask.skill.one"],
    )
    service.set_alexa_account_linking_settings(link_code="Family123")

    backup_document = json.loads(service.export_operator_settings_backup()["backup_json"])

    for key in (
        "apple_account_label",
        "apple_username",
        "apple_app_specific_password",
        "apple_primary_calendar_url",
        "apple_primary_calendar_name",
        "desired_alexa_enable",
        "desired_alexa_allowed_skill_ids",
        "alexa_account_linking_client_id",
        "alexa_account_linking_link_code",
        "alexa_account_linking_access_token",
    ):
        service.delete_value(key)

    service.restore_operator_settings_backup(backup_document)

    assert service.get_apple_calendar_settings()["username"] == "family@example.com"
    assert service.get_desired_alexa_settings() == {
        "enable_alexa": True,
        "allowed_skill_ids": ["amzn1.ask.skill.one"],
    }
    restored_linking = service.get_alexa_account_linking_settings()
    assert restored_linking["client_id"] == "calsync-alexa-household"
    assert restored_linking["link_code"] == "FAMILY123"
    assert isinstance(restored_linking["access_token"], str)
    assert restored_linking["access_token"]


def test_operator_settings_can_store_legacy_apple_recovery_hints() -> None:
    settings = _settings()
    service = OperatorSettingsService(settings=settings)

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

    described = service.describe_legacy_apple_recovery_hints()
    assert described["source"] == "product_vault"
    assert described["account_username"] == "kaymayers9@gmail.com"
    assert described["recommended_calendar_name"] == "Calendar"
    assert described["calendars"][0]["is_writable_hint"] is True
    assert described["encrypted_secret_present"] is False
    assert described["can_reuse_saved_password"] is False


def test_operator_settings_can_describe_reusable_legacy_apple_secret() -> None:
    settings = _settings()
    service = OperatorSettingsService(settings=settings)
    recovered_secret = service._fernet.encrypt(b"apple-secret-123").decode("utf-8")

    service.set_legacy_apple_recovery_hints(
        {
            "source_filename": "calsync-db-backup.zip",
            "account_label": "kaymayers9@gmail.com",
            "account_username": "kaymayers9@gmail.com",
            "calendar_home_url": "https://p52-caldav.icloud.com:443/112135872/calendars/",
            "principal_url": "https://caldav.icloud.com/112135872/principal/",
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

    described = service.describe_legacy_apple_recovery_hints()

    assert described["encrypted_secret_present"] is True
    assert described["encrypted_secret_status"] == "reusable_with_current_key"
    assert described["can_reuse_saved_password"] is True
    assert service.get_legacy_apple_recovered_password() == "apple-secret-123"


def test_operator_settings_can_describe_legacy_apple_secret_that_needs_original_key() -> None:
    settings = _settings()
    service = OperatorSettingsService(settings=settings)
    other_settings = settings.model_copy(update={"encryption_key": "different-test-key"})
    other_service = OperatorSettingsService(settings=other_settings)
    encrypted_with_other_key = other_service._fernet.encrypt(b"apple-secret-123").decode(
        "utf-8"
    )

    service.set_legacy_apple_recovery_hints(
        {
            "source_filename": "calsync-db-backup.zip",
            "account_label": "kaymayers9@gmail.com",
            "account_username": "kaymayers9@gmail.com",
            "calendar_home_url": "https://p52-caldav.icloud.com:443/112135872/calendars/",
            "principal_url": "https://caldav.icloud.com/112135872/principal/",
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

    described = service.describe_legacy_apple_recovery_hints()

    assert described["encrypted_secret_present"] is True
    assert described["encrypted_secret_status"] == "needs_original_key"
    assert described["can_reuse_saved_password"] is False
    assert service.get_legacy_apple_recovered_password() is None


def test_operator_settings_can_recover_legacy_apple_secret_with_original_key() -> None:
    settings = _settings()
    service = OperatorSettingsService(settings=settings)
    other_settings = settings.model_copy(update={"encryption_key": "different-test-key"})
    other_service = OperatorSettingsService(settings=other_settings)
    encrypted_with_other_key = other_service._fernet.encrypt(b"apple-secret-123").decode(
        "utf-8"
    )

    service.set_legacy_apple_recovery_hints(
        {
            "source_filename": "calsync-db-backup.zip",
            "account_label": "kaymayers9@gmail.com",
            "account_username": "kaymayers9@gmail.com",
            "calendar_home_url": "https://p52-caldav.icloud.com:443/112135872/calendars/",
            "principal_url": "https://caldav.icloud.com/112135872/principal/",
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

    assert service.get_legacy_apple_recovered_password() is None
    assert (
        service.get_legacy_apple_recovered_password(
            original_encryption_key="different-test-key"
        )
        == "apple-secret-123"
    )


def test_operator_settings_encrypts_apple_calendar_values_at_rest() -> None:
    settings = _settings()
    service = OperatorSettingsService(settings=settings)

    service.set_apple_calendar_settings(
        account_label="Family",
        username="family@example.com",
        app_specific_password="apple-secret-123",
        primary_calendar_url="https://caldav.icloud.com/family/",
        primary_calendar_name="Family",
    )

    apple_state = service.describe_apple_calendar_settings()
    assert apple_state["username"] == "family@example.com"
    assert apple_state["password_saved"] is True
    assert apple_state["source"] == "product_vault"

    session_factory = _get_session_factory_for_url(settings.database_url)
    with session_factory() as session:
        stored_rows = {
            row.key: row.value_encrypted
            for row in session.query(OperatorSetting).all()
        }

    assert stored_rows["apple_username"] != "family@example.com"
    assert stored_rows["apple_app_specific_password"] != "apple-secret-123"
    assert stored_rows["apple_primary_calendar_url"] != "https://caldav.icloud.com/family/"


def test_operator_settings_keeps_existing_apple_password_when_blank_update() -> None:
    settings = _settings()
    service = OperatorSettingsService(settings=settings)

    service.set_apple_calendar_settings(
        account_label="Family",
        username="family@example.com",
        app_specific_password="apple-secret-123",
        primary_calendar_url="https://caldav.icloud.com/family/",
        primary_calendar_name="Family",
    )
    service.set_apple_calendar_settings(
        account_label="Household",
        username="household@example.com",
        app_specific_password="",
        primary_calendar_url="https://caldav.icloud.com/household/",
        primary_calendar_name="Household",
        preserve_existing_password=True,
    )

    apple_settings = service.get_apple_calendar_settings()
    assert apple_settings["account_label"] == "Household"
    assert apple_settings["username"] == "household@example.com"
    assert apple_settings["app_specific_password"] == "apple-secret-123"
    assert apple_settings["primary_calendar_url"] == "https://caldav.icloud.com/household/"


def test_operator_settings_stores_apple_calendar_catalog() -> None:
    settings = _settings()
    service = OperatorSettingsService(settings=settings)

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

    assert service.get_apple_calendar_catalog() == [
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


def test_operator_settings_can_store_multiple_apple_accounts() -> None:
    settings = _settings()
    service = OperatorSettingsService(settings=settings)

    service.upsert_apple_account(
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
    service.upsert_apple_account(
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

    assert service.get_apple_accounts() == [
        {
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
        {
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
    ]


def test_operator_settings_encrypts_google_oauth_values_at_rest() -> None:
    settings = _settings()
    service = OperatorSettingsService(settings=settings)

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

    google_state = service.describe_google_oauth_settings()
    assert google_state["client_id"] == "google-client-id"
    assert google_state["client_secret_saved"] is True
    assert google_state["account_email"] == "kay@example.com"
    assert google_state["refresh_token_saved"] is True
    assert google_state["source"] == "product_vault"

    session_factory = _get_session_factory_for_url(settings.database_url)
    with session_factory() as session:
        stored_rows = {
            row.key: row.value_encrypted
            for row in session.query(OperatorSetting).all()
        }

    assert stored_rows["google_client_id"] != "google-client-id"
    assert stored_rows["google_client_secret"] != "google-client-secret"
    assert stored_rows["google_refresh_token"] != "google-refresh-token"


def test_operator_settings_can_clear_google_account_state() -> None:
    settings = _settings()
    service = OperatorSettingsService(settings=settings)

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
    service.set_google_oauth_state("state-123")

    service.clear_google_oauth_state()
    service.clear_google_account_settings()
    service.clear_google_calendar_catalog()

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
    assert service.get_google_oauth_state() is None


def test_operator_settings_can_store_multiple_google_accounts() -> None:
    settings = _settings()
    service = OperatorSettingsService(settings=settings)

    service.upsert_google_account(
        account_label="Kay Google",
        account_email="kay@example.com",
        refresh_token="kay-refresh-token",
        calendars=[
            {
                "calendar_name": "Primary",
                "calendar_id": "primary",
                "is_default": True,
            },
            {
                "calendar_name": "Family",
                "calendar_id": "family",
                "is_default": False,
            },
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

    assert service.get_google_accounts() == [
        {
            "account_label": "Kay Google",
            "account_email": "kay@example.com",
            "refresh_token": "kay-refresh-token",
            "calendars": [
                {
                    "calendar_name": "Primary",
                    "calendar_id": "primary",
                    "is_default": True,
                },
                {
                    "calendar_name": "Family",
                    "calendar_id": "family",
                    "is_default": False,
                },
            ],
        },
        {
            "account_label": "Work Google",
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


def test_operator_settings_encrypts_microsoft_oauth_values_at_rest() -> None:
    settings = _settings()
    service = OperatorSettingsService(settings=settings)

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

    microsoft_state = service.describe_microsoft_oauth_settings()
    assert microsoft_state["client_id"] == "microsoft-client-id"
    assert microsoft_state["client_secret_saved"] is True
    assert microsoft_state["account_email"] == "kay@example.com"
    assert microsoft_state["refresh_token_saved"] is True
    assert microsoft_state["source"] == "product_vault"

    session_factory = _get_session_factory_for_url(settings.database_url)
    with session_factory() as session:
        stored_rows = {
            row.key: row.value_encrypted
            for row in session.query(OperatorSetting).all()
        }

    assert stored_rows["microsoft_client_id"] != "microsoft-client-id"
    assert stored_rows["microsoft_client_secret"] != "microsoft-client-secret"
    assert stored_rows["microsoft_refresh_token"] != "microsoft-refresh-token"


def test_operator_settings_can_store_calendar_write_verifications() -> None:
    settings = _settings()
    service = OperatorSettingsService(settings=settings)

    service.record_calendar_write_verification(
        target_value="google:kay@example.com:primary",
        provider_type="google",
        provider_label="Google Calendar",
        account_label="Kay Google",
        calendar_name="Primary",
        passed=True,
        message="Write test passed for Primary on Google Calendar (Kay Google).",
        checked_at="2026-05-29T22:30:00+00:00",
    )
    service.record_calendar_write_verification(
        target_value="google:kay@example.com:primary",
        provider_type="google",
        provider_label="Google Calendar",
        account_label="Kay Google",
        calendar_name="Primary",
        passed=False,
        message="Token refresh failed.",
        checked_at="2026-05-29T22:45:00+00:00",
    )

    verification = service.get_calendar_write_verification(
        "google:kay@example.com:primary"
    )

    assert verification == {
        "target_value": "google:kay@example.com:primary",
        "provider_type": "google",
        "provider_label": "Google Calendar",
        "account_label": "Kay Google",
        "calendar_name": "Primary",
        "status": "failed",
        "message": "Token refresh failed.",
        "checked_at": "2026-05-29T22:45:00+00:00",
    }


def test_operator_settings_can_store_multiple_microsoft_accounts() -> None:
    settings = _settings()
    service = OperatorSettingsService(settings=settings)

    service.upsert_microsoft_account(
        account_label="Kay Microsoft",
        account_email="kay@example.com",
        refresh_token="kay-refresh-token",
        calendars=[
            {
                "calendar_name": "Calendar",
                "calendar_id": "primary",
                "is_default": True,
            }
        ],
    )
    service.upsert_microsoft_account(
        account_label="Work Microsoft",
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

    assert service.get_microsoft_accounts() == [
        {
            "account_label": "Kay Microsoft",
            "account_email": "kay@example.com",
            "refresh_token": "kay-refresh-token",
            "calendars": [
                {
                    "calendar_name": "Calendar",
                    "calendar_id": "primary",
                    "is_default": True,
                }
            ],
        },
        {
            "account_label": "Work Microsoft",
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


def test_operator_settings_can_store_public_booking_settings() -> None:
    settings = _settings()
    service = OperatorSettingsService(settings=settings)

    service.set_public_booking_settings(
        page_title="Book time with Kayra",
        page_description="Choose an open time for a household appointment.",
        duration_minutes=45,
        search_window_days=28,
        success_message="You're booked.",
        target_calendar_url="https://caldav.icloud.com/family/",
        booking_weekdays=[0, 1, 2, 3, 4],
        day_start_time="09:00",
        day_end_time="15:00",
    )

    assert service.get_public_booking_settings() == {
        "page_title": "Book time with Kayra",
        "page_description": "Choose an open time for a household appointment.",
        "duration_minutes": 45,
        "search_window_days": 28,
        "success_message": "You're booked.",
        "target_calendar_url": "https://caldav.icloud.com/family/",
        "booking_weekdays": [0, 1, 2, 3, 4],
        "day_start_time": "09:00",
        "day_end_time": "15:00",
    }

    described = service.describe_public_booking_settings()
    assert described["page_title"] == "Book time with Kayra"
    assert described["duration_minutes"] == 45
    assert described["search_window_days"] == 28
    assert described["target_calendar_url"] == "https://caldav.icloud.com/family/"
    assert described["booking_weekdays"] == [0, 1, 2, 3, 4]
    assert described["day_start_time"] == "09:00"
    assert described["day_end_time"] == "15:00"


def test_operator_settings_can_store_multiple_public_booking_types() -> None:
    settings = _settings()
    service = OperatorSettingsService(settings=settings)

    service.set_public_booking_settings(
        page_title="Book time with Kayra",
        page_description="Choose an open time for a household appointment.",
        duration_minutes=45,
        search_window_days=28,
        success_message="You're booked.",
        target_calendar_url="https://caldav.icloud.com/family/",
        booking_weekdays=[0, 1, 2, 3, 4],
        day_start_time="09:00",
        day_end_time="15:00",
    )
    service.upsert_public_booking_type(
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
    service.upsert_public_booking_type(
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

    booking_types = service.describe_public_booking_types()

    assert [item["slug"] for item in booking_types] == [
        "family-follow-up",
        "school-intake",
    ]
    assert booking_types[0]["is_default"] is True
    assert booking_types[0]["public_url"] == "/book/family-follow-up"
    assert booking_types[1]["weekday_summary"] == "Monday, Wednesday, Friday"
    assert booking_types[1]["time_window_summary"] == "10:00 AM to 2:00 PM"

    default_settings = service.describe_public_booking_settings()
    follow_up_settings = service.describe_public_booking_settings(
        slug="family-follow-up"
    )
    school_settings = service.describe_public_booking_settings(slug="school-intake")

    assert default_settings["slug"] == "family-follow-up"
    assert follow_up_settings["page_title"] == "Family follow-up"
    assert school_settings["page_title"] == "School intake call"
    assert school_settings["duration_minutes"] == 30


def test_operator_settings_can_update_and_delete_public_booking_type_defaults() -> None:
    settings = _settings()
    service = OperatorSettingsService(settings=settings)

    service.set_public_booking_settings(
        page_title="Book time with Kayra",
        page_description="Choose an open time for a household appointment.",
        duration_minutes=45,
        search_window_days=28,
        success_message="You're booked.",
        target_calendar_url="https://caldav.icloud.com/family/",
        booking_weekdays=[0, 1, 2, 3, 4],
        day_start_time="09:00",
        day_end_time="15:00",
    )
    service.upsert_public_booking_type(
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
    service.upsert_public_booking_type(
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

    service.set_default_public_booking_type("school-intake")

    updated_types = service.describe_public_booking_types()
    assert updated_types[0]["slug"] == "school-intake"
    assert updated_types[0]["is_default"] is True
    assert updated_types[1]["is_default"] is False
    assert service.describe_public_booking_settings()["slug"] == "school-intake"

    service.delete_public_booking_type("school-intake")

    remaining_types = service.describe_public_booking_types()
    assert [item["slug"] for item in remaining_types] == ["family-follow-up"]
    assert remaining_types[0]["is_default"] is True
    assert service.describe_public_booking_settings()["slug"] == "family-follow-up"
