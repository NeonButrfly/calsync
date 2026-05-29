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

    def resolve(
        self,
        calendar_url: str | None = None,
        calendar_name: str | None = None,
    ) -> dict[str, Any]:
        credentials = self._resolve_credentials()
        calendars = self.list_calendars()
        selected_calendar = self._select_calendar(
            calendars,
            calendar_url=calendar_url,
            calendar_name=calendar_name,
        )
        ready = bool(
            credentials["username"]
            and credentials["app_specific_password"]
            and selected_calendar["calendar_url"]
        )
        return {
            "account_label": credentials["account_label"],
            "username": credentials["username"],
            "app_specific_password": credentials["app_specific_password"],
            "primary_calendar_url": selected_calendar["calendar_url"],
            "primary_calendar_name": selected_calendar["calendar_name"],
            "source": credentials["source"],
            "ready": ready,
            "calendars": calendars,
        }

    def list_calendars(self) -> list[dict[str, object]]:
        catalog = self._vault_calendar_catalog()
        if catalog:
            return catalog

        env_calendar = self._env_calendar()
        if env_calendar is not None:
            return [env_calendar]

        legacy = self._legacy_vault_calendar()
        if legacy is not None:
            return [legacy]

        return []

    def _operator_settings(self) -> OperatorSettingsService:
        if self.operator_settings is None:
            self.operator_settings = OperatorSettingsService(settings=self.settings)
        return self.operator_settings

    def _resolve_credentials(self) -> dict[str, str]:
        if self.settings.apple_username and self.settings.apple_app_specific_password:
            return {
                "account_label": self.settings.apple_account_label,
                "username": self.settings.apple_username,
                "app_specific_password": self.settings.apple_app_specific_password,
                "source": "deployment_env",
            }

        stored = self._safe_vault_settings()
        return {
            "account_label": stored["account_label"] or self.settings.apple_account_label,
            "username": stored["username"] or "",
            "app_specific_password": stored["app_specific_password"] or "",
            "source": "product_vault" if any(stored.values()) else "missing",
        }

    def _env_calendar(self) -> dict[str, object] | None:
        if not self.settings.apple_primary_calendar_url:
            return None
        return {
            "calendar_name": self.settings.apple_primary_calendar_name,
            "calendar_url": self.settings.apple_primary_calendar_url,
            "is_default": True,
        }

    def _legacy_vault_calendar(self) -> dict[str, object] | None:
        stored = self._safe_vault_settings()
        calendar_url = stored["primary_calendar_url"] or ""
        if not calendar_url:
            return None
        return {
            "calendar_name": stored["primary_calendar_name"]
            or self.settings.apple_primary_calendar_name,
            "calendar_url": calendar_url,
            "is_default": True,
        }

    def _vault_calendar_catalog(self) -> list[dict[str, object]]:
        try:
            return self._operator_settings().get_apple_calendar_catalog()
        except (ImportError, ModuleNotFoundError, SQLAlchemyError, ValueError):
            return []

    def _safe_vault_settings(self) -> dict[str, str | None]:
        try:
            return self._operator_settings().get_apple_calendar_settings()
        except (ImportError, ModuleNotFoundError, SQLAlchemyError):
            return {
                "account_label": None,
                "username": None,
                "app_specific_password": None,
                "primary_calendar_url": None,
                "primary_calendar_name": None,
            }

    @staticmethod
    def _select_calendar(
        calendars: list[dict[str, object]],
        *,
        calendar_url: str | None,
        calendar_name: str | None,
    ) -> dict[str, str]:
        selected = None
        if calendar_url:
            selected = next(
                (
                    item
                    for item in calendars
                    if str(item.get("calendar_url") or "") == calendar_url
                ),
                None,
            )
            if selected is None:
                raise ValueError("Apple calendar target URL was not found.")
        if selected is None and calendar_name:
            normalized_target = AppleRuntimeConfigService._normalize_calendar_name(
                calendar_name
            )
            matches = [
                item
                for item in calendars
                if AppleRuntimeConfigService._normalize_calendar_name(
                    str(item.get("calendar_name") or "")
                )
                == normalized_target
            ]
            if len(matches) > 1:
                raise ValueError(
                    f"Apple calendar target name '{calendar_name}' is ambiguous."
                )
            if not matches:
                raise ValueError(
                    f"Apple calendar target name '{calendar_name}' was not found."
                )
            selected = matches[0]
        if selected is None and calendars:
            selected = next(
                (item for item in calendars if bool(item.get("is_default"))),
                calendars[0],
            )
        selected = selected or {
            "calendar_name": "",
            "calendar_url": "",
            "is_default": True,
        }
        return {
            "calendar_name": str(selected.get("calendar_name") or ""),
            "calendar_url": str(selected.get("calendar_url") or ""),
        }

    @staticmethod
    def _normalize_calendar_name(value: str) -> str:
        return " ".join(value.lower().split())
