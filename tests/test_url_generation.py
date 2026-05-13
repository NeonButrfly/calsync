from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from calsync.config import Settings, build_external_url


def test_settings_default_bind_host(monkeypatch) -> None:
    monkeypatch.delenv("CALSYNC_BIND_HOST", raising=False)
    monkeypatch.delenv("CALSYNC_BIND_PORT", raising=False)
    monkeypatch.delenv("CALSYNC_PUBLIC_BASE_URL", raising=False)

    settings = Settings()

    assert settings.bind_host == "0.0.0.0"


def test_settings_default_bind_port(monkeypatch) -> None:
    monkeypatch.delenv("CALSYNC_BIND_HOST", raising=False)
    monkeypatch.delenv("CALSYNC_BIND_PORT", raising=False)
    monkeypatch.delenv("CALSYNC_PUBLIC_BASE_URL", raising=False)

    settings = Settings()

    assert settings.bind_port == 3080


def test_public_base_url_overrides_request_origin() -> None:
    settings = Settings(public_base_url="https://calendar.example.com/base")
    app = FastAPI()

    @app.get("/external-url")
    def external_url(request: Request) -> dict[str, str]:
        return {
            "url": build_external_url(
                request,
                "/healthz",
                settings=settings,
            )
        }

    client = TestClient(app, base_url="http://internal.service.local:9999")

    response = client.get("/external-url")

    assert response.status_code == 200
    assert response.json() == {
        "url": "https://calendar.example.com/base/healthz"
    }
