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
