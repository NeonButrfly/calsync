from __future__ import annotations

import json
from typing import Any

import httpx

from calsync.config import Settings, get_settings
from calsync.services.operator_settings import OperatorSettingsService


class CloudflareWorkerConfigService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        operator_settings: OperatorSettingsService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.operator_settings = operator_settings or OperatorSettingsService(
            settings=self.settings
        )

    def get_alexa_settings(self) -> dict[str, Any]:
        resolved = self._resolved_cloudflare_worker_credentials()
        if not self._is_configured(resolved):
            return {
                "worker_name": self.settings.cloudflare_edge_worker_name,
                "enable_alexa": False,
                "allowed_skill_ids": [],
                "manageable": False,
                "credential_source": resolved["source"],
                "message": "Cloudflare worker management is not configured for this deployment.",
            }

        try:
            settings_payload = self._get_worker_settings(resolved)
        except httpx.HTTPStatusError as exc:
            return {
                "worker_name": self.settings.cloudflare_edge_worker_name,
                "enable_alexa": False,
                "allowed_skill_ids": [],
                "manageable": False,
                "credential_source": resolved["source"],
                "message": self._http_error_message(exc),
            }
        except (httpx.HTTPError, ValueError):
            return {
                "worker_name": self.settings.cloudflare_edge_worker_name,
                "enable_alexa": False,
                "allowed_skill_ids": [],
                "manageable": False,
                "credential_source": resolved["source"],
                "message": "Cloudflare worker settings are unavailable right now.",
            }

        bindings = settings_payload.get("bindings", [])
        enable_alexa = self._binding_text(bindings, "ENABLE_ALEXA") == "true"
        allowed_skill_ids = self._split_skill_ids(
            self._binding_text(bindings, "ALEXA_ALLOWED_SKILL_IDS") or ""
        )
        return {
            "worker_name": self.settings.cloudflare_edge_worker_name,
            "enable_alexa": enable_alexa,
            "allowed_skill_ids": allowed_skill_ids,
            "manageable": True,
            "credential_source": resolved["source"],
            "message": "Ready to configure the edge Worker from the product.",
        }

    def update_alexa_settings(
        self,
        *,
        enable_alexa: bool,
        allowed_skill_ids: list[str],
    ) -> dict[str, Any]:
        resolved = self._resolved_cloudflare_worker_credentials()
        if not self._is_configured(resolved):
            raise ValueError(
                "Cloudflare worker management is not configured for this deployment."
            )

        try:
            settings_payload = self._get_worker_settings(resolved)
            bindings = list(settings_payload.get("bindings", []))
            bindings = self._upsert_plain_text_binding(
                bindings,
                "ENABLE_ALEXA",
                "true" if enable_alexa else "false",
            )
            bindings = self._upsert_plain_text_binding(
                bindings,
                "ALEXA_ALLOWED_SKILL_IDS",
                ",".join(allowed_skill_ids),
            )

            outgoing: dict[str, Any] = {
                key: settings_payload[key]
                for key in (
                    "annotations",
                    "compatibility_date",
                    "compatibility_flags",
                    "limits",
                    "logpush",
                    "observability",
                    "placement",
                    "tags",
                    "tail_consumers",
                    "usage_model",
                )
                if key in settings_payload
            }
            outgoing["bindings"] = bindings

            response = httpx.patch(
                self._settings_url(resolved),
                headers=self._headers(resolved),
                files={
                    "settings": (
                        None,
                        json.dumps({"settings": outgoing}),
                        "application/json",
                    )
                },
                timeout=20.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ValueError(self._http_error_message(exc)) from exc
        except httpx.HTTPError as exc:
            raise ValueError(
                "Cloudflare worker settings could not be updated right now."
            ) from exc

        return self.get_alexa_settings()

    def _get_worker_settings(self, resolved: dict[str, str]) -> dict[str, Any]:
        response = httpx.get(
            self._settings_url(resolved),
            headers=self._headers(resolved),
            timeout=10.0,
        )
        response.raise_for_status()
        payload = response.json()
        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict):
            raise ValueError("Cloudflare returned an unexpected worker settings payload.")
        return result

    def _settings_url(self, resolved: dict[str, str]) -> str:
        return (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{resolved['account_id']}/workers/scripts/"
            f"{self.settings.cloudflare_edge_worker_name}/settings"
        )

    def _headers(self, resolved: dict[str, str]) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {resolved['api_token']}",
        }

    def _is_configured(self, resolved: dict[str, str]) -> bool:
        return bool(
            resolved["account_id"]
            and resolved["api_token"]
            and self.settings.cloudflare_edge_worker_name
        )

    def _resolved_cloudflare_worker_credentials(self) -> dict[str, str]:
        if self.settings.cloudflare_account_id and self.settings.cloudflare_api_token:
            return {
                "account_id": self.settings.cloudflare_account_id,
                "api_token": self.settings.cloudflare_api_token,
                "source": "deployment_env",
            }

        stored = self.operator_settings.get_cloudflare_worker_credentials()
        if stored["account_id"] and stored["api_token"]:
            return {
                "account_id": stored["account_id"],
                "api_token": stored["api_token"],
                "source": "product_vault",
            }

        return {
            "account_id": "",
            "api_token": "",
            "source": "missing",
        }

    @staticmethod
    def _binding_text(bindings: list[dict[str, Any]], name: str) -> str | None:
        for binding in bindings:
            if binding.get("name") == name and binding.get("type") == "plain_text":
                text = binding.get("text")
                return str(text) if text is not None else ""
        return None

    @staticmethod
    def _split_skill_ids(raw_value: str) -> list[str]:
        return [value.strip() for value in raw_value.split(",") if value.strip()]

    @staticmethod
    def _upsert_plain_text_binding(
        bindings: list[dict[str, Any]],
        name: str,
        text: str,
    ) -> list[dict[str, Any]]:
        updated = False
        next_bindings: list[dict[str, Any]] = []
        for binding in bindings:
            if binding.get("name") == name:
                next_bindings.append(
                    {
                        "type": "plain_text",
                        "name": name,
                        "text": text,
                    }
                )
                updated = True
            else:
                next_bindings.append(binding)
        if not updated:
            next_bindings.append(
                {
                    "type": "plain_text",
                    "name": name,
                    "text": text,
                }
            )
        return next_bindings

    @staticmethod
    def _http_error_message(exc: httpx.HTTPStatusError) -> str:
        if exc.response.status_code in {401, 403}:
            return "Cloudflare API token needs Workers Scripts permission to manage the edge Worker."
        return (
            f"Cloudflare worker settings request failed with "
            f"{exc.response.status_code}."
        )
