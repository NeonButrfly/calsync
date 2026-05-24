from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from calsync.models import Base, ProviderAccount
from calsync.repos.provider_config import get_provider_configuration
from calsync.services.provider_config import (
    DEFAULT_MICROSOFT_OAUTH_SCOPES,
    resolve_microsoft_oauth_configuration,
    save_microsoft_oauth_configuration,
)
from calsync.services.providers.base import get_provider_adapter
from calsync.services.providers.microsoft import (
    MicrosoftProviderAdapter,
    infer_microsoft_account_capabilities,
)


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
        stored_configuration = get_provider_configuration(session, "microsoft")

    assert configuration is not None
    assert configuration.client_id == "microsoft-client-id"
    assert configuration.scopes == (
        "openid",
        "offline_access",
        "Calendars.ReadWrite",
    )
    assert stored_configuration is not None
    assert stored_configuration.provider_type == "microsoft"


def test_microsoft_provider_scaffold_reports_provider_identity() -> None:
    adapter = MicrosoftProviderAdapter()

    assert adapter.provider_type == "microsoft"
    assert adapter.auth_mode == "oauth"


def test_provider_factory_resolves_microsoft_adapter() -> None:
    adapter = get_provider_adapter("microsoft")

    assert isinstance(adapter, MicrosoftProviderAdapter)
    assert adapter.provider_type == "microsoft"


def test_microsoft_provider_configuration_round_trip_supports_space_delimited_scopes(
    tmp_path: Path,
) -> None:
    account = ProviderAccount(
        provider_type="microsoft",
        provider_account_id="microsoft-user",
        provider_metadata={},
    )

    with _build_session(tmp_path) as session:
        save_microsoft_oauth_configuration(
            session,
            client_id="microsoft-client-id",
            client_secret="microsoft-client-secret",
            scopes=(
                "openid profile offline_access "
                "https://graph.microsoft.com/Calendars.ReadWrite"
            ),
            encryption_key=ENCRYPTION_KEY,
        )
        session.commit()

        configuration = resolve_microsoft_oauth_configuration(
            session,
            encryption_key=ENCRYPTION_KEY,
        )

    assert configuration is not None
    assert configuration.scopes == (
        "openid",
        "profile",
        "offline_access",
        "https://graph.microsoft.com/Calendars.ReadWrite",
    )

    account.provider_metadata = {
        "microsoft_scopes": list(configuration.scopes),
    }
    assert infer_microsoft_account_capabilities(account) == ("oauth", True, True)


def test_microsoft_provider_configuration_defaults_blank_scopes(
    tmp_path: Path,
) -> None:
    with _build_session(tmp_path) as session:
        save_microsoft_oauth_configuration(
            session,
            client_id="microsoft-client-id",
            client_secret="microsoft-client-secret",
            scopes="   ",
            encryption_key=ENCRYPTION_KEY,
        )
        session.commit()

        configuration = resolve_microsoft_oauth_configuration(
            session,
            encryption_key=ENCRYPTION_KEY,
        )
        stored_configuration = get_provider_configuration(session, "microsoft")

    assert configuration is not None
    assert configuration.scopes == DEFAULT_MICROSOFT_OAUTH_SCOPES
    assert stored_configuration is not None
    assert stored_configuration.public_config_json is not None
    assert stored_configuration.public_config_json["scopes"] == " ".join(
        DEFAULT_MICROSOFT_OAUTH_SCOPES
    )


def test_microsoft_provider_configuration_defaults_delimiter_only_scopes(
    tmp_path: Path,
) -> None:
    with _build_session(tmp_path) as session:
        save_microsoft_oauth_configuration(
            session,
            client_id="microsoft-client-id",
            client_secret="microsoft-client-secret",
            scopes=", , ,",
            encryption_key=ENCRYPTION_KEY,
        )
        session.commit()

        configuration = resolve_microsoft_oauth_configuration(
            session,
            encryption_key=ENCRYPTION_KEY,
        )
        stored_configuration = get_provider_configuration(session, "microsoft")

    assert configuration is not None
    assert configuration.scopes == DEFAULT_MICROSOFT_OAUTH_SCOPES
    assert stored_configuration is not None
    assert stored_configuration.public_config_json is not None
    assert stored_configuration.public_config_json["scopes"] == " ".join(
        DEFAULT_MICROSOFT_OAUTH_SCOPES
    )


def _build_session(tmp_path: Path) -> Session:
    database_path = tmp_path / "microsoft-provider.sqlite3"
    engine = create_engine(
        f"sqlite+pysqlite:///{database_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine)
