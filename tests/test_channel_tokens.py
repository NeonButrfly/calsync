from pathlib import Path

from calsync.services.channel_tokens import ChannelTokenManager, hash_token


def test_hash_token_is_stable_sha256_hex() -> None:
    digest = hash_token("secret-token")

    assert len(digest) == 64
    assert digest == hash_token("secret-token")


def test_manager_builds_cloudflare_kv_payload(tmp_path: Path) -> None:
    manager = ChannelTokenManager(runtime_path=tmp_path / "channel-tokens.json")
    token = manager.bootstrap_channel("chatgpt")

    payload = manager.build_cloudflare_kv_payload()

    assert payload["chatgpt"]["hash"] == hash_token(token)


def test_sync_hashes_to_cloudflare_writes_each_channel(
    monkeypatch,
    tmp_path: Path,
) -> None:
    manager = ChannelTokenManager(runtime_path=tmp_path / "channel-tokens.json")
    manager.bootstrap_channel("chatgpt")
    manager.bootstrap_channel("shortcuts")
    calls: list[tuple[str, dict[str, str], str, float]] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    def fake_put(
        url: str,
        *,
        headers: dict[str, str],
        content: str,
        timeout: float,
    ) -> FakeResponse:
        calls.append((url, headers, content, timeout))
        return FakeResponse()

    monkeypatch.setattr("calsync.services.channel_tokens.httpx.put", fake_put)

    manager.sync_hashes_to_cloudflare(
        account_id="acct-123",
        api_token="api-secret",
        namespace_id="ns-456",
    )

    assert len(calls) == 2
    assert {
        url
        for url, _, _, _ in calls
    } == {
        "https://api.cloudflare.com/client/v4/accounts/acct-123/storage/kv/namespaces/ns-456/values/chatgpt",
        "https://api.cloudflare.com/client/v4/accounts/acct-123/storage/kv/namespaces/ns-456/values/shortcuts",
    }
    assert all(
        headers["Authorization"] == "Bearer api-secret" and timeout == 30
        for _, headers, _, timeout in calls
    )
