from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from calsync.config import Settings, get_google_oauth_scopes, get_settings
from calsync.crypto import decrypt_text, encrypt_text
from calsync.repos.provider_config import (
    get_provider_configuration,
    upsert_provider_configuration,
)


GOOGLE_OAUTH_PROVIDER_TYPE = "google_oauth"


@dataclass(frozen=True)
class GoogleOAuthConfiguration:
    client_id: str
    client_secret: str
    scopes: tuple[str, ...]
    source: str


def get_google_provider_configuration_snapshot(
    session: Session,
    *,
    settings: Settings | None = None,
) -> dict[str, object]:
    resolved_settings = settings or get_settings()
    configuration = get_provider_configuration(session, GOOGLE_OAUTH_PROVIDER_TYPE)
    if configuration is not None:
        public_config = dict(configuration.public_config_json or {})
        return {
            "client_id": str(public_config.get("client_id") or ""),
            "scopes": str(
                public_config.get("scopes")
                or ",".join(get_google_oauth_scopes(resolved_settings))
            ),
            "configured": bool(
                public_config.get("client_id") and configuration.secret_config_encrypted
            ),
            "source": "database",
            "has_secret": configuration.secret_config_encrypted is not None,
        }

    return {
        "client_id": str(resolved_settings.google_oauth_client_id or ""),
        "scopes": ",".join(get_google_oauth_scopes(resolved_settings)),
        "configured": bool(
            resolved_settings.google_oauth_client_id
            and resolved_settings.google_oauth_client_secret
        ),
        "source": "environment",
        "has_secret": bool(resolved_settings.google_oauth_client_secret),
    }


def has_google_oauth_configuration(
    session: Session,
    *,
    settings: Settings | None = None,
) -> bool:
    snapshot = get_google_provider_configuration_snapshot(session, settings=settings)
    return bool(snapshot["configured"])


def resolve_google_oauth_configuration(
    session: Session | None,
    *,
    settings: Settings | None = None,
    encryption_key: str | None = None,
) -> GoogleOAuthConfiguration | None:
    resolved_settings = settings or get_settings()
    configuration = (
        get_provider_configuration(session, GOOGLE_OAUTH_PROVIDER_TYPE)
        if session is not None
        else None
    )
    if configuration is not None:
        public_config = dict(configuration.public_config_json or {})
        client_id = str(public_config.get("client_id") or "").strip()
        if not client_id or not configuration.secret_config_encrypted:
            return None
        if not encryption_key:
            raise RuntimeError(
                "CalSync encryption_key must be configured explicitly."
            )
        client_secret = decrypt_text(
            encryption_key,
            configuration.secret_config_encrypted,
        )
        scopes = _split_scopes(
            str(
                public_config.get("scopes")
                or ",".join(get_google_oauth_scopes(resolved_settings))
            )
        )
        return GoogleOAuthConfiguration(
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes,
            source="database",
        )

    if (
        resolved_settings.google_oauth_client_id
        and resolved_settings.google_oauth_client_secret
    ):
        return GoogleOAuthConfiguration(
            client_id=resolved_settings.google_oauth_client_id,
            client_secret=resolved_settings.google_oauth_client_secret,
            scopes=get_google_oauth_scopes(resolved_settings),
            source="environment",
        )
    return None


def save_google_oauth_configuration(
    session: Session,
    *,
    client_id: str,
    client_secret: str | None,
    scopes: str,
    encryption_key: str,
    settings: Settings | None = None,
) -> None:
    resolved_settings = settings or get_settings()
    existing = get_provider_configuration(session, GOOGLE_OAUTH_PROVIDER_TYPE)
    existing_secret = existing.secret_config_encrypted if existing is not None else None
    normalized_secret = (client_secret or "").strip()
    if not normalized_secret and existing_secret is None:
        raise ValueError("Google client secret is required.")

    upsert_provider_configuration(
        session,
        provider_type=GOOGLE_OAUTH_PROVIDER_TYPE,
        public_config_json={
            "client_id": client_id.strip(),
            "scopes": scopes.strip()
            or ",".join(get_google_oauth_scopes(settings=resolved_settings)),
        },
        secret_config_encrypted=(
            encrypt_text(encryption_key, normalized_secret)
            if normalized_secret
            else existing_secret
        ),
    )


def _split_scopes(scope_text: str) -> tuple[str, ...]:
    return tuple(scope.strip() for scope in scope_text.split(",") if scope.strip())
