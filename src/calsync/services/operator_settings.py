from __future__ import annotations

import base64
import hashlib
import json

from cryptography.fernet import Fernet

from calsync.config import Settings, get_settings
from calsync.db import create_session_factory
from calsync.models import OperatorSetting


class OperatorSettingsService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        session_factory=None,
    ) -> None:
        self.settings = settings or get_settings()
        self.session_factory = session_factory or create_session_factory(self.settings)
        key_material = hashlib.sha256(
            self.settings.encryption_key.encode("utf-8")
        ).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(key_material))

    def set_value(self, key: str, value: str) -> None:
        normalized_key = key.strip()
        if not normalized_key:
            raise ValueError("Operator setting key cannot be empty.")
        if not value.strip():
            raise ValueError(f"{normalized_key} cannot be empty.")

        encrypted_value = self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")
        with self.session_factory() as session:
            self._ensure_table(session)
            record = session.get(OperatorSetting, normalized_key)
            if record is None:
                record = OperatorSetting(
                    key=normalized_key,
                    value_encrypted=encrypted_value,
                )
                session.add(record)
            else:
                record.value_encrypted = encrypted_value
            session.commit()

    def get_value(self, key: str) -> str | None:
        with self.session_factory() as session:
            self._ensure_table(session)
            record = session.get(OperatorSetting, key)
            if record is None:
                return None
            return self._fernet.decrypt(
                record.value_encrypted.encode("utf-8")
            ).decode("utf-8")

    def delete_value(self, key: str) -> None:
        with self.session_factory() as session:
            self._ensure_table(session)
            record = session.get(OperatorSetting, key)
            if record is not None:
                session.delete(record)
                session.commit()

    def set_cloudflare_worker_credentials(
        self,
        *,
        account_id: str,
        api_token: str,
        preserve_existing_token: bool = False,
    ) -> None:
        normalized_account_id = account_id.strip()
        normalized_api_token = api_token.strip()
        if not normalized_account_id:
            raise ValueError("Cloudflare account ID is required.")

        existing = self.get_cloudflare_worker_credentials()
        if not normalized_api_token and not (
            preserve_existing_token and existing["api_token"]
        ):
            raise ValueError("Cloudflare API token is required.")

        self.set_value("cloudflare_account_id", normalized_account_id)
        if normalized_api_token:
            self.set_value("cloudflare_api_token", normalized_api_token)

    def get_cloudflare_worker_credentials(self) -> dict[str, str | None]:
        return {
            "account_id": self.get_value("cloudflare_account_id"),
            "api_token": self.get_value("cloudflare_api_token"),
        }

    def set_apple_calendar_settings(
        self,
        *,
        account_label: str,
        username: str,
        app_specific_password: str,
        primary_calendar_url: str,
        primary_calendar_name: str,
        preserve_existing_password: bool = False,
    ) -> None:
        normalized_account_label = account_label.strip()
        normalized_username = username.strip()
        normalized_password = app_specific_password.strip()
        normalized_calendar_url = primary_calendar_url.strip()
        normalized_calendar_name = primary_calendar_name.strip()

        if not normalized_account_label:
            raise ValueError("Apple account label is required.")
        if not normalized_username:
            raise ValueError("Apple username is required.")
        if not normalized_calendar_url:
            raise ValueError("Apple calendar URL is required.")
        if not normalized_calendar_name:
            raise ValueError("Apple calendar name is required.")

        existing = self.get_apple_calendar_settings()
        if not normalized_password and not (
            preserve_existing_password and existing["app_specific_password"]
        ):
            raise ValueError("Apple app-specific password is required.")

        self.set_value("apple_account_label", normalized_account_label)
        self.set_value("apple_username", normalized_username)
        self.set_value("apple_primary_calendar_url", normalized_calendar_url)
        self.set_value("apple_primary_calendar_name", normalized_calendar_name)
        if normalized_password:
            self.set_value("apple_app_specific_password", normalized_password)
        existing_accounts = self.get_apple_accounts()
        existing_account = next(
            (
                item
                for item in existing_accounts
                if str(item.get("username") or "").strip().lower()
                == normalized_username.lower()
            ),
            None,
        )
        existing_calendars = list(existing_account.get("calendars", [])) if existing_account else []
        remaining = [
            item
            for item in existing_calendars
            if str(item.get("calendar_url") or "") != normalized_calendar_url
        ]
        self.upsert_apple_account(
            account_label=normalized_account_label,
            username=normalized_username,
            app_specific_password=normalized_password,
            calendars=[
                {
                    "calendar_name": normalized_calendar_name,
                    "calendar_url": normalized_calendar_url,
                    "is_default": True,
                },
                *[
                    {
                        "calendar_name": str(item["calendar_name"]),
                        "calendar_url": str(item["calendar_url"]),
                        "is_default": False,
                    }
                    for item in remaining
                ],
            ],
            preserve_existing_password=preserve_existing_password,
        )
        accounts = self.get_apple_accounts()
        prioritized = [
            item
            for item in accounts
            if str(item.get("username") or "").strip().lower()
            == normalized_username.lower()
        ] + [
            item
            for item in accounts
            if str(item.get("username") or "").strip().lower()
            != normalized_username.lower()
        ]
        if prioritized:
            self.set_value("apple_accounts", json.dumps(prioritized))
            first = prioritized[0]
            first_primary = next(
                (item for item in first["calendars"] if bool(item.get("is_default"))),
                first["calendars"][0],
            )
            self.set_value("apple_account_label", str(first["account_label"]))
            self.set_value("apple_username", str(first["username"]))
            self.set_value("apple_app_specific_password", str(first["app_specific_password"]))
            self.set_value("apple_primary_calendar_url", str(first_primary["calendar_url"]))
            self.set_value("apple_primary_calendar_name", str(first_primary["calendar_name"]))
            self.set_value("apple_calendar_catalog", json.dumps(first["calendars"]))

    def get_apple_calendar_settings(self) -> dict[str, str | None]:
        accounts = self.get_apple_accounts()
        if accounts:
            first = accounts[0]
            calendars = list(first.get("calendars", []))
            primary = next(
                (item for item in calendars if bool(item.get("is_default"))),
                calendars[0] if calendars else {"calendar_url": None, "calendar_name": None},
            )
            return {
                "account_label": str(first.get("account_label") or ""),
                "username": str(first.get("username") or ""),
                "app_specific_password": str(first.get("app_specific_password") or ""),
                "primary_calendar_url": str(primary.get("calendar_url") or "") or None,
                "primary_calendar_name": str(primary.get("calendar_name") or "") or None,
            }
        return {
            "account_label": self.get_value("apple_account_label"),
            "username": self.get_value("apple_username"),
            "app_specific_password": self.get_value("apple_app_specific_password"),
            "primary_calendar_url": self.get_value("apple_primary_calendar_url"),
            "primary_calendar_name": self.get_value("apple_primary_calendar_name"),
        }

    def describe_apple_calendar_settings(self) -> dict[str, object]:
        values = self.get_apple_calendar_settings()
        return {
            "account_label": values["account_label"] or "",
            "username": values["username"] or "",
            "primary_calendar_url": values["primary_calendar_url"] or "",
            "primary_calendar_name": values["primary_calendar_name"] or "",
            "password_saved": bool(values["app_specific_password"]),
            "source": "product_vault"
            if any(values.values())
            else "missing",
        }

    def upsert_apple_account(
        self,
        *,
        account_label: str,
        username: str,
        app_specific_password: str,
        calendars: list[dict[str, object]],
        preserve_existing_password: bool = False,
    ) -> None:
        normalized_account_label = account_label.strip()
        normalized_username = username.strip()
        normalized_password = app_specific_password.strip()
        if not normalized_account_label:
            raise ValueError("Apple account label is required.")
        if not normalized_username:
            raise ValueError("Apple username is required.")
        normalized_calendars = self._normalize_apple_calendars(calendars)

        accounts = self.get_apple_accounts()
        existing = next(
            (
                item
                for item in accounts
                if str(item.get("username") or "").strip().lower()
                == normalized_username.lower()
            ),
            None,
        )
        current_password = str(self.get_value("apple_app_specific_password") or "")
        if not normalized_password and not (
            preserve_existing_password
            and (
                (existing and existing.get("app_specific_password"))
                or current_password
            )
        ):
            raise ValueError("Apple app-specific password is required.")

        next_accounts: list[dict[str, object]] = []
        replaced = False
        for item in accounts:
            if str(item.get("username") or "").strip().lower() != normalized_username.lower():
                next_accounts.append(item)
                continue
            next_accounts.append(
                {
                    "account_label": normalized_account_label,
                    "username": normalized_username,
                    "app_specific_password": normalized_password
                    or str(item.get("app_specific_password") or "")
                    or current_password,
                    "calendars": normalized_calendars,
                }
            )
            replaced = True
        if not replaced:
            next_accounts.append(
                {
                    "account_label": normalized_account_label,
                    "username": normalized_username,
                    "app_specific_password": normalized_password or current_password,
                    "calendars": normalized_calendars,
                }
            )

        self.set_value("apple_accounts", json.dumps(next_accounts))
        first = next_accounts[0]
        first_primary = next(
            (item for item in first["calendars"] if bool(item.get("is_default"))),
            first["calendars"][0],
        )
        self.set_value("apple_account_label", str(first["account_label"]))
        self.set_value("apple_username", str(first["username"]))
        self.set_value("apple_app_specific_password", str(first["app_specific_password"]))
        self.set_value("apple_primary_calendar_url", str(first_primary["calendar_url"]))
        self.set_value("apple_primary_calendar_name", str(first_primary["calendar_name"]))
        self.set_value("apple_calendar_catalog", json.dumps(first["calendars"]))

    def get_apple_accounts(self) -> list[dict[str, object]]:
        raw = self.get_value("apple_accounts")
        if raw:
            payload = json.loads(raw)
            if isinstance(payload, list):
                accounts = self._coerce_apple_accounts(payload)
                if accounts:
                    return accounts

        legacy = {
            "account_label": self.get_value("apple_account_label"),
            "username": self.get_value("apple_username"),
            "app_specific_password": self.get_value("apple_app_specific_password"),
            "primary_calendar_url": self.get_value("apple_primary_calendar_url"),
            "primary_calendar_name": self.get_value("apple_primary_calendar_name"),
        }
        legacy_catalog = self._coerce_apple_calendars(
            json.loads(self.get_value("apple_calendar_catalog") or "[]")
        )
        if legacy["username"] and legacy["app_specific_password"]:
            if not legacy_catalog and legacy["primary_calendar_url"]:
                legacy_catalog = [
                    {
                        "calendar_name": legacy["primary_calendar_name"] or legacy["primary_calendar_url"],
                        "calendar_url": legacy["primary_calendar_url"],
                        "is_default": True,
                    }
                ]
            return [
                {
                    "account_label": legacy["account_label"] or legacy["username"],
                    "username": legacy["username"],
                    "app_specific_password": legacy["app_specific_password"],
                    "calendars": legacy_catalog,
                }
            ]
        return []

    def add_apple_calendar_target(
        self,
        *,
        account_username: str,
        calendar_name: str,
        calendar_url: str,
        is_default: bool,
    ) -> None:
        normalized_username = account_username.strip()
        if not normalized_username:
            raise ValueError("Apple account username is required.")
        accounts = self.get_apple_accounts()
        existing = next(
            (
                item
                for item in accounts
                if str(item.get("username") or "").strip().lower()
                == normalized_username.lower()
            ),
            None,
        )
        if existing is None:
            raise ValueError("Apple account was not found.")
        calendars = list(existing.get("calendars", []))
        calendars.append(
            {
                "calendar_name": calendar_name,
                "calendar_url": calendar_url,
                "is_default": is_default,
            }
        )
        self.upsert_apple_account(
            account_label=str(existing["account_label"]),
            username=normalized_username,
            app_specific_password="",
            calendars=calendars,
            preserve_existing_password=True,
        )

    def remove_apple_account(self, username: str) -> None:
        normalized_username = username.strip().lower()
        accounts = [
            item
            for item in self.get_apple_accounts()
            if str(item.get("username") or "").strip().lower() != normalized_username
        ]
        if accounts:
            self.set_value("apple_accounts", json.dumps(accounts))
            first = accounts[0]
            first_primary = next(
                (item for item in first["calendars"] if bool(item.get("is_default"))),
                first["calendars"][0],
            )
            self.set_value("apple_account_label", str(first["account_label"]))
            self.set_value("apple_username", str(first["username"]))
            self.set_value("apple_app_specific_password", str(first["app_specific_password"]))
            self.set_value("apple_primary_calendar_url", str(first_primary["calendar_url"]))
            self.set_value("apple_primary_calendar_name", str(first_primary["calendar_name"]))
            self.set_value("apple_calendar_catalog", json.dumps(first["calendars"]))
            return
        self.delete_value("apple_accounts")
        self.delete_value("apple_account_label")
        self.delete_value("apple_username")
        self.delete_value("apple_app_specific_password")
        self.delete_value("apple_primary_calendar_url")
        self.delete_value("apple_primary_calendar_name")
        self.delete_value("apple_calendar_catalog")

    def set_google_oauth_settings(
        self,
        *,
        client_id: str,
        client_secret: str,
        preserve_existing_secret: bool = False,
    ) -> None:
        normalized_client_id = client_id.strip()
        normalized_client_secret = client_secret.strip()
        if not normalized_client_id:
            raise ValueError("Google client ID is required.")

        existing = self.get_google_oauth_settings()
        if not normalized_client_secret and not (
            preserve_existing_secret and existing["client_secret"]
        ):
            raise ValueError("Google client secret is required.")

        self.set_value("google_client_id", normalized_client_id)
        if normalized_client_secret:
            self.set_value("google_client_secret", normalized_client_secret)

    def get_google_oauth_settings(self) -> dict[str, str | None]:
        return {
            "client_id": self.get_value("google_client_id"),
            "client_secret": self.get_value("google_client_secret"),
        }

    def set_google_account_settings(
        self,
        *,
        account_label: str,
        account_email: str,
        refresh_token: str,
        preserve_existing_refresh_token: bool = False,
    ) -> None:
        normalized_account_label = account_label.strip()
        normalized_account_email = account_email.strip()
        normalized_refresh_token = refresh_token.strip()
        if not normalized_account_label:
            raise ValueError("Google account label is required.")
        if not normalized_account_email:
            raise ValueError("Google account email is required.")

        existing = self.get_google_account_settings()
        if not normalized_refresh_token and not (
            preserve_existing_refresh_token and existing["refresh_token"]
        ):
            raise ValueError("Google refresh token is required.")

        self.set_value("google_account_label", normalized_account_label)
        self.set_value("google_account_email", normalized_account_email)
        if normalized_refresh_token:
            self.set_value("google_refresh_token", normalized_refresh_token)
        existing_calendars = self.get_google_calendar_catalog()
        if existing_calendars:
            self.upsert_google_account(
                account_label=normalized_account_label,
                account_email=normalized_account_email,
                refresh_token=normalized_refresh_token,
                calendars=existing_calendars,
                preserve_existing_refresh_token=preserve_existing_refresh_token,
            )

    def get_google_account_settings(self) -> dict[str, str | None]:
        accounts = self.get_google_accounts()
        if accounts:
            first = accounts[0]
            return {
                "account_label": str(first["account_label"] or ""),
                "account_email": str(first["account_email"] or ""),
                "refresh_token": str(first["refresh_token"] or ""),
            }
        return {
            "account_label": self.get_value("google_account_label"),
            "account_email": self.get_value("google_account_email"),
            "refresh_token": self.get_value("google_refresh_token"),
        }

    def set_google_calendar_catalog(self, calendars: list[dict[str, object]]) -> None:
        normalized = self._normalize_google_calendars(calendars)
        self.set_value("google_calendar_catalog", json.dumps(normalized))
        account = self.get_google_account_settings()
        if account["account_email"]:
            self.upsert_google_account(
                account_label=str(account["account_label"] or account["account_email"] or ""),
                account_email=str(account["account_email"] or ""),
                refresh_token=str(account["refresh_token"] or ""),
                calendars=normalized,
                preserve_existing_refresh_token=True,
            )

    def get_google_calendar_catalog(self) -> list[dict[str, object]]:
        accounts = self.get_google_accounts()
        if accounts:
            calendars = self._coerce_google_calendars(accounts[0].get("calendars"))
            if calendars:
                return calendars
        raw = self.get_value("google_calendar_catalog")
        if not raw:
            return []
        payload = json.loads(raw)
        return self._coerce_google_calendars(payload)

    def get_google_accounts(self) -> list[dict[str, object]]:
        raw = self.get_value("google_accounts")
        if raw:
            payload = json.loads(raw)
            if isinstance(payload, list):
                accounts = self._coerce_google_accounts(payload)
                if accounts:
                    return accounts

        legacy_account = {
            "account_label": self.get_value("google_account_label"),
            "account_email": self.get_value("google_account_email"),
            "refresh_token": self.get_value("google_refresh_token"),
        }
        legacy_catalog = self._coerce_google_calendars(
            json.loads(self.get_value("google_calendar_catalog") or "[]")
        )
        if legacy_account["account_email"] and legacy_account["refresh_token"]:
            return [
                {
                    "account_label": legacy_account["account_label"]
                    or legacy_account["account_email"],
                    "account_email": legacy_account["account_email"],
                    "refresh_token": legacy_account["refresh_token"],
                    "calendars": legacy_catalog,
                }
            ]
        return []

    def upsert_google_account(
        self,
        *,
        account_label: str,
        account_email: str,
        refresh_token: str,
        calendars: list[dict[str, object]],
        preserve_existing_refresh_token: bool = False,
    ) -> None:
        normalized_account_label = account_label.strip()
        normalized_account_email = account_email.strip()
        normalized_refresh_token = refresh_token.strip()
        if not normalized_account_label:
            raise ValueError("Google account label is required.")
        if not normalized_account_email:
            raise ValueError("Google account email is required.")
        normalized_calendars = self._normalize_google_calendars(calendars)

        accounts = self.get_google_accounts()
        existing = next(
            (
                item
                for item in accounts
                if str(item.get("account_email") or "").strip().lower()
                == normalized_account_email.lower()
            ),
            None,
        )
        if not normalized_refresh_token and not (
            preserve_existing_refresh_token and existing and existing.get("refresh_token")
        ):
            raise ValueError("Google refresh token is required.")

        next_accounts: list[dict[str, object]] = []
        replaced = False
        for item in accounts:
            if str(item.get("account_email") or "").strip().lower() != normalized_account_email.lower():
                next_accounts.append(item)
                continue
            next_accounts.append(
                {
                    "account_label": normalized_account_label,
                    "account_email": normalized_account_email,
                    "refresh_token": normalized_refresh_token
                    or str(item.get("refresh_token") or ""),
                    "calendars": normalized_calendars,
                }
            )
            replaced = True
        if not replaced:
            next_accounts.append(
                {
                    "account_label": normalized_account_label,
                    "account_email": normalized_account_email,
                    "refresh_token": normalized_refresh_token,
                    "calendars": normalized_calendars,
                }
            )

        self.set_value("google_accounts", json.dumps(next_accounts))
        first = next_accounts[0]
        self.set_value("google_account_label", str(first["account_label"]))
        self.set_value("google_account_email", str(first["account_email"]))
        self.set_value("google_refresh_token", str(first["refresh_token"]))
        self.set_value("google_calendar_catalog", json.dumps(first["calendars"]))

    def remove_google_account(self, account_email: str) -> None:
        normalized_account_email = account_email.strip().lower()
        accounts = [
            item
            for item in self.get_google_accounts()
            if str(item.get("account_email") or "").strip().lower() != normalized_account_email
        ]
        if accounts:
            self.set_value("google_accounts", json.dumps(accounts))
            first = accounts[0]
            self.set_value("google_account_label", str(first["account_label"]))
            self.set_value("google_account_email", str(first["account_email"]))
            self.set_value("google_refresh_token", str(first["refresh_token"]))
            self.set_value("google_calendar_catalog", json.dumps(first["calendars"]))
            return
        self.delete_value("google_accounts")
        self.clear_google_account_settings()
        self.clear_google_calendar_catalog()

    def _coerce_google_accounts(self, payload: object) -> list[dict[str, object]]:
        if not isinstance(payload, list):
            return []
        accounts: list[dict[str, object]] = []
        seen_emails: set[str] = set()
        for item in payload:
            if not isinstance(item, dict):
                continue
            account_label = str(item.get("account_label") or "").strip()
            account_email = str(item.get("account_email") or "").strip()
            refresh_token = str(item.get("refresh_token") or "").strip()
            calendars = self._coerce_google_calendars(item.get("calendars"))
            if not account_email or not refresh_token:
                continue
            email_key = account_email.lower()
            if email_key in seen_emails:
                continue
            seen_emails.add(email_key)
            accounts.append(
                {
                    "account_label": account_label or account_email,
                    "account_email": account_email,
                    "refresh_token": refresh_token,
                    "calendars": calendars,
                }
            )
        return accounts

    def _coerce_google_calendars(self, payload: object) -> list[dict[str, object]]:
        if not isinstance(payload, list):
            return []
        calendars: list[dict[str, object]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            calendar_name = str(item.get("calendar_name") or "").strip()
            calendar_id = str(item.get("calendar_id") or "").strip()
            if not calendar_name or not calendar_id:
                continue
            calendars.append(
                {
                    "calendar_name": calendar_name,
                    "calendar_id": calendar_id,
                    "is_default": bool(item.get("is_default")),
                }
            )
        if calendars and not any(item["is_default"] for item in calendars):
            calendars[0]["is_default"] = True
        return calendars

    def _normalize_google_calendars(
        self,
        calendars: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        if not calendars:
            raise ValueError("At least one Google calendar is required.")

        normalized: list[dict[str, object]] = []
        seen_ids: set[str] = set()
        default_index = None
        for index, item in enumerate(calendars):
            calendar_name = str(item.get("calendar_name") or "").strip()
            calendar_id = str(item.get("calendar_id") or "").strip()
            is_default = bool(item.get("is_default"))
            if not calendar_name:
                raise ValueError("Google calendar name is required.")
            if not calendar_id:
                raise ValueError("Google calendar ID is required.")
            if calendar_id in seen_ids:
                raise ValueError("Google calendar IDs must be unique.")
            seen_ids.add(calendar_id)
            if is_default and default_index is None:
                default_index = index
            normalized.append(
                {
                    "calendar_name": calendar_name,
                    "calendar_id": calendar_id,
                    "is_default": False,
                }
            )

        if default_index is None:
            default_index = 0
        normalized[default_index]["is_default"] = True
        return normalized

    def describe_google_oauth_settings(self) -> dict[str, object]:
        oauth = self.get_google_oauth_settings()
        account = self.get_google_account_settings()
        catalog = self.get_google_calendar_catalog()
        accounts = self.get_google_accounts()
        has_any = any(oauth.values()) or any(account.values()) or bool(catalog) or bool(accounts)
        return {
            "client_id": oauth["client_id"] or "",
            "client_secret_saved": bool(oauth["client_secret"]),
            "account_label": account["account_label"] or "",
            "account_email": account["account_email"] or "",
            "refresh_token_saved": bool(account["refresh_token"]),
            "calendar_count": len(catalog),
            "account_count": len(accounts),
            "source": "product_vault" if has_any else "missing",
        }

    def set_google_oauth_state(self, state: str) -> None:
        self.set_value("google_oauth_state", state)

    def get_google_oauth_state(self) -> str | None:
        return self.get_value("google_oauth_state")

    def clear_google_oauth_state(self) -> None:
        self.delete_value("google_oauth_state")

    def clear_google_account_settings(self) -> None:
        self.delete_value("google_account_label")
        self.delete_value("google_account_email")
        self.delete_value("google_refresh_token")
        self.delete_value("google_accounts")

    def clear_google_calendar_catalog(self) -> None:
        self.delete_value("google_calendar_catalog")

    def set_apple_calendar_catalog(self, calendars: list[dict[str, object]]) -> None:
        normalized = self._normalize_apple_calendars(calendars)
        self.set_value("apple_calendar_catalog", json.dumps(normalized))
        account = self.get_apple_calendar_settings()
        if account["username"]:
            self.upsert_apple_account(
                account_label=str(account["account_label"] or account["username"] or ""),
                username=str(account["username"] or ""),
                app_specific_password=str(account["app_specific_password"] or ""),
                calendars=normalized,
                preserve_existing_password=True,
            )

    def get_apple_calendar_catalog(self) -> list[dict[str, object]]:
        accounts = self.get_apple_accounts()
        if accounts:
            calendars: list[dict[str, object]] = []
            for account in accounts:
                for item in account.get("calendars", []):
                    calendars.append(
                        {
                            "calendar_name": str(item.get("calendar_name") or ""),
                            "calendar_url": str(item.get("calendar_url") or ""),
                            "is_default": bool(item.get("is_default")),
                        }
                    )
            return calendars
        raw = self.get_value("apple_calendar_catalog")
        if not raw:
            return []
        payload = json.loads(raw)
        return self._coerce_apple_calendars(payload)

    def _coerce_apple_accounts(self, payload: object) -> list[dict[str, object]]:
        if not isinstance(payload, list):
            return []
        accounts: list[dict[str, object]] = []
        seen_usernames: set[str] = set()
        for item in payload:
            if not isinstance(item, dict):
                continue
            username = str(item.get("username") or "").strip()
            password = str(item.get("app_specific_password") or "").strip()
            if not username or not password:
                continue
            username_key = username.lower()
            if username_key in seen_usernames:
                continue
            seen_usernames.add(username_key)
            accounts.append(
                {
                    "account_label": str(item.get("account_label") or username),
                    "username": username,
                    "app_specific_password": password,
                    "calendars": self._coerce_apple_calendars(item.get("calendars")),
                }
            )
        return accounts

    def _coerce_apple_calendars(self, payload: object) -> list[dict[str, object]]:
        if not isinstance(payload, list):
            return []
        calendars: list[dict[str, object]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            calendar_name = str(item.get("calendar_name") or "").strip()
            calendar_url = str(item.get("calendar_url") or "").strip()
            if not calendar_name or not calendar_url:
                continue
            calendars.append(
                {
                    "calendar_name": calendar_name,
                    "calendar_url": calendar_url,
                    "is_default": bool(item.get("is_default")),
                }
            )
        if calendars and not any(item["is_default"] for item in calendars):
            calendars[0]["is_default"] = True
        return calendars

    def _normalize_apple_calendars(
        self,
        calendars: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        if not calendars:
            raise ValueError("At least one Apple calendar is required.")

        normalized: list[dict[str, object]] = []
        seen_urls: set[str] = set()
        default_index = None
        for index, item in enumerate(calendars):
            calendar_name = str(item.get("calendar_name") or "").strip()
            calendar_url = str(item.get("calendar_url") or "").strip()
            is_default = bool(item.get("is_default"))
            if not calendar_name:
                raise ValueError("Apple calendar name is required.")
            if not calendar_url:
                raise ValueError("Apple calendar URL is required.")
            if calendar_url in seen_urls:
                raise ValueError("Apple calendar URLs must be unique.")
            seen_urls.add(calendar_url)
            if is_default and default_index is None:
                default_index = index
            normalized.append(
                {
                    "calendar_name": calendar_name,
                    "calendar_url": calendar_url,
                    "is_default": False,
                }
            )

        if default_index is None:
            default_index = 0
        normalized[default_index]["is_default"] = True
        return normalized

    def describe_cloudflare_worker_credentials(self) -> dict[str, object]:
        values = self.get_cloudflare_worker_credentials()
        return {
            "account_id": values["account_id"] or "",
            "api_token_saved": bool(values["api_token"]),
            "source": "product_vault"
            if values["account_id"] or values["api_token"]
            else "missing",
        }

    @staticmethod
    def _ensure_table(session) -> None:
        OperatorSetting.__table__.create(bind=session.get_bind(), checkfirst=True)
