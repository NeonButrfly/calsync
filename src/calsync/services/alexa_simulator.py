from __future__ import annotations

from typing import Any

import httpx

from calsync.config import Settings, get_settings
from calsync.services.channel_tokens import ChannelTokenManager


class AlexaSimulatorService:
    def __init__(self, *, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.token_manager = ChannelTokenManager(
            runtime_path=self.settings.channel_token_runtime_path
        )

    def simulate(
        self,
        *,
        request_type: str,
        intent_name: str | None,
        slots: dict[str, str],
    ) -> dict[str, Any]:
        edge_base_url = self.settings.edge_base_url.strip()
        if not edge_base_url:
            raise ValueError("Edge base URL is not configured.")

        token = self.token_manager.show_channel("chatgpt")
        payload: dict[str, Any] = {
            "request_type": request_type,
            "slots": {
                key: value
                for key, value in slots.items()
                if isinstance(value, str) and value.strip()
            },
        }
        if intent_name:
            payload["intent_name"] = intent_name

        response = httpx.post(
            f"{edge_base_url.rstrip('/')}/alexa/simulate",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            json=payload,
            timeout=10.0,
        )
        body = response.json()
        if not response.is_success:
            message = body.get("message") if isinstance(body, dict) else None
            raise ValueError(message or "Alexa simulation failed.")

        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            raise ValueError("Alexa simulation returned an unexpected payload.")
        return {
            "ok": bool(body.get("ok", False)) if isinstance(body, dict) else False,
            "speech": data.get("speech") or "",
            "card_type": data.get("card_type") or "",
            "should_end_session": data.get("should_end_session"),
            "raw_response": data.get("raw_response") or {},
        }
