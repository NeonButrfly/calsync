from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from calsync.config import Settings, build_external_url
from calsync.db import get_db_session
from calsync.main import create_app


def test_settings_default_app_host(monkeypatch) -> None:
    monkeypatch.delenv("APP_HOST", raising=False)
    monkeypatch.delenv("APP_PORT", raising=False)
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)

    settings = Settings()

    assert settings.app_host == "0.0.0.0"


def test_settings_default_app_port(monkeypatch) -> None:
    monkeypatch.delenv("APP_HOST", raising=False)
    monkeypatch.delenv("APP_PORT", raising=False)
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)

    settings = Settings()

    assert settings.app_port == 3080


def test_settings_read_required_app_env_names(monkeypatch) -> None:
    monkeypatch.setenv("APP_HOST", "127.0.0.1")
    monkeypatch.setenv("APP_PORT", "4010")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://calendar.example.com")

    settings = Settings()

    assert settings.app_host == "127.0.0.1"
    assert settings.app_port == 4010
    assert str(settings.public_base_url) == "https://calendar.example.com/"


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


def test_create_app_accepts_explicit_settings() -> None:
    settings = Settings(app_host="127.0.0.1", app_port=4010)

    app = create_app(settings=settings)

    assert app.state.settings is settings


def test_get_db_session_uses_explicit_settings(tmp_path) -> None:
    database_path = tmp_path / "explicit.db"
    settings = Settings(database_url=f"sqlite+pysqlite:///{database_path.as_posix()}")

    session = next(get_db_session(settings))
    try:
        assert str(session.bind.url) == settings.database_url
    finally:
        session.close()
