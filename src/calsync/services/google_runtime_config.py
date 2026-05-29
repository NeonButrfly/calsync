from __future__ import annotations

from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from calsync.config import Settings, get_settings
from calsync.services.operator_settings import OperatorSettingsService


class GoogleRuntimeConfigService:
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
        *,
        calendar_id: str | None = None,
        calendar_name: str | None = None,
    ) -> dict[str, Any]:
        oauth = self._safe_google_oauth_settings()
        account = self._safe_google_account_settings()
        calendars = self.list_calendars()
        selected_calendar = self._select_calendar(
            calendars,
            calendar_id=calendar_id,
            calendar_name=calendar_name,
        )
        ready = bool(
            oauth["client_id"]
            and oauth["client_secret"]
            and account["refresh_token"]
            and selected_calendar["calendar_id"]
        )
        return {
            "account_label": account["account_label"] or account["account_email"] or "",
            "account_email": account["account_email"] or "",
            "refresh_token": account["refresh_token"] or "",
            "client_id": oauth["client_id"] or "",
            "client_secret": oauth["client_secret"] or "",
            "primary_calendar_id": selected_calendar["calendar_id"],
            "primary_calendar_name": selected_calendar["calendar_name"],
            "source": "product_vault"
            if ready or any(oauth.values()) or any(account.values()) or bool(calendars)
            else "missing",
            "ready": ready,
            "calendars": calendars,
        }

    def list_calendars(self) -> list[dict[str, object]]:
        try:
            return self._operator_settings().get_google_calendar_catalog()
        except (ImportError, ModuleNotFoundError, SQLAlchemyError, ValueError):
            return []

    def _safe_google_oauth_settings(self) -> dict[str, str | None]:
        try:
            return self._operator_settings().get_google_oauth_settings()
        except (ImportError, ModuleNotFoundError, SQLAlchemyError):
            return {
                "client_id": None,
                "client_secret": None,
            }

    def _safe_google_account_settings(self) -> dict[str, str | None]:
        try:
            return self._operator_settings().get_google_account_settings()
        except (ImportError, ModuleNotFoundError, SQLAlchemyError):
            return {
                "account_label": None,
                "account_email": None,
                "refresh_token": None,
            }

    def _operator_settings(self) -> OperatorSettingsService:
        if self.operator_settings is None:
            self.operator_settings = OperatorSettingsService(settings=self.settings)
        return self.operator_settings

    @staticmethod
    def _select_calendar(
        calendars: list[dict[str, object]],
        *,
        calendar_id: str | None,
        calendar_name: str | None,
    ) -> dict[str, str]:
        selected = None
        if calendar_id:
            selected = next(
                (
                    item
                    for item in calendars
                    if str(item.get("calendar_id") or "") == calendar_id
                ),
                None,
            )
            if selected is None:
                raise ValueError("Google calendar target ID was not found.")
        if selected is None and calendar_name:
            normalized_target = GoogleRuntimeConfigService._normalize_calendar_name(
                calendar_name
            )
            matches = [
                item
                for item in calendars
                if GoogleRuntimeConfigService._normalize_calendar_name(
                    str(item.get("calendar_name") or "")
                )
                == normalized_target
            ]
            if len(matches) > 1:
                raise ValueError(
                    f"Google calendar target name '{calendar_name}' is ambiguous."
                )
            if not matches:
                raise ValueError(
                    f"Google calendar target name '{calendar_name}' was not found."
                )
            selected = matches[0]
        if selected is None and calendars:
            selected = next(
                (item for item in calendars if bool(item.get("is_default"))),
                calendars[0],
            )
        selected = selected or {
            "calendar_name": "",
            "calendar_id": "",
            "is_default": True,
        }
        return {
            "calendar_name": str(selected.get("calendar_name") or ""),
            "calendar_id": str(selected.get("calendar_id") or ""),
        }

    @staticmethod
    def _normalize_calendar_name(value: str) -> str:
        return " ".join(value.lower().split())
