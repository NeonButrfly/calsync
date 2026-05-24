from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from calsync.models import Base
from calsync.services.provider_config import (
    save_microsoft_oauth_configuration,
    resolve_microsoft_oauth_configuration,
)
from calsync.services.providers.microsoft import MicrosoftProviderAdapter


ENCRYPTION_KEY = "phase1-microsoft-provider-encryption-key"


def test_microsoft_provider_configuration_round_trip(tmp_path: Path) -> None:
    with _build_session(tmp_path) as session:
        save_microsoft_oauth_configuration(
            session,
            client_id="microsoft-client-id",
            client_secret="microsoft-client-secret",
            scopes="openid,offline_access,Calendars.ReadWrite",
            encryption_key=ENCRYPTION_KEY,
        )
        session.commit()

        configuration = resolve_microsoft_oauth_configuration(
            session,
            encryption_key=ENCRYPTION_KEY,
        )

    assert configuration is not None
    assert configuration.client_id == "microsoft-client-id"
    assert configuration.scopes == (
        "openid",
        "offline_access",
        "Calendars.ReadWrite",
    )


def test_microsoft_provider_scaffold_reports_provider_identity() -> None:
    adapter = MicrosoftProviderAdapter()

    assert adapter.provider_type == "microsoft"
    assert adapter.auth_mode == "oauth"


def _build_session(tmp_path: Path) -> Session:
    database_path = tmp_path / "microsoft-provider.sqlite3"
    engine = create_engine(
        f"sqlite+pysqlite:///{database_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine)
