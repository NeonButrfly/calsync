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
        account_email: str | None = None,
    ) -> dict[str, Any]:
        oauth = self._safe_google_oauth_settings()
        accounts = self.list_accounts()
        selected_account = self._select_account(
            accounts,
            account_email=account_email,
            calendar_id=calendar_id,
            calendar_name=calendar_name,
        )
        calendars = self.list_calendars(account_email=selected_account["account_email"])
        selected_calendar = self._select_calendar(
            calendars,
            calendar_id=calendar_id,
            calendar_name=calendar_name,
            account_email=selected_account["account_email"],
        )
        ready = bool(
            oauth["client_id"]
            and oauth["client_secret"]
            and selected_account["refresh_token"]
            and selected_calendar["calendar_id"]
        )
        return {
            "account_label": selected_account["account_label"] or selected_account["account_email"] or "",
            "account_email": selected_account["account_email"] or "",
            "refresh_token": selected_account["refresh_token"] or "",
            "client_id": oauth["client_id"] or "",
            "client_secret": oauth["client_secret"] or "",
            "primary_calendar_id": selected_calendar["calendar_id"],
            "primary_calendar_name": selected_calendar["calendar_name"],
            "source": "product_vault"
            if ready or any(oauth.values()) or bool(accounts)
            else "missing",
            "ready": ready,
            "calendars": calendars,
            "accounts": accounts,
        }

    def list_accounts(self) -> list[dict[str, object]]:
        try:
            return self._operator_settings().get_google_accounts()
        except (ImportError, ModuleNotFoundError, SQLAlchemyError, ValueError):
            return []

    def list_calendars(
        self,
        *,
        account_email: str | None = None,
    ) -> list[dict[str, object]]:
        calendars: list[dict[str, object]] = []
        for account in self.list_accounts():
            email = str(account.get("account_email") or "")
            if account_email and email.lower() != account_email.strip().lower():
                continue
            for item in account.get("calendars", []):
                calendar_id = str(item.get("calendar_id") or "")
                calendars.append(
                    {
                        "account_label": str(account.get("account_label") or email),
                        "account_email": email,
                        "calendar_name": str(item.get("calendar_name") or ""),
                        "calendar_id": calendar_id,
                        "is_default": bool(item.get("is_default")),
                        "target_value": self.encode_target_value(
                            email,
                            calendar_id,
                        ),
                    }
                )
        return calendars

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
    def encode_target_value(account_email: str, calendar_id: str) -> str:
        return f"google:{account_email}:{calendar_id}"

    @staticmethod
    def decode_target_value(value: str) -> tuple[str | None, str]:
        raw = str(value or "").strip()
        if not raw.startswith("google:"):
            return (None, raw)
        payload = raw.split(":", 1)[1]
        if ":" not in payload:
            return (None, payload)
        account_email, calendar_id = payload.split(":", 1)
        return (account_email or None, calendar_id)

    def _select_account(
        self,
        accounts: list[dict[str, object]],
        *,
        account_email: str | None,
        calendar_id: str | None,
        calendar_name: str | None,
    ) -> dict[str, str]:
        if account_email:
            selected = next(
                (
                    item
                    for item in accounts
                    if str(item.get("account_email") or "").strip().lower()
                    == account_email.strip().lower()
                ),
                None,
            )
            if selected is None:
                raise ValueError(
                    f"Google account '{account_email}' was not found."
                )
            return {
                "account_label": str(selected.get("account_label") or account_email),
                "account_email": str(selected.get("account_email") or ""),
                "refresh_token": str(selected.get("refresh_token") or ""),
            }

        if calendar_id:
            matches = [
                item
                for item in accounts
                if any(
                    str(calendar.get("calendar_id") or "") == calendar_id
                    for calendar in item.get("calendars", [])
                )
            ]
            if len(matches) > 1:
                raise ValueError(
                    f"Google calendar target ID '{calendar_id}' is ambiguous across connected accounts."
                )
            if matches:
                match = matches[0]
                return {
                    "account_label": str(match.get("account_label") or match.get("account_email") or ""),
                    "account_email": str(match.get("account_email") or ""),
                    "refresh_token": str(match.get("refresh_token") or ""),
                }

        if calendar_name:
            normalized_target = self._normalize_calendar_name(calendar_name)
            matches = [
                item
                for item in accounts
                if any(
                    self._normalize_calendar_name(str(calendar.get("calendar_name") or ""))
                    == normalized_target
                    for calendar in item.get("calendars", [])
                )
            ]
            if len(matches) > 1:
                raise ValueError(
                    f"Google calendar target name '{calendar_name}' is ambiguous across connected accounts."
                )
            if matches:
                match = matches[0]
                return {
                    "account_label": str(match.get("account_label") or match.get("account_email") or ""),
                    "account_email": str(match.get("account_email") or ""),
                    "refresh_token": str(match.get("refresh_token") or ""),
                }

        if accounts:
            first = accounts[0]
            return {
                "account_label": str(first.get("account_label") or first.get("account_email") or ""),
                "account_email": str(first.get("account_email") or ""),
                "refresh_token": str(first.get("refresh_token") or ""),
            }

        account = self._safe_google_account_settings()
        return {
            "account_label": str(account["account_label"] or account["account_email"] or ""),
            "account_email": str(account["account_email"] or ""),
            "refresh_token": str(account["refresh_token"] or ""),
        }

    @staticmethod
    def _select_calendar(
        calendars: list[dict[str, object]],
        *,
        calendar_id: str | None,
        calendar_name: str | None,
        account_email: str | None = None,
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
