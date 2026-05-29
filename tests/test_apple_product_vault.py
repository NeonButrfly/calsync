import tempfile
from pathlib import Path
from uuid import uuid4

from calsync.config import Settings
from calsync.db import _get_engine_for_url, _get_session_factory_for_url
from calsync.models import Base
from calsync.services.appointments import AppointmentService
from calsync.services.operator_settings import OperatorSettingsService
from calsync.services.readiness import ReadinessService


def _settings() -> Settings:
    db_path = Path(tempfile.gettempdir()) / f"calsync-apple-vault-{uuid4()}.db"
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
        channel_token_runtime_path=".runtime/channel-tokens.json",
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
