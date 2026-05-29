from __future__ import annotations

from typing import Any

import httpx

from calsync.config import Settings, get_settings
from calsync.services.channel_tokens import ChannelTokenManager


_CHANNELS = ["chatgpt", "shortcuts", "alexa", "webhooks"]


class ReadinessService:
    def __init__(self, *, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.token_manager = ChannelTokenManager(
            runtime_path=self.settings.channel_token_runtime_path
        )

    def build(self) -> dict[str, Any]:
        channel_tokens = self.token_manager.channel_presence(_CHANNELS)
        edge = self._fetch_edge_status()
        origin = {
            "apple_ready": self._apple_ready(),
            "account_label": self.settings.apple_account_label,
            "calendar_name": self.settings.apple_primary_calendar_name,
            "default_timezone": self.settings.default_timezone,
        }
        return {
            "origin": origin,
            "channel_tokens": channel_tokens,
            "edge": edge,
            "next_action": self._next_action(origin, channel_tokens, edge),
        }

    def _fetch_edge_status(self) -> dict[str, Any]:
        base_url = self.settings.edge_base_url.strip()
        if not base_url:
            return {
                "reachable": False,
                "message": "Edge base URL is not configured.",
            }

        try:
            response = httpx.get(f"{base_url.rstrip('/')}/status", timeout=5.0)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return {
                "reachable": False,
                "message": "Edge status is unavailable right now.",
            }

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            return {
                "reachable": False,
                "message": "Edge status returned an unexpected payload.",
            }

        data["reachable"] = True
        return data

    def _next_action(
        self,
        origin: dict[str, Any],
        channel_tokens: dict[str, bool],
        edge: dict[str, Any],
    ) -> str:
        if not origin["apple_ready"]:
            return "Add the Apple calendar credentials so CalSync can read and write the family calendar."
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
        return "The current Apple-first scheduling stack is ready for app, edge, and Alexa verification."

    def _apple_ready(self) -> bool:
        return bool(
            self.settings.apple_username
            and self.settings.apple_app_specific_password
            and self.settings.apple_primary_calendar_url
        )
