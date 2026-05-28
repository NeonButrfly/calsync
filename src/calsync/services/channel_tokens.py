import hashlib
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path

import httpx

from calsync.config import get_settings


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class ChannelTokenManager:
    def __init__(self, *, runtime_path: str | Path | None = None) -> None:
        configured_path = runtime_path or get_settings().channel_token_runtime_path
        self.runtime_path = Path(configured_path)

    def bootstrap_channel(self, channel: str, *, replace: bool = False) -> str:
        normalized_channel = self._normalize_channel(channel)
        data = self._load()
        existing = data.get(normalized_channel)
        if existing and not replace:
            return existing["token"]

        token = secrets.token_urlsafe(32)
        data[normalized_channel] = {
            "token": token,
            "hash": hash_token(token),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        self._save(data)
        return token

    def rotate_channel(self, channel: str) -> str:
        return self.bootstrap_channel(channel, replace=True)

    def show_channel(self, channel: str) -> str:
        normalized_channel = self._normalize_channel(channel)
        data = self._load()
        record = data.get(normalized_channel)
        if record is None:
            raise KeyError(f"Channel '{normalized_channel}' is not bootstrapped.")
        return record["token"]

    def build_cloudflare_kv_payload(self) -> dict[str, dict[str, str]]:
        data = self._load()
        return {
            channel: {"hash": value["hash"]}
            for channel, value in data.items()
        }

    def sync_hashes_to_cloudflare(
        self,
        *,
        account_id: str,
        api_token: str,
        namespace_id: str,
    ) -> None:
        payload = self.build_cloudflare_kv_payload()
        headers = {"Authorization": f"Bearer {api_token}"}
        for channel, value in payload.items():
            httpx.put(
                f"https://api.cloudflare.com/client/v4/accounts/{account_id}/storage/kv/namespaces/{namespace_id}/values/{channel}",
                headers=headers,
                content=value["hash"],
                timeout=30,
            ).raise_for_status()

    def _load(self) -> dict[str, dict[str, str]]:
        if not self.runtime_path.exists():
            return {}

        data = json.loads(self.runtime_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Channel token runtime file must contain an object.")
        return {
            str(channel): {
                "token": str(value["token"]),
                "hash": str(value["hash"]),
                "updated_at": str(value.get("updated_at", "")),
            }
            for channel, value in data.items()
            if isinstance(value, dict)
            and "token" in value
            and "hash" in value
        }

    def _save(self, data: dict[str, dict[str, str]]) -> None:
        self.runtime_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime_path.write_text(
            json.dumps(data, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    @staticmethod
    def _normalize_channel(channel: str) -> str:
        normalized_channel = channel.strip().lower()
        if not normalized_channel:
            raise ValueError("Channel name cannot be empty.")
        return normalized_channel
