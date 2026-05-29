from __future__ import annotations

import httpx
import pytest

from calsync.config import Settings
from calsync.services.cloudflare_worker_config import CloudflareWorkerConfigService
from calsync.services.operator_settings import OperatorSettingsService


class _FakeResponse:
    def __init__(self, *, status_code: int, payload: dict[str, object]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, object]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "request failed",
                request=httpx.Request("GET", "https://api.cloudflare.com"),
                response=httpx.Response(self.status_code),
            )


def _settings() -> Settings:
    return Settings.model_construct(
        app_host="0.0.0.0",
        app_port=3080,
        database_url="sqlite+pysqlite:///:memory:",
        default_timezone="America/Anchorage",
        apple_account_label="Family",
        apple_username="family@example.com",
        apple_app_specific_password="secret",
        apple_primary_calendar_url="https://caldav.icloud.com/calendar/",
        apple_primary_calendar_name="Family",
        cloudflare_account_id="acct-123",
        cloudflare_api_token="token-123",
        cloudflare_token_kv_namespace_id="kv-123",
        channel_token_runtime_path=".runtime/channel-tokens.json",
        edge_base_url="https://edge-calsync.neonbutterfly.net",
        cloudflare_edge_worker_name="edge-calsync",
    )


def test_reads_edge_alexa_settings_from_cloudflare(monkeypatch) -> None:
    service = CloudflareWorkerConfigService(settings=_settings())

    def fake_get(url: str, *, headers: dict[str, str], timeout: float):
        assert url.endswith("/accounts/acct-123/workers/scripts/edge-calsync/settings")
        assert headers["Authorization"] == "Bearer token-123"
        assert timeout == 10.0
        return _FakeResponse(
            status_code=200,
            payload={
                "result": {
                    "bindings": [
                        {"type": "plain_text", "name": "ENABLE_ALEXA", "text": "false"},
                        {
                            "type": "plain_text",
                            "name": "ALEXA_ALLOWED_SKILL_IDS",
                            "text": "amzn1.ask.skill.one, amzn1.ask.skill.two",
                        },
                    ]
                }
            },
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    result = service.get_alexa_settings()

    assert result["worker_name"] == "edge-calsync"
    assert result["enable_alexa"] is False
    assert result["allowed_skill_ids"] == [
        "amzn1.ask.skill.one",
        "amzn1.ask.skill.two",
    ]
    assert result["manageable"] is True


def test_updates_edge_alexa_settings_and_preserves_other_bindings(monkeypatch) -> None:
    service = CloudflareWorkerConfigService(settings=_settings())
    calls: list[tuple[str, dict[str, str], dict[str, object] | None]] = []

    def fake_get(url: str, *, headers: dict[str, str], timeout: float):
        calls.append(("GET", headers, None))
        return _FakeResponse(
            status_code=200,
            payload={
                "result": {
                    "bindings": [
                        {"type": "plain_text", "name": "ENABLE_CHATGPT", "text": "true"},
                        {"type": "plain_text", "name": "ENABLE_ALEXA", "text": "false"},
                        {"type": "kv_namespace", "name": "TOKEN_HASHES", "namespace_id": "kv-123"},
                    ],
                    "compatibility_date": "2026-05-28",
                    "compatibility_flags": ["nodejs_compat"],
                    "observability": {"enabled": True, "head_sampling_rate": 1},
                }
            },
        )

    def fake_patch(url: str, *, headers: dict[str, str], files: dict[str, tuple[None, str, str]], timeout: float):
        body = files["settings"][1]
        calls.append(("PATCH", headers, {"body": body}))
        return _FakeResponse(status_code=200, payload={"result": {"ok": True}})

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "patch", fake_patch)

    service.update_alexa_settings(
        enable_alexa=True,
        allowed_skill_ids=["amzn1.ask.skill.real"],
    )

    assert calls[0][0] == "GET"
    assert calls[1][0] == "PATCH"
    payload_text = calls[1][2]["body"]  # type: ignore[index]
    assert '"name": "ENABLE_CHATGPT"' in payload_text
    assert '"name": "ENABLE_ALEXA"' in payload_text
    assert '"text": "true"' in payload_text
    assert '"name": "ALEXA_ALLOWED_SKILL_IDS"' in payload_text
    assert '"text": "amzn1.ask.skill.real"' in payload_text
    assert '"name": "TOKEN_HASHES"' in payload_text
    assert '"compatibility_date": "2026-05-28"' in payload_text


def test_reports_unmanageable_when_cloudflare_worker_config_is_missing() -> None:
    settings = Settings.model_construct(
        app_host="0.0.0.0",
        app_port=3080,
        database_url="sqlite+pysqlite:///:memory:",
        default_timezone="America/Anchorage",
        apple_account_label="Family",
        apple_username="family@example.com",
        apple_app_specific_password="secret",
        apple_primary_calendar_url="https://caldav.icloud.com/calendar/",
        apple_primary_calendar_name="Family",
        cloudflare_account_id=None,
        cloudflare_api_token=None,
        cloudflare_token_kv_namespace_id="kv-123",
        channel_token_runtime_path=".runtime/channel-tokens.json",
        edge_base_url="https://edge-calsync.neonbutterfly.net",
        cloudflare_edge_worker_name="edge-calsync",
    )
    service = CloudflareWorkerConfigService(settings=settings)

    result = service.get_alexa_settings()

    assert result["manageable"] is False
    assert "Cloudflare worker management is not configured" in result["message"]


def test_surfaces_permission_error_from_cloudflare(monkeypatch) -> None:
    service = CloudflareWorkerConfigService(settings=_settings())

    def fake_get(url: str, *, headers: dict[str, str], timeout: float):
        raise httpx.HTTPStatusError(
            "forbidden",
            request=httpx.Request("GET", url),
            response=httpx.Response(403),
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    result = service.get_alexa_settings()

    assert result["manageable"] is False
    assert "Workers Scripts" in result["message"]


def test_uses_product_vault_credentials_when_env_is_missing(monkeypatch) -> None:
    settings = Settings.model_construct(
        app_host="0.0.0.0",
        app_port=3080,
        database_url="sqlite+pysqlite:///:memory:",
        default_timezone="America/Anchorage",
        apple_account_label="Family",
        apple_username="family@example.com",
        apple_app_specific_password="secret",
        apple_primary_calendar_url="https://caldav.icloud.com/calendar/",
        apple_primary_calendar_name="Family",
        cloudflare_account_id=None,
        cloudflare_api_token=None,
        cloudflare_token_kv_namespace_id="kv-123",
        channel_token_runtime_path=".runtime/channel-tokens.json",
        edge_base_url="https://edge-calsync.neonbutterfly.net",
        cloudflare_edge_worker_name="edge-calsync",
        encryption_key="unit-test-encryption-key",
    )
    operator_settings = OperatorSettingsService(settings=settings)
    operator_settings.set_cloudflare_worker_credentials(
        account_id="acct-from-vault",
        api_token="token-from-vault",
    )
    service = CloudflareWorkerConfigService(
        settings=settings,
        operator_settings=operator_settings,
    )

    def fake_get(url: str, *, headers: dict[str, str], timeout: float):
        assert url.endswith(
            "/accounts/acct-from-vault/workers/scripts/edge-calsync/settings"
        )
        assert headers["Authorization"] == "Bearer token-from-vault"
        assert timeout == 10.0
        return _FakeResponse(status_code=200, payload={"result": {"bindings": []}})

    monkeypatch.setattr(httpx, "get", fake_get)

    result = service.get_alexa_settings()

    assert result["manageable"] is True
    assert result["credential_source"] == "product_vault"
