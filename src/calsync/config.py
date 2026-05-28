from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
    )

    app_host: str = "0.0.0.0"
    app_port: int = 3080
    database_url: str = "postgresql+psycopg://calsync:calsync@db:5432/calsync"
    apple_account_label: str = "Family"
    apple_username: str | None = None
    apple_app_specific_password: str | None = None
    apple_primary_calendar_url: str | None = None
    apple_primary_calendar_name: str = "Family"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
