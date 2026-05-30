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
        username: str | None = None,
    ) -> dict[str, Any]:
        accounts = self.list_accounts()
        calendars = self.list_calendars()
        selected_calendar = self._select_calendar(
            calendars,
            calendar_url=calendar_url,
            calendar_name=calendar_name,
        )
        credentials = self._resolve_credentials(
            accounts=accounts,
            selected_calendar=selected_calendar,
            username=username,
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
            "accounts": accounts,
        }

    def list_accounts(self) -> list[dict[str, object]]:
        vault_accounts = self._vault_accounts()
        if vault_accounts:
            return vault_accounts

        env_account = self._env_account()
        if env_account is not None:
            return [env_account]

        legacy = self._legacy_vault_account()
        if legacy is not None:
            return [legacy]

        return []

    def list_calendars(self) -> list[dict[str, object]]:
        calendars: list[dict[str, object]] = []
        for account in self.list_accounts():
            for item in account.get("calendars", []):
                calendars.append(
                    {
                        "account_label": str(account.get("account_label") or account.get("username") or ""),
                        "username": str(account.get("username") or ""),
                        "calendar_name": str(item.get("calendar_name") or ""),
                        "calendar_url": str(item.get("calendar_url") or ""),
                        "is_default": bool(item.get("is_default")),
                    }
                )
        return calendars

    def _operator_settings(self) -> OperatorSettingsService:
        if self.operator_settings is None:
            self.operator_settings = OperatorSettingsService(settings=self.settings)
        return self.operator_settings

    def _resolve_credentials(
        self,
        *,
        accounts: list[dict[str, object]],
        selected_calendar: dict[str, str],
        username: str | None,
    ) -> dict[str, str]:
        if self.settings.apple_username and self.settings.apple_app_specific_password:
            return {
                "account_label": self.settings.apple_account_label,
                "username": self.settings.apple_username,
                "app_specific_password": self.settings.apple_app_specific_password,
                "source": "deployment_env",
            }

        selected_account = self._select_account(
            accounts,
            selected_calendar=selected_calendar,
            username=username,
        )
        account_label = str(selected_account["account_label"] or "")
        return {
            "account_label": account_label,
            "username": selected_account["username"] or "",
            "app_specific_password": selected_account["app_specific_password"] or "",
            "source": "product_vault" if any(selected_account.values()) else "missing",
        }

    def _env_account(self) -> dict[str, object] | None:
        if not (
            self.settings.apple_username
            and self.settings.apple_app_specific_password
        ):
            return None
        calendars = self._legacy_calendar_catalog()
        if not calendars:
            if not self.settings.apple_primary_calendar_url:
                return None
            calendars = [
                {
                    "calendar_name": self.settings.apple_primary_calendar_name,
                    "calendar_url": self.settings.apple_primary_calendar_url,
                    "is_default": True,
                }
            ]
        return {
            "account_label": self.settings.apple_account_label,
            "username": self.settings.apple_username,
            "app_specific_password": self.settings.apple_app_specific_password,
            "calendars": calendars,
        }

    def _legacy_vault_account(self) -> dict[str, object] | None:
        stored = self._safe_vault_settings()
        calendar_url = stored["primary_calendar_url"] or ""
        if not calendar_url or not stored["username"] or not stored["app_specific_password"]:
            return None
        calendars = self._legacy_calendar_catalog()
        if not calendars:
            calendars = [
                {
                    "calendar_name": stored["primary_calendar_name"]
                    or self.settings.apple_primary_calendar_name,
                    "calendar_url": calendar_url,
                    "is_default": True,
                }
            ]
        return {
            "account_label": stored["account_label"] or stored["username"],
            "username": stored["username"],
            "app_specific_password": stored["app_specific_password"],
            "calendars": calendars,
        }

    def _vault_accounts(self) -> list[dict[str, object]]:
        try:
            return self._operator_settings().get_apple_accounts()
        except (ImportError, ModuleNotFoundError, SQLAlchemyError, ValueError):
            return []

    def _legacy_calendar_catalog(self) -> list[dict[str, object]]:
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
    def _select_account(
        accounts: list[dict[str, object]],
        *,
        selected_calendar: dict[str, str],
        username: str | None,
    ) -> dict[str, str]:
        if username:
            selected = next(
                (
                    item
                    for item in accounts
                    if str(item.get("username") or "").strip().lower()
                    == username.strip().lower()
                ),
                None,
            )
            if selected is None:
                raise ValueError("Apple account username was not found.")
            return {
                "account_label": str(selected.get("account_label") or username),
                "username": str(selected.get("username") or ""),
                "app_specific_password": str(selected.get("app_specific_password") or ""),
            }

        calendar_url = selected_calendar.get("calendar_url") or ""
        if calendar_url:
            matches = [
                item
                for item in accounts
                if any(
                    str(calendar.get("calendar_url") or "") == calendar_url
                    for calendar in item.get("calendars", [])
                )
            ]
            if len(matches) > 1:
                raise ValueError("Apple calendar target URL is ambiguous across accounts.")
            if matches:
                selected = matches[0]
                return {
                    "account_label": str(selected.get("account_label") or selected.get("username") or ""),
                    "username": str(selected.get("username") or ""),
                    "app_specific_password": str(selected.get("app_specific_password") or ""),
                }

        if accounts:
            first = accounts[0]
            return {
                "account_label": str(first.get("account_label") or first.get("username") or ""),
                "username": str(first.get("username") or ""),
                "app_specific_password": str(first.get("app_specific_password") or ""),
            }

        return {
            "account_label": "",
            "username": "",
            "app_specific_password": "",
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
