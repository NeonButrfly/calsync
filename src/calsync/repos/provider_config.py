from __future__ import annotations

from sqlalchemy.orm import Session

from calsync.models import ProviderConfiguration


def get_provider_configuration(
    session: Session,
    provider_type: str,
) -> ProviderConfiguration | None:
    return session.get(ProviderConfiguration, provider_type)


def upsert_provider_configuration(
    session: Session,
    *,
    provider_type: str,
    public_config_json: dict[str, object] | None,
    secret_config_encrypted: str | None,
) -> ProviderConfiguration:
    configuration = get_provider_configuration(session, provider_type)
    if configuration is None:
        configuration = ProviderConfiguration(provider_type=provider_type)
        session.add(configuration)

    configuration.public_config_json = (
        dict(public_config_json) if public_config_json is not None else None
    )
    configuration.secret_config_encrypted = secret_config_encrypted
    session.flush()
    return configuration
