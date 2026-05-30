from __future__ import annotations

from typing import Any

import httpx

from calsync.config import Settings, get_settings
from calsync.services.apple_runtime_config import AppleRuntimeConfigService
from calsync.services.channel_tokens import ChannelTokenManager
from calsync.services.google_runtime_config import GoogleRuntimeConfigService
from calsync.services.microsoft_runtime_config import MicrosoftRuntimeConfigService


_CHANNELS = ["chatgpt", "shortcuts", "alexa", "webhooks"]


class ReadinessService:
    def __init__(self, *, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.token_manager = ChannelTokenManager(
            runtime_path=self.settings.channel_token_runtime_path
        )
        self.apple_runtime_config = AppleRuntimeConfigService(settings=self.settings)
        self.google_runtime_config = GoogleRuntimeConfigService(settings=self.settings)
        self.microsoft_runtime_config = MicrosoftRuntimeConfigService(settings=self.settings)

    def build(self) -> dict[str, Any]:
        channel_tokens = self.token_manager.channel_presence(_CHANNELS)
        edge = self._fetch_edge_status()
        apple = self.apple_runtime_config.resolve()
        google = self.google_runtime_config.resolve()
        microsoft = self.microsoft_runtime_config.resolve()
        desired_alexa = self._load_desired_alexa_settings()
        primary_account_label = (
            apple["account_label"]
            if apple["ready"]
            else google["account_label"]
            if google["ready"]
            else microsoft["account_label"]
        )
        primary_calendar_name = (
            apple["primary_calendar_name"]
            if apple["ready"]
            else google["primary_calendar_name"]
            if google["ready"]
            else microsoft["primary_calendar_name"]
        )
        origin = {
            "apple_ready": bool(apple["ready"]),
            "google_ready": bool(google["ready"]),
            "microsoft_ready": bool(microsoft["ready"]),
            "any_calendar_ready": bool(apple["ready"] or google["ready"] or microsoft["ready"]),
            "account_label": primary_account_label,
            "calendar_name": primary_calendar_name,
            "default_timezone": self.settings.default_timezone,
        }
        return {
            "origin": origin,
            "channel_tokens": channel_tokens,
            "edge": edge,
            "desired_alexa": desired_alexa,
            "next_action": self._next_action(
                origin,
                channel_tokens,
                edge,
                desired_alexa,
            ),
        }

    def _load_desired_alexa_settings(self) -> dict[str, Any]:
        try:
            from calsync.services.operator_settings import OperatorSettingsService

            return OperatorSettingsService(
                settings=self.settings
            ).describe_desired_alexa_settings()
        except Exception:
            return {
                "enable_alexa": False,
                "allowed_skill_ids": [],
                "saved": False,
                "source": "defaults",
            }

    def _fetch_edge_status(self) -> dict[str, Any]:
        default_status = {
            "reachable": False,
            "message": "Edge status is unavailable right now.",
            "alexa": {
                "enabled": False,
                "skill_ids_configured": False,
            },
        }
        base_url = self.settings.edge_base_url.strip()
        if not base_url:
            default_status["message"] = "Edge base URL is not configured."
            return default_status

        try:
            response = httpx.get(f"{base_url.rstrip('/')}/status", timeout=5.0)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return default_status

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            default_status["message"] = "Edge status returned an unexpected payload."
            return default_status

        data.setdefault("alexa", {})
        data["alexa"].setdefault("enabled", False)
        data["alexa"].setdefault("skill_ids_configured", False)
        data["reachable"] = True
        return data

    def _next_action(
        self,
        origin: dict[str, Any],
        channel_tokens: dict[str, bool],
        edge: dict[str, Any],
        desired_alexa: dict[str, Any],
    ) -> str:
        if not origin["any_calendar_ready"]:
            return "Add an Apple calendar or finish Google or Microsoft setup so CalSync can read and write a real connected calendar."
        desired_enabled = bool(desired_alexa.get("enable_alexa"))
        desired_skill_ids = [
            str(value).strip()
            for value in desired_alexa.get("allowed_skill_ids", [])
            if str(value).strip()
        ]
        live_enabled = bool(edge.get("alexa", {}).get("enabled", False))
        live_skill_ids_configured = bool(
            edge.get("alexa", {}).get("skill_ids_configured", False)
        )
        if desired_alexa.get("saved") and (
            not edge.get("reachable", False)
            or desired_enabled != live_enabled
            or bool(desired_skill_ids) != live_skill_ids_configured
        ):
            return "Desired Alexa settings are saved in CalSync and still need to be applied to the live edge Worker."
        if not channel_tokens.get("chatgpt", False):
            return "Bootstrap the ChatGPT channel token so the edge Worker can authenticate app requests."
        if not edge.get("reachable", False):
            return "Check the edge Worker deployment so channel and Alexa status can be verified live."
        if not edge.get("alexa", {}).get("enabled", False):
            return "Alexa still needs to be enabled on the edge Worker before real voice requests can flow."
        if not edge.get("alexa", {}).get("skill_ids_configured", False):
            return "Add the real Alexa skill ID to the edge Worker allowlist before turning voice access on."
        if not channel_tokens.get("alexa", False):
            return "Bootstrap the Alexa channel token on the origin so voice-origin calls can be authenticated."
        return "The current scheduling stack is ready for app, edge, and Alexa verification."
