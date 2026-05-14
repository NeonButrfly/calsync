from functools import lru_cache
from ipaddress import ip_address
from urllib.parse import urlsplit, urlunsplit

from fastapi import Request
from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_host: str = "0.0.0.0"
    app_port: int = 3080
    public_base_url: AnyHttpUrl | None = None
    database_url: str = "sqlite+pysqlite:///./calsync.db"
    session_secret: str | None = None
    encryption_key: str | None = None
    sync_poll_seconds: int = 300
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_scopes: str = (
        "openid,email,profile,https://www.googleapis.com/auth/calendar.readonly"
    )
    google_oauth_redirect_path: str = "/auth/google/callback"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def build_external_url(
    request: Request,
    path: str,
    *,
    settings: Settings | None = None,
    public_base_url: str | None = None,
) -> str:
    resolved_settings = settings or get_settings()
    base_url = _resolve_public_base_url(
        request,
        settings=resolved_settings,
        public_base_url=public_base_url,
    )
    return join_url(base_url, path)


def build_google_callback_url(
    request: Request,
    *,
    settings: Settings | None = None,
    public_base_url: str | None = None,
) -> str:
    resolved_settings = settings or get_settings()
    request_base_url = str(request.base_url)
    resolved_public_base_url = _resolve_configured_public_base_url(
        resolved_settings,
        public_base_url=public_base_url,
    )
    if resolved_public_base_url:
        public_callback_url = build_google_callback_url_from_base(
            resolved_public_base_url,
            settings=resolved_settings,
        )
        request_callback_url = build_google_callback_url_from_base(
            request_base_url,
            settings=resolved_settings,
        )
        if (
            validate_google_callback_url(public_callback_url) is not None
            and validate_google_callback_url(request_callback_url) is None
        ):
            return request_callback_url
    return build_google_callback_url_from_base(
        resolved_public_base_url or request_base_url,
        settings=resolved_settings,
    )


def build_google_callback_url_from_base(
    base_url: str,
    *,
    settings: Settings | None = None,
) -> str:
    resolved_settings = settings or get_settings()
    return join_url(base_url, resolved_settings.google_oauth_redirect_path)


def get_google_oauth_scopes(settings: Settings | None = None) -> tuple[str, ...]:
    resolved_settings = settings or get_settings()
    return tuple(
        scope.strip()
        for scope in resolved_settings.google_oauth_scopes.split(",")
        if scope.strip()
    )


def validate_google_callback_url(callback_url: str) -> str | None:
    split = urlsplit(callback_url)
    if split.scheme not in {"http", "https"}:
        return "Google OAuth callback URLs must use http or https."

    hostname = split.hostname
    if not hostname:
        return "Google OAuth callback URL must include a hostname."

    if _is_localhost_hostname(hostname):
        return None if split.scheme == "http" else None

    if _is_ip_address(hostname):
        return (
            "Google OAuth does not allow raw IP addresses as redirect URIs except "
            "localhost. Use localhost on the server itself, or save a Public "
            "app URL with an HTTPS hostname registered with Google."
        )

    if split.scheme != "https":
        return (
            "Google OAuth requires an HTTPS hostname for non-localhost callbacks. "
            "Use localhost on the server itself, or save a Public app URL with an "
            "HTTPS hostname registered with Google."
        )

    return None


def has_google_oauth_config(settings: Settings | None = None) -> bool:
    resolved_settings = settings or get_settings()
    return bool(
        resolved_settings.google_oauth_client_id
        and resolved_settings.google_oauth_client_secret
    )


def build_healthcheck_url(
    settings: Settings | None = None,
    *,
    public_base_url: str | None = None,
) -> str:
    resolved_settings = settings or get_settings()
    resolved_public_base_url = _resolve_configured_public_base_url(
        resolved_settings,
        public_base_url=public_base_url,
    )
    if resolved_public_base_url:
        return join_url(resolved_public_base_url, "/healthz")

    host = (
        "127.0.0.1"
        if resolved_settings.app_host == "0.0.0.0"
        else resolved_settings.app_host
    )
    return join_url(f"http://{host}:{resolved_settings.app_port}", "/healthz")


def join_url(base_url: str, path: str) -> str:
    split = urlsplit(base_url)
    base_path = split.path.rstrip("/")
    extra_path = path.strip()
    if not extra_path.startswith("/"):
        extra_path = f"/{extra_path}"

    return urlunsplit(
        (
            split.scheme,
            split.netloc,
            f"{base_path}{extra_path}",
            "",
            "",
        )
    )


def _is_ip_address(hostname: str) -> bool:
    try:
        ip_address(hostname)
    except ValueError:
        return False
    return True


def _is_localhost_hostname(hostname: str) -> bool:
    return hostname in {"localhost", "127.0.0.1", "::1"}


def _resolve_public_base_url(
    request: Request,
    *,
    settings: Settings,
    public_base_url: str | None,
) -> str:
    return _resolve_configured_public_base_url(
        settings,
        public_base_url=public_base_url,
    ) or str(request.base_url)


def _resolve_configured_public_base_url(
    settings: Settings,
    *,
    public_base_url: str | None,
) -> str | None:
    if public_base_url:
        return public_base_url
    if settings.public_base_url:
        return str(settings.public_base_url)
    return None
