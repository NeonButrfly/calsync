from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
from datetime import UTC, datetime

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

    @staticmethod
    def _build_fernet_for_key(encryption_key: str) -> Fernet:
        key_material = hashlib.sha256(encryption_key.encode("utf-8")).digest()
        return Fernet(base64.urlsafe_b64encode(key_material))

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

    def export_operator_settings_backup(self) -> dict[str, object]:
        settings_map = self._read_all_settings_plaintext()
        exported_at = datetime.now(UTC).isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        )
        encrypted_payload = self._fernet.encrypt(
            json.dumps(
                {
                    "version": 1,
                    "settings": settings_map,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).decode("utf-8")
        backup_document = {
            "kind": "calsync_operator_settings_backup",
            "version": 1,
            "exported_at": exported_at,
            "setting_count": len(settings_map),
            "encrypted_payload": encrypted_payload,
        }
        return {
            "filename": f"calsync-operator-settings-backup-{exported_at.replace(':', '').replace('-', '')}.json",
            "backup_json": json.dumps(backup_document, indent=2, sort_keys=True),
            "setting_count": len(settings_map),
        }

    def restore_operator_settings_backup(self, backup_document: dict[str, object]) -> int:
        if str(backup_document.get("kind") or "") != "calsync_operator_settings_backup":
            raise ValueError("Backup file is not a CalSync operator settings export.")
        if int(backup_document.get("version") or 0) != 1:
            raise ValueError("Backup version is not supported.")
        encrypted_payload = str(backup_document.get("encrypted_payload") or "").strip()
        if not encrypted_payload:
            raise ValueError("Backup file is missing the encrypted payload.")
        try:
            payload = json.loads(
                self._fernet.decrypt(encrypted_payload.encode("utf-8")).decode("utf-8")
            )
        except Exception as exc:
            raise ValueError(
                "Backup file could not be decrypted with this CalSync encryption key."
            ) from exc
        settings_map = payload.get("settings")
        if not isinstance(settings_map, dict):
            raise ValueError("Backup payload does not contain operator settings.")

        normalized_settings: dict[str, str] = {}
        for key, value in settings_map.items():
            normalized_key = str(key or "").strip()
            normalized_value = str(value or "").strip()
            if not normalized_key or not normalized_value:
                continue
            normalized_settings[normalized_key] = normalized_value

        with self.session_factory() as session:
            self._ensure_table(session)
            existing_records = {
                record.key: record
                for record in session.query(OperatorSetting).all()
            }
            for key in list(existing_records):
                if key not in normalized_settings:
                    session.delete(existing_records[key])
            for key, value in normalized_settings.items():
                encrypted_value = self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")
                record = existing_records.get(key)
                if record is None:
                    session.add(
                        OperatorSetting(
                            key=key,
                            value_encrypted=encrypted_value,
                        )
                    )
                else:
                    record.value_encrypted = encrypted_value
            session.commit()
        return len(normalized_settings)

    def set_legacy_apple_recovery_hints(self, hints: dict[str, object]) -> None:
        normalized = {
            "source_filename": str(hints.get("source_filename") or "").strip(),
            "account_label": str(hints.get("account_label") or "").strip(),
            "account_username": str(hints.get("account_username") or "").strip(),
            "principal_url": str(hints.get("principal_url") or "").strip(),
            "calendar_home_url": str(hints.get("calendar_home_url") or "").strip(),
            "credential_secret_encrypted": str(
                hints.get("credential_secret_encrypted") or ""
            ).strip(),
            "recommended_calendar_name": str(
                hints.get("recommended_calendar_name") or ""
            ).strip(),
            "recommended_calendar_url": str(
                hints.get("recommended_calendar_url") or ""
            ).strip(),
            "calendar_count": int(hints.get("calendar_count") or 0),
            "calendars": [
                {
                    "calendar_name": str(item.get("calendar_name") or "").strip(),
                    "calendar_url": str(item.get("calendar_url") or "").strip(),
                    "calendar_role": str(item.get("calendar_role") or "").strip(),
                    "enabled": bool(item.get("enabled")),
                    "is_writable_hint": bool(item.get("is_writable_hint")),
                }
                for item in (hints.get("calendars") or [])
                if isinstance(item, dict)
                and str(item.get("calendar_name") or "").strip()
                and str(item.get("calendar_url") or "").strip()
            ],
        }
        if not normalized["account_username"]:
            raise ValueError("Legacy Apple recovery hints need an Apple username.")
        if not normalized["calendars"]:
            raise ValueError("Legacy Apple recovery hints need at least one Apple calendar.")
        self.set_value("legacy_apple_recovery_hints", json.dumps(normalized))

    def get_legacy_apple_recovery_hints(self) -> dict[str, object]:
        raw = self.get_value("legacy_apple_recovery_hints")
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def describe_legacy_apple_recovery_hints(self) -> dict[str, object]:
        payload = self.get_legacy_apple_recovery_hints()
        if not payload:
            return {
                "source": "missing",
                "source_filename": "",
                "account_label": "",
                "account_username": "",
                "principal_url": "",
                "calendar_home_url": "",
                "encrypted_secret_present": False,
                "encrypted_secret_status": "missing",
                "encrypted_secret_detail": "",
                "can_reuse_saved_password": False,
                "recommended_calendar_name": "",
                "recommended_calendar_url": "",
                "calendar_count": 0,
                "calendars": [],
            }
        calendars = [
            {
                "calendar_name": str(item.get("calendar_name") or ""),
                "calendar_url": str(item.get("calendar_url") or ""),
                "calendar_role": str(item.get("calendar_role") or ""),
                "enabled": bool(item.get("enabled")),
                "is_writable_hint": bool(item.get("is_writable_hint")),
            }
            for item in payload.get("calendars", [])
            if isinstance(item, dict)
        ]
        encrypted_secret = str(payload.get("credential_secret_encrypted") or "").strip()
        encrypted_secret_present = bool(encrypted_secret)
        encrypted_secret_status = "missing"
        encrypted_secret_detail = ""
        if encrypted_secret_present:
            try:
                recovered_secret = self._fernet.decrypt(
                    encrypted_secret.encode("utf-8")
                ).decode("utf-8")
                if recovered_secret.strip():
                    encrypted_secret_status = "reusable_with_current_key"
                    encrypted_secret_detail = (
                        "The preserved Apple app-specific password is reusable with the current CalSync encryption key."
                    )
                else:
                    encrypted_secret_status = "needs_original_key"
                    encrypted_secret_detail = (
                        "The preserved Apple app-specific password was empty after decryption. Save a fresh app-specific password."
                    )
            except Exception:
                encrypted_secret_status = "needs_original_key"
                encrypted_secret_detail = (
                    "The preserved Apple app-specific password needs the original CalSync encryption key or a fresh manual replacement."
                )
        return {
            "source": "product_vault",
            "source_filename": str(payload.get("source_filename") or ""),
            "account_label": str(payload.get("account_label") or ""),
            "account_username": str(payload.get("account_username") or ""),
            "principal_url": str(payload.get("principal_url") or ""),
            "calendar_home_url": str(payload.get("calendar_home_url") or ""),
            "encrypted_secret_present": encrypted_secret_present,
            "encrypted_secret_status": encrypted_secret_status,
            "encrypted_secret_detail": encrypted_secret_detail,
            "can_reuse_saved_password": (
                encrypted_secret_status == "reusable_with_current_key"
            ),
            "recommended_calendar_name": str(payload.get("recommended_calendar_name") or ""),
            "recommended_calendar_url": str(payload.get("recommended_calendar_url") or ""),
            "calendar_count": int(payload.get("calendar_count") or len(calendars)),
            "calendars": calendars,
        }

    def get_legacy_apple_recovered_password(
        self,
        *,
        original_encryption_key: str | None = None,
    ) -> str | None:
        payload = self.get_legacy_apple_recovery_hints()
        encrypted_secret = str(payload.get("credential_secret_encrypted") or "").strip()
        if not encrypted_secret:
            return None
        try:
            recovered_secret = self._fernet.decrypt(encrypted_secret.encode("utf-8")).decode(
                "utf-8"
            )
        except Exception:
            normalized_original_key = str(original_encryption_key or "").strip()
            if not normalized_original_key:
                return None
            try:
                recovered_secret = self._build_fernet_for_key(
                    normalized_original_key
                ).decrypt(encrypted_secret.encode("utf-8")).decode("utf-8")
            except Exception:
                return None
        normalized_secret = recovered_secret.strip()
        return normalized_secret or None

    def set_desired_alexa_settings(
        self,
        *,
        enable_alexa: bool,
        allowed_skill_ids: list[str],
    ) -> None:
        normalized_skill_ids = self._normalize_skill_ids(allowed_skill_ids)
        if not enable_alexa and not normalized_skill_ids:
            self.delete_value("desired_alexa_enable")
            self.delete_value("desired_alexa_allowed_skill_ids")
            return
        self.set_value(
            "desired_alexa_enable",
            "true" if enable_alexa else "false",
        )
        self.set_value(
            "desired_alexa_allowed_skill_ids",
            json.dumps(normalized_skill_ids),
        )

    def get_desired_alexa_settings(self) -> dict[str, object]:
        enable_value = self.get_value("desired_alexa_enable")
        raw_skill_ids = self.get_value("desired_alexa_allowed_skill_ids")
        if not enable_value and not raw_skill_ids:
            return {
                "enable_alexa": False,
                "allowed_skill_ids": [],
            }
        try:
            payload = json.loads(raw_skill_ids) if raw_skill_ids else []
        except json.JSONDecodeError:
            payload = []
        return {
            "enable_alexa": str(enable_value or "").strip().lower() == "true",
            "allowed_skill_ids": self._normalize_skill_ids(payload if isinstance(payload, list) else []),
        }

    def describe_desired_alexa_settings(self) -> dict[str, object]:
        values = self.get_desired_alexa_settings()
        saved = bool(values["allowed_skill_ids"])
        return {
            "enable_alexa": bool(values["enable_alexa"]),
            "allowed_skill_ids": list(values["allowed_skill_ids"]),
            "saved": saved,
            "source": "product_vault" if saved else "defaults",
        }

    def set_alexa_account_linking_settings(
        self,
        *,
        link_code: str,
        client_id: str = "calsync-alexa-household",
        regenerate_access_token: bool = False,
    ) -> None:
        normalized_link_code = re.sub(r"[^A-Za-z0-9]+", "", link_code or "").upper()
        normalized_client_id = str(client_id or "").strip() or "calsync-alexa-household"
        if len(normalized_link_code) < 6:
            raise ValueError("Alexa link code must be at least 6 letters or numbers.")

        existing = self.get_alexa_account_linking_settings()
        access_token = str(existing["access_token"] or "").strip()
        if regenerate_access_token or not access_token:
            access_token = secrets.token_urlsafe(32)

        self.set_value("alexa_account_linking_client_id", normalized_client_id)
        self.set_value("alexa_account_linking_link_code", normalized_link_code)
        self.set_value("alexa_account_linking_access_token", access_token)

    def get_alexa_account_linking_settings(self) -> dict[str, str | None]:
        return {
            "client_id": self.get_value("alexa_account_linking_client_id")
            or "calsync-alexa-household",
            "link_code": self.get_value("alexa_account_linking_link_code"),
            "access_token": self.get_value("alexa_account_linking_access_token"),
        }

    def describe_alexa_account_linking_settings(self) -> dict[str, object]:
        values = self.get_alexa_account_linking_settings()
        configured = bool(values["link_code"] and values["access_token"])
        return {
            "client_id": str(values["client_id"] or "calsync-alexa-household"),
            "configured": configured,
            "link_code_saved": bool(values["link_code"]),
            "access_token_ready": bool(values["access_token"]),
            "authorization_url": "/alexa/account-linking/authorize",
            "scopes": ["calendar:read", "calendar:write"],
            "source": "product_vault" if configured else "defaults",
        }

    def validate_alexa_account_linking_code(self, link_code: str) -> bool:
        stored = str(
            self.get_alexa_account_linking_settings()["link_code"] or ""
        ).strip()
        candidate = re.sub(r"[^A-Za-z0-9]+", "", link_code or "").upper()
        return bool(stored) and secrets.compare_digest(stored, candidate)

    def validate_alexa_account_linking_access_token(self, access_token: str) -> bool:
        stored = str(
            self.get_alexa_account_linking_settings()["access_token"] or ""
        ).strip()
        candidate = str(access_token or "").strip()
        return bool(stored) and bool(candidate) and secrets.compare_digest(stored, candidate)

    def set_public_booking_settings(
        self,
        *,
        page_title: str,
        page_description: str,
        duration_minutes: int,
        search_window_days: int,
        success_message: str,
        target_calendar_url: str,
        booking_weekdays: list[int] | None = None,
        day_start_time: str = "08:00",
        day_end_time: str = "18:00",
    ) -> None:
        payload = self._normalize_public_booking_payload(
            page_title=page_title,
            page_description=page_description,
            duration_minutes=duration_minutes,
            search_window_days=search_window_days,
            success_message=success_message,
            target_calendar_url=target_calendar_url,
            booking_weekdays=booking_weekdays,
            day_start_time=day_start_time,
            day_end_time=day_end_time,
        )
        self._store_legacy_public_booking_payload(payload)

    def upsert_public_booking_type(
        self,
        *,
        slug: str,
        page_title: str,
        page_description: str,
        duration_minutes: int,
        search_window_days: int,
        success_message: str,
        target_calendar_url: str,
        booking_weekdays: list[int] | None = None,
        day_start_time: str = "08:00",
        day_end_time: str = "18:00",
        set_as_default: bool = False,
    ) -> None:
        normalized_slug = self._normalize_booking_slug(slug)
        payload = self._normalize_public_booking_payload(
            page_title=page_title,
            page_description=page_description,
            duration_minutes=duration_minutes,
            search_window_days=search_window_days,
            success_message=success_message,
            target_calendar_url=target_calendar_url,
            booking_weekdays=booking_weekdays,
            day_start_time=day_start_time,
            day_end_time=day_end_time,
        )
        existing = self.get_public_booking_types()
        next_items: list[dict[str, object]] = []
        replaced = False
        for item in existing:
            if str(item.get("slug") or "") != normalized_slug:
                next_items.append(item)
                continue
            next_items.append(
                {
                    "slug": normalized_slug,
                    **payload,
                    "is_default": bool(item.get("is_default")),
                }
            )
            replaced = True
        if not replaced:
            next_items.append(
                {
                    "slug": normalized_slug,
                    **payload,
                    "is_default": False,
                }
            )
        if set_as_default or not any(bool(item.get("is_default")) for item in next_items):
            next_items = [
                {
                    **item,
                    "is_default": str(item.get("slug") or "") == normalized_slug,
                }
                for item in next_items
            ]
        normalized_items = self._coerce_public_booking_types(next_items)
        self.set_value("public_booking_types", json.dumps(normalized_items))
        default_item = next(
            (item for item in normalized_items if bool(item.get("is_default"))),
            None,
        )
        if default_item:
            self._store_legacy_public_booking_payload(default_item)

    def set_default_public_booking_type(self, slug: str) -> None:
        normalized_slug = self._normalize_booking_slug(slug)
        existing = self.get_public_booking_types()
        if not existing:
            raise ValueError("Public booking type was not found.")
        if not any(str(item.get("slug") or "") == normalized_slug for item in existing):
            raise ValueError("Public booking type was not found.")
        next_items = [
            {
                **item,
                "is_default": str(item.get("slug") or "") == normalized_slug,
            }
            for item in existing
        ]
        normalized_items = self._coerce_public_booking_types(next_items)
        self.set_value("public_booking_types", json.dumps(normalized_items))
        default_item = next(
            (item for item in normalized_items if bool(item.get("is_default"))),
            None,
        )
        if default_item:
            self._store_legacy_public_booking_payload(default_item)

    def delete_public_booking_type(self, slug: str) -> None:
        normalized_slug = self._normalize_booking_slug(slug)
        existing = self.get_public_booking_types()
        if not existing:
            raise ValueError("Public booking type was not found.")
        next_items = [
            item
            for item in existing
            if str(item.get("slug") or "") != normalized_slug
        ]
        if len(next_items) == len(existing):
            raise ValueError("Public booking type was not found.")
        if not next_items:
            self.delete_value("public_booking_types")
            return
        if not any(bool(item.get("is_default")) for item in next_items):
            next_items[0] = {
                **next_items[0],
                "is_default": True,
            }
        normalized_items = self._coerce_public_booking_types(next_items)
        self.set_value("public_booking_types", json.dumps(normalized_items))
        default_item = next(
            (item for item in normalized_items if bool(item.get("is_default"))),
            None,
        )
        if default_item:
            self._store_legacy_public_booking_payload(default_item)

    def get_public_booking_types(self) -> list[dict[str, object]]:
        raw = self.get_value("public_booking_types")
        if not raw:
            return []
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, list):
            return []
        return self._coerce_public_booking_types(payload)

    def get_public_booking_settings(self, *, slug: str | None = None) -> dict[str, object]:
        booking_types = self.get_public_booking_types()
        if booking_types:
            selected = None
            if slug:
                selected = next(
                    (
                        item
                        for item in booking_types
                        if str(item.get("slug") or "") == str(slug)
                    ),
                    None,
                )
            if selected is None:
                selected = next(
                    (item for item in booking_types if bool(item.get("is_default"))),
                    booking_types[0],
                )
            return {
                "slug": str(selected.get("slug") or ""),
                "page_title": str(selected.get("page_title") or ""),
                "page_description": str(selected.get("page_description") or ""),
                "duration_minutes": int(selected.get("duration_minutes") or 60),
                "search_window_days": int(selected.get("search_window_days") or 7),
                "success_message": str(selected.get("success_message") or ""),
                "target_calendar_url": str(selected.get("target_calendar_url") or ""),
                "booking_weekdays": self._coerce_booking_weekdays(
                    selected.get("booking_weekdays")
                ),
                "day_start_time": str(selected.get("day_start_time") or "08:00"),
                "day_end_time": str(selected.get("day_end_time") or "18:00"),
                "is_default": bool(selected.get("is_default")),
            }

        duration_value = self.get_value("public_booking_duration_minutes")
        search_window_value = self.get_value("public_booking_search_window_days")
        weekday_value = self.get_value("public_booking_weekdays")
        weekdays = self._coerce_booking_weekdays(
            json.loads(weekday_value) if weekday_value else None
        )
        day_start_time = self.get_value("public_booking_day_start_time") or "08:00"
        day_end_time = self.get_value("public_booking_day_end_time") or "18:00"
        return {
            "page_title": self.get_value("public_booking_page_title"),
            "page_description": self.get_value("public_booking_page_description"),
            "duration_minutes": int(duration_value) if duration_value else 60,
            "search_window_days": int(search_window_value) if search_window_value else 7,
            "success_message": self.get_value("public_booking_success_message"),
            "target_calendar_url": self.get_value("public_booking_target_calendar_url"),
            "booking_weekdays": weekdays,
            "day_start_time": day_start_time,
            "day_end_time": day_end_time,
        }

    def describe_public_booking_settings(self, *, slug: str | None = None) -> dict[str, object]:
        values = self.get_public_booking_settings(slug=slug)
        booking_weekdays = self._coerce_booking_weekdays(values["booking_weekdays"])
        weekday_options = self._weekday_options(booking_weekdays)
        booking_slug = str(values.get("slug") or "")
        return {
            "slug": booking_slug,
            "is_default": bool(values.get("is_default")),
            "public_url": self._public_booking_url(booking_slug),
            "page_title": str(values["page_title"] or "Book time with CalSync"),
            "page_description": str(
                values["page_description"]
                or "Claim an open slot from the live scheduling brain and let CalSync write the appointment directly into the connected calendar."
            ),
            "duration_minutes": int(values["duration_minutes"] or 60),
            "search_window_days": int(values["search_window_days"] or 7),
            "success_message": str(values["success_message"] or "Booking confirmed."),
            "target_calendar_url": str(values["target_calendar_url"] or ""),
            "booking_weekdays": booking_weekdays,
            "weekday_options": weekday_options,
            "weekday_summary": self._weekday_summary(booking_weekdays),
            "day_start_time": str(values["day_start_time"] or "08:00"),
            "day_end_time": str(values["day_end_time"] or "18:00"),
            "time_window_summary": self._time_window_summary(
                day_start_time=str(values["day_start_time"] or "08:00"),
                day_end_time=str(values["day_end_time"] or "18:00"),
            ),
            "source": "booking_type"
            if booking_slug
            else "product_vault"
            if any(
                [
                    values["page_title"],
                    values["page_description"],
                    values["success_message"],
                    values["target_calendar_url"],
                    values["booking_weekdays"] != list(range(7)),
                    str(values["day_start_time"] or "08:00") != "08:00",
                    str(values["day_end_time"] or "18:00") != "18:00",
                ]
            )
            else "defaults",
        }

    def describe_public_booking_types(self) -> list[dict[str, object]]:
        items = self.get_public_booking_types()
        sorted_items = sorted(
            items,
            key=lambda item: (
                0 if bool(item.get("is_default")) else 1,
                str(item.get("page_title") or str(item.get("slug") or "")).lower(),
            ),
        )
        return [
            {
                "slug": str(item.get("slug") or ""),
                "page_title": str(item.get("page_title") or ""),
                "page_description": str(item.get("page_description") or ""),
                "duration_minutes": int(item.get("duration_minutes") or 60),
                "public_url": self._public_booking_url(str(item.get("slug") or "")),
                "is_default": bool(item.get("is_default")),
                "weekday_summary": self._weekday_summary(
                    self._coerce_booking_weekdays(item.get("booking_weekdays"))
                ),
                "time_window_summary": self._time_window_summary(
                    day_start_time=str(item.get("day_start_time") or "08:00"),
                    day_end_time=str(item.get("day_end_time") or "18:00"),
                ),
            }
            for item in sorted_items
        ]

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

    def record_calendar_write_verification(
        self,
        *,
        target_value: str,
        provider_type: str,
        provider_label: str,
        account_label: str,
        calendar_name: str,
        passed: bool,
        message: str,
        checked_at: str,
    ) -> None:
        normalized_target_value = str(target_value or "").strip()
        normalized_provider_type = str(provider_type or "").strip()
        normalized_provider_label = str(provider_label or "").strip()
        normalized_account_label = str(account_label or "").strip()
        normalized_calendar_name = str(calendar_name or "").strip()
        normalized_message = str(message or "").strip()
        normalized_checked_at = str(checked_at or "").strip()
        if not normalized_target_value:
            raise ValueError("Writable calendar target value is required.")
        if not normalized_provider_type:
            raise ValueError("Provider type is required.")
        if not normalized_provider_label:
            raise ValueError("Provider label is required.")
        if not normalized_calendar_name:
            raise ValueError("Calendar name is required.")
        if not normalized_message:
            raise ValueError("Verification message is required.")
        if not normalized_checked_at:
            raise ValueError("Verification timestamp is required.")

        verification = {
            "target_value": normalized_target_value,
            "provider_type": normalized_provider_type,
            "provider_label": normalized_provider_label,
            "account_label": normalized_account_label,
            "calendar_name": normalized_calendar_name,
            "status": "passed" if passed else "failed",
            "message": normalized_message,
            "checked_at": normalized_checked_at,
        }
        remaining = [
            item
            for item in self.get_calendar_write_verifications()
            if str(item.get("target_value") or "") != normalized_target_value
        ]
        remaining.append(verification)
        self.set_value("calendar_write_verifications", json.dumps(remaining))

    def get_calendar_write_verifications(self) -> list[dict[str, str]]:
        raw = self.get_value("calendar_write_verifications")
        if not raw:
            return []
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return []
        return self._coerce_calendar_write_verifications(payload)

    def get_calendar_write_verification(
        self,
        target_value: str,
    ) -> dict[str, str] | None:
        normalized_target_value = str(target_value or "").strip()
        if not normalized_target_value:
            return None
        return next(
            (
                item
                for item in self.get_calendar_write_verifications()
                if str(item.get("target_value") or "") == normalized_target_value
            ),
            None,
        )

    def set_microsoft_oauth_settings(
        self,
        *,
        client_id: str,
        client_secret: str,
        preserve_existing_secret: bool = False,
    ) -> None:
        normalized_client_id = client_id.strip()
        normalized_client_secret = client_secret.strip()
        if not normalized_client_id:
            raise ValueError("Microsoft client ID is required.")

        existing = self.get_microsoft_oauth_settings()
        if not normalized_client_secret and not (
            preserve_existing_secret and existing["client_secret"]
        ):
            raise ValueError("Microsoft client secret is required.")

        self.set_value("microsoft_client_id", normalized_client_id)
        if normalized_client_secret:
            self.set_value("microsoft_client_secret", normalized_client_secret)

    def get_microsoft_oauth_settings(self) -> dict[str, str | None]:
        return {
            "client_id": self.get_value("microsoft_client_id"),
            "client_secret": self.get_value("microsoft_client_secret"),
        }

    def set_microsoft_account_settings(
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
            raise ValueError("Microsoft account label is required.")
        if not normalized_account_email:
            raise ValueError("Microsoft account email is required.")

        existing = self.get_microsoft_account_settings()
        if not normalized_refresh_token and not (
            preserve_existing_refresh_token and existing["refresh_token"]
        ):
            raise ValueError("Microsoft refresh token is required.")

        self.set_value("microsoft_account_label", normalized_account_label)
        self.set_value("microsoft_account_email", normalized_account_email)
        if normalized_refresh_token:
            self.set_value("microsoft_refresh_token", normalized_refresh_token)
        existing_calendars = self.get_microsoft_calendar_catalog()
        if existing_calendars:
            self.upsert_microsoft_account(
                account_label=normalized_account_label,
                account_email=normalized_account_email,
                refresh_token=normalized_refresh_token,
                calendars=existing_calendars,
                preserve_existing_refresh_token=preserve_existing_refresh_token,
            )

    def get_microsoft_account_settings(self) -> dict[str, str | None]:
        accounts = self.get_microsoft_accounts()
        if accounts:
            first = accounts[0]
            return {
                "account_label": str(first["account_label"] or ""),
                "account_email": str(first["account_email"] or ""),
                "refresh_token": str(first["refresh_token"] or ""),
            }
        return {
            "account_label": self.get_value("microsoft_account_label"),
            "account_email": self.get_value("microsoft_account_email"),
            "refresh_token": self.get_value("microsoft_refresh_token"),
        }

    def set_microsoft_calendar_catalog(self, calendars: list[dict[str, object]]) -> None:
        normalized = self._normalize_microsoft_calendars(calendars)
        self.set_value("microsoft_calendar_catalog", json.dumps(normalized))
        account = self.get_microsoft_account_settings()
        if account["account_email"]:
            self.upsert_microsoft_account(
                account_label=str(account["account_label"] or account["account_email"] or ""),
                account_email=str(account["account_email"] or ""),
                refresh_token=str(account["refresh_token"] or ""),
                calendars=normalized,
                preserve_existing_refresh_token=True,
            )

    def get_microsoft_calendar_catalog(self) -> list[dict[str, object]]:
        accounts = self.get_microsoft_accounts()
        if accounts:
            calendars = self._coerce_microsoft_calendars(accounts[0].get("calendars"))
            if calendars:
                return calendars
        raw = self.get_value("microsoft_calendar_catalog")
        if not raw:
            return []
        payload = json.loads(raw)
        return self._coerce_microsoft_calendars(payload)

    def get_microsoft_accounts(self) -> list[dict[str, object]]:
        raw = self.get_value("microsoft_accounts")
        if raw:
            payload = json.loads(raw)
            if isinstance(payload, list):
                accounts = self._coerce_microsoft_accounts(payload)
                if accounts:
                    return accounts

        legacy_account = {
            "account_label": self.get_value("microsoft_account_label"),
            "account_email": self.get_value("microsoft_account_email"),
            "refresh_token": self.get_value("microsoft_refresh_token"),
        }
        legacy_catalog = self._coerce_microsoft_calendars(
            json.loads(self.get_value("microsoft_calendar_catalog") or "[]")
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

    def upsert_microsoft_account(
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
            raise ValueError("Microsoft account label is required.")
        if not normalized_account_email:
            raise ValueError("Microsoft account email is required.")
        normalized_calendars = self._normalize_microsoft_calendars(calendars)

        accounts = self.get_microsoft_accounts()
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
            raise ValueError("Microsoft refresh token is required.")

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

        self.set_value("microsoft_accounts", json.dumps(next_accounts))
        first = next_accounts[0]
        self.set_value("microsoft_account_label", str(first["account_label"]))
        self.set_value("microsoft_account_email", str(first["account_email"]))
        self.set_value("microsoft_refresh_token", str(first["refresh_token"]))
        self.set_value("microsoft_calendar_catalog", json.dumps(first["calendars"]))

    def remove_microsoft_account(self, account_email: str) -> None:
        normalized_account_email = account_email.strip().lower()
        accounts = [
            item
            for item in self.get_microsoft_accounts()
            if str(item.get("account_email") or "").strip().lower() != normalized_account_email
        ]
        if accounts:
            self.set_value("microsoft_accounts", json.dumps(accounts))
            first = accounts[0]
            self.set_value("microsoft_account_label", str(first["account_label"]))
            self.set_value("microsoft_account_email", str(first["account_email"]))
            self.set_value("microsoft_refresh_token", str(first["refresh_token"]))
            self.set_value("microsoft_calendar_catalog", json.dumps(first["calendars"]))
            return
        self.delete_value("microsoft_accounts")
        self.clear_microsoft_account_settings()
        self.clear_microsoft_calendar_catalog()

    def _coerce_microsoft_accounts(self, payload: object) -> list[dict[str, object]]:
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
            calendars = self._coerce_microsoft_calendars(item.get("calendars"))
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

    def _coerce_microsoft_calendars(self, payload: object) -> list[dict[str, object]]:
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

    def _normalize_microsoft_calendars(
        self,
        calendars: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        if not calendars:
            raise ValueError("At least one Microsoft calendar is required.")

        normalized: list[dict[str, object]] = []
        seen_ids: set[str] = set()
        default_index = None
        for index, item in enumerate(calendars):
            calendar_name = str(item.get("calendar_name") or "").strip()
            calendar_id = str(item.get("calendar_id") or "").strip()
            is_default = bool(item.get("is_default"))
            if not calendar_name:
                raise ValueError("Microsoft calendar name is required.")
            if not calendar_id:
                raise ValueError("Microsoft calendar ID is required.")
            if calendar_id in seen_ids:
                raise ValueError("Microsoft calendar IDs must be unique.")
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

    def describe_microsoft_oauth_settings(self) -> dict[str, object]:
        oauth = self.get_microsoft_oauth_settings()
        account = self.get_microsoft_account_settings()
        catalog = self.get_microsoft_calendar_catalog()
        accounts = self.get_microsoft_accounts()
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

    def set_microsoft_oauth_state(self, state: str) -> None:
        self.set_value("microsoft_oauth_state", state)

    def get_microsoft_oauth_state(self) -> str | None:
        return self.get_value("microsoft_oauth_state")

    def clear_microsoft_oauth_state(self) -> None:
        self.delete_value("microsoft_oauth_state")

    def clear_microsoft_account_settings(self) -> None:
        self.delete_value("microsoft_account_label")
        self.delete_value("microsoft_account_email")
        self.delete_value("microsoft_refresh_token")
        self.delete_value("microsoft_accounts")

    def clear_microsoft_calendar_catalog(self) -> None:
        self.delete_value("microsoft_calendar_catalog")

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

    def _coerce_calendar_write_verifications(
        self,
        payload: object,
    ) -> list[dict[str, str]]:
        if not isinstance(payload, list):
            return []
        results: list[dict[str, str]] = []
        seen_targets: set[str] = set()
        for item in payload:
            if not isinstance(item, dict):
                continue
            target_value = str(item.get("target_value") or "").strip()
            provider_type = str(item.get("provider_type") or "").strip()
            provider_label = str(item.get("provider_label") or "").strip()
            account_label = str(item.get("account_label") or "").strip()
            calendar_name = str(item.get("calendar_name") or "").strip()
            status = str(item.get("status") or "").strip()
            message = str(item.get("message") or "").strip()
            checked_at = str(item.get("checked_at") or "").strip()
            if not (
                target_value
                and provider_type
                and provider_label
                and calendar_name
                and status in {"passed", "failed"}
                and message
                and checked_at
            ):
                continue
            if target_value in seen_targets:
                continue
            seen_targets.add(target_value)
            results.append(
                {
                    "target_value": target_value,
                    "provider_type": provider_type,
                    "provider_label": provider_label,
                    "account_label": account_label,
                    "calendar_name": calendar_name,
                    "status": status,
                    "message": message,
                    "checked_at": checked_at,
                }
            )
        return results

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

    def _normalize_public_booking_payload(
        self,
        *,
        page_title: str,
        page_description: str,
        duration_minutes: int,
        search_window_days: int,
        success_message: str,
        target_calendar_url: str,
        booking_weekdays: list[int] | None,
        day_start_time: str,
        day_end_time: str,
    ) -> dict[str, object]:
        normalized_title = page_title.strip()
        normalized_description = page_description.strip()
        normalized_success = success_message.strip()
        normalized_target = target_calendar_url.strip()
        normalized_weekdays = self._normalize_booking_weekdays(booking_weekdays)
        normalized_day_start_time = self._normalize_time_value(
            day_start_time,
            field_label="Public booking day start time",
        )
        normalized_day_end_time = self._normalize_time_value(
            day_end_time,
            field_label="Public booking day end time",
        )
        if not normalized_title:
            raise ValueError("Public booking title is required.")
        if not normalized_description:
            raise ValueError("Public booking description is required.")
        if not normalized_success:
            raise ValueError("Public booking success message is required.")
        if duration_minutes < 15:
            raise ValueError("Public booking duration must be at least 15 minutes.")
        if duration_minutes % 15 != 0:
            raise ValueError("Public booking duration must use 15-minute increments.")
        if search_window_days < 7:
            raise ValueError("Public booking search window must be at least 7 days.")
        if normalized_day_end_time <= normalized_day_start_time:
            raise ValueError(
                "Public booking day end time must be after the day start time."
            )
        return {
            "page_title": normalized_title,
            "page_description": normalized_description,
            "duration_minutes": int(duration_minutes),
            "search_window_days": int(search_window_days),
            "success_message": normalized_success,
            "target_calendar_url": normalized_target,
            "booking_weekdays": normalized_weekdays,
            "day_start_time": normalized_day_start_time,
            "day_end_time": normalized_day_end_time,
        }

    def _store_legacy_public_booking_payload(self, payload: dict[str, object]) -> None:
        self.set_value("public_booking_page_title", str(payload["page_title"]))
        self.set_value("public_booking_page_description", str(payload["page_description"]))
        self.set_value("public_booking_duration_minutes", str(payload["duration_minutes"]))
        self.set_value(
            "public_booking_search_window_days",
            str(payload["search_window_days"]),
        )
        self.set_value("public_booking_success_message", str(payload["success_message"]))
        self.set_value(
            "public_booking_weekdays",
            json.dumps(list(payload["booking_weekdays"])),
        )
        self.set_value("public_booking_day_start_time", str(payload["day_start_time"]))
        self.set_value("public_booking_day_end_time", str(payload["day_end_time"]))
        normalized_target = str(payload["target_calendar_url"] or "").strip()
        if normalized_target:
            self.set_value("public_booking_target_calendar_url", normalized_target)
        else:
            self.delete_value("public_booking_target_calendar_url")

    def _public_booking_url(self, slug: str) -> str:
        normalized_slug = str(slug or "").strip()
        return f"/book/{normalized_slug}" if normalized_slug else "/book"

    def _normalize_booking_slug(self, slug: str) -> str:
        normalized = re.sub(r"[^a-z0-9-]+", "-", slug.strip().lower())
        normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
        if not normalized:
            raise ValueError("Public booking type slug is required.")
        return normalized

    @staticmethod
    def _normalize_skill_ids(values: list[object]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            if text in seen:
                continue
            seen.add(text)
            normalized.append(text)
        return normalized

    def _coerce_public_booking_types(self, payload: object) -> list[dict[str, object]]:
        if not isinstance(payload, list):
            return []
        items: list[dict[str, object]] = []
        seen_slugs: set[str] = set()
        for item in payload:
            if not isinstance(item, dict):
                continue
            slug = self._normalize_booking_slug(str(item.get("slug") or ""))
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            items.append(
                {
                    "slug": slug,
                    "page_title": str(item.get("page_title") or "").strip(),
                    "page_description": str(item.get("page_description") or "").strip(),
                    "duration_minutes": int(item.get("duration_minutes") or 60),
                    "search_window_days": int(item.get("search_window_days") or 7),
                    "success_message": str(item.get("success_message") or "").strip(),
                    "target_calendar_url": str(item.get("target_calendar_url") or "").strip(),
                    "booking_weekdays": self._coerce_booking_weekdays(
                        item.get("booking_weekdays")
                    ),
                    "day_start_time": self._normalize_time_value(
                        str(item.get("day_start_time") or "08:00"),
                        field_label="Public booking day start time",
                    ),
                    "day_end_time": self._normalize_time_value(
                        str(item.get("day_end_time") or "18:00"),
                        field_label="Public booking day end time",
                    ),
                    "is_default": bool(item.get("is_default")),
                }
            )
        if items and not any(bool(item["is_default"]) for item in items):
            items[0]["is_default"] = True
        return items

    def _coerce_booking_weekdays(self, payload: object) -> list[int]:
        if not isinstance(payload, list):
            return list(range(7))
        normalized: list[int] = []
        seen: set[int] = set()
        for item in payload:
            try:
                value = int(item)
            except (TypeError, ValueError):
                continue
            if value < 0 or value > 6 or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
        return normalized or list(range(7))

    def _normalize_booking_weekdays(self, payload: list[int] | None) -> list[int]:
        normalized = self._coerce_booking_weekdays(payload if payload is not None else list(range(7)))
        if not normalized:
            raise ValueError("Choose at least one public booking weekday.")
        return normalized

    def _normalize_time_value(self, value: str, *, field_label: str) -> str:
        normalized = value.strip()
        try:
            parsed = datetime.strptime(normalized, "%H:%M")
        except ValueError as exc:
            raise ValueError(f"{field_label} must use HH:MM format.") from exc
        return parsed.strftime("%H:%M")

    def _weekday_options(self, selected_weekdays: list[int]) -> list[dict[str, object]]:
        labels = [
            ("Mon", "Monday"),
            ("Tue", "Tuesday"),
            ("Wed", "Wednesday"),
            ("Thu", "Thursday"),
            ("Fri", "Friday"),
            ("Sat", "Saturday"),
            ("Sun", "Sunday"),
        ]
        return [
            {
                "value": index,
                "short_label": short_label,
                "label": label,
                "is_selected": index in selected_weekdays,
            }
            for index, (short_label, label) in enumerate(labels)
        ]

    def _weekday_summary(self, selected_weekdays: list[int]) -> str:
        if selected_weekdays == [0, 1, 2, 3, 4, 5, 6]:
            return "Every day"
        if selected_weekdays == [0, 1, 2, 3, 4]:
            return "Monday to Friday"
        labels = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        return ", ".join(labels[index] for index in selected_weekdays)

    def _time_window_summary(self, *, day_start_time: str, day_end_time: str) -> str:
        start = datetime.strptime(day_start_time, "%H:%M")
        end = datetime.strptime(day_end_time, "%H:%M")
        return (
            f"{start.strftime('%I:%M %p').lstrip('0')} to "
            f"{end.strftime('%I:%M %p').lstrip('0')}"
        )

    def describe_cloudflare_worker_credentials(self) -> dict[str, object]:
        values = self.get_cloudflare_worker_credentials()
        return {
            "account_id": values["account_id"] or "",
            "api_token_saved": bool(values["api_token"]),
            "source": "product_vault"
            if values["account_id"] or values["api_token"]
            else "missing",
        }

    def _read_all_settings_plaintext(self) -> dict[str, str]:
        with self.session_factory() as session:
            self._ensure_table(session)
            records = session.query(OperatorSetting).all()
            return {
                record.key: self._fernet.decrypt(
                    record.value_encrypted.encode("utf-8")
                ).decode("utf-8")
                for record in records
            }

    @staticmethod
    def _ensure_table(session) -> None:
        OperatorSetting.__table__.create(bind=session.get_bind(), checkfirst=True)
