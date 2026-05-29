from __future__ import annotations

import base64
import hashlib

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

    def get_apple_calendar_settings(self) -> dict[str, str | None]:
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
