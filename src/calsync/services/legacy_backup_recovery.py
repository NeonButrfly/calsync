from __future__ import annotations

import json
import re
from io import BytesIO
from zipfile import ZipFile


class LegacyBackupRecoveryService:
    def extract_apple_hints(
        self,
        *,
        backup_bytes: bytes,
        filename: str,
    ) -> dict[str, object]:
        sql_text = self._extract_sql_text(backup_bytes=backup_bytes, filename=filename)
        accounts = self._parse_copy_rows(sql_text, "provider_accounts")
        calendars = self._parse_copy_rows(sql_text, "provider_calendars")

        apple_accounts = [
            row for row in accounts if str(row.get("provider_type") or "") == "icloud_caldav"
        ]
        if not apple_accounts:
            raise ValueError("Legacy backup does not contain any Apple CalDAV provider accounts.")

        primary_account = apple_accounts[0]
        account_pk = str(primary_account.get("id") or "")
        provider_metadata = self._load_json(primary_account.get("provider_metadata"))
        apple_calendars = [
            row
            for row in calendars
            if str(row.get("provider_account_pk") or "") == account_pk
        ]
        if not apple_calendars:
            raise ValueError("Legacy backup does not contain any Apple calendars for the recovered account.")

        normalized_calendars = []
        for row in apple_calendars:
            role = str(row.get("calendar_role") or "")
            enabled = str(row.get("enabled") or "").lower() == "t"
            normalized_calendars.append(
                {
                    "calendar_name": str(row.get("name") or "Unnamed Apple calendar"),
                    "calendar_url": str(row.get("provider_calendar_id") or ""),
                    "calendar_role": role,
                    "enabled": enabled,
                    "is_writable_hint": enabled or role == "writable_booking_target",
                }
            )

        normalized_calendars.sort(
            key=lambda item: (
                0
                if str(item["calendar_role"] or "") == "writable_booking_target"
                else 1
                if bool(item["enabled"])
                else 2,
                str(item["calendar_name"]).lower(),
            )
        )
        recommended = normalized_calendars[0]
        account_username = str(primary_account.get("provider_account_id") or "").strip()
        account_label = str(primary_account.get("display_name") or account_username).strip()
        return {
            "source_filename": filename,
            "account_label": account_label,
            "account_username": account_username,
            "principal_url": str(provider_metadata.get("principal_url") or ""),
            "calendar_home_url": str(provider_metadata.get("calendar_home_url") or ""),
            "credential_secret_encrypted": str(
                primary_account.get("credential_secret_encrypted") or ""
            ).strip(),
            "recommended_calendar_name": str(recommended["calendar_name"]),
            "recommended_calendar_url": str(recommended["calendar_url"]),
            "calendar_count": len(normalized_calendars),
            "calendars": normalized_calendars,
        }

    def _extract_sql_text(self, *, backup_bytes: bytes, filename: str) -> str:
        normalized_filename = filename.lower().strip()
        if normalized_filename.endswith(".zip"):
            with ZipFile(BytesIO(backup_bytes)) as archive:
                sql_members = [
                    name for name in archive.namelist() if name.lower().endswith(".sql")
                ]
                if not sql_members:
                    raise ValueError("Legacy backup zip does not contain a SQL dump.")
                return archive.read(sql_members[0]).decode("utf-8", errors="ignore")
        return backup_bytes.decode("utf-8", errors="ignore")

    def _parse_copy_rows(self, sql_text: str, table_name: str) -> list[dict[str, object]]:
        pattern = (
            rf"COPY public\.{table_name} \((?P<columns>.*?)\) FROM stdin;\n"
            rf"(?P<body>.*?)\n\\\."
        )
        match = re.search(pattern, sql_text, re.S)
        if not match:
            return []

        columns = [item.strip() for item in match.group("columns").split(",")]
        rows: list[dict[str, object]] = []
        for raw_line in match.group("body").splitlines():
            if not raw_line.strip():
                continue
            values = raw_line.split("\t")
            if len(values) != len(columns):
                continue
            row = {
                column: None if value == r"\N" else value
                for column, value in zip(columns, values, strict=True)
            }
            rows.append(row)
        return rows

    @staticmethod
    def _load_json(raw_value: object) -> dict[str, object]:
        if not isinstance(raw_value, str) or not raw_value.strip():
            return {}
        try:
            payload = json.loads(raw_value)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}
