from __future__ import annotations

from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from calsync.config import Settings, get_settings
from calsync.services.operator_settings import OperatorSettingsService


class AppleRuntimeConfigService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        operator_settings: OperatorSettingsService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.operator_settings = operator_settings

    def resolve(self) -> dict[str, Any]:
        if (
            self.settings.apple_username
            and self.settings.apple_app_specific_password
            and self.settings.apple_primary_calendar_url
        ):
            return {
                "account_label": self.settings.apple_account_label,
                "username": self.settings.apple_username,
                "app_specific_password": self.settings.apple_app_specific_password,
                "primary_calendar_url": self.settings.apple_primary_calendar_url,
                "primary_calendar_name": self.settings.apple_primary_calendar_name,
                "source": "deployment_env",
                "ready": True,
            }

        try:
            stored = self._operator_settings().get_apple_calendar_settings()
        except (ImportError, ModuleNotFoundError, SQLAlchemyError):
            stored = {
                "account_label": None,
                "username": None,
                "app_specific_password": None,
                "primary_calendar_url": None,
                "primary_calendar_name": None,
            }
        account_label = stored["account_label"] or self.settings.apple_account_label
        primary_calendar_name = (
            stored["primary_calendar_name"] or self.settings.apple_primary_calendar_name
        )
        ready = bool(
            stored["username"]
            and stored["app_specific_password"]
            and stored["primary_calendar_url"]
        )
        return {
            "account_label": account_label,
            "username": stored["username"] or "",
            "app_specific_password": stored["app_specific_password"] or "",
            "primary_calendar_url": stored["primary_calendar_url"] or "",
            "primary_calendar_name": primary_calendar_name,
            "source": "product_vault" if any(stored.values()) else "missing",
            "ready": ready,
        }

    def _operator_settings(self) -> OperatorSettingsService:
        if self.operator_settings is None:
            self.operator_settings = OperatorSettingsService(settings=self.settings)
        return self.operator_settings
