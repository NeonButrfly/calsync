from functools import lru_cache
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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def build_external_url(
    request: Request,
    path: str,
    *,
    settings: Settings | None = None,
) -> str:
    resolved_settings = settings or get_settings()
    base_url = str(resolved_settings.public_base_url or request.base_url)
    return join_url(base_url, path)


def build_healthcheck_url(settings: Settings | None = None) -> str:
    resolved_settings = settings or get_settings()
    if resolved_settings.public_base_url:
        return join_url(str(resolved_settings.public_base_url), "/healthz")

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
