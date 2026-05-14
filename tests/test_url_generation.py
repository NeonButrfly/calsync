from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import importlib

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from calsync.config import (
    Settings,
    build_external_url,
    build_google_callback_url,
    get_google_oauth_scopes,
    validate_google_callback_url,
)
from calsync.db import get_db_session
from calsync.main import create_app
from calsync.models import Base
from calsync.repos.state import set_app_state


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


def test_debug_external_url_uses_production_service_builder(
    monkeypatch,
    tmp_path: Path,
) -> None:
    app_settings = importlib.import_module("calsync.services.app_settings")

    def fake_build_external_url(
        request: Request,
        path: str,
        *,
        session: Session | None,
        settings: Settings,
    ) -> str:
        return "https://calendar.example.com/from-service/healthz"

    monkeypatch.setattr(
        app_settings,
        "build_external_url",
        fake_build_external_url,
        raising=False,
    )

    with _build_client_with_state(
        tmp_path,
        saved_public_base_url="https://calsync.neonbutterfly.net",
        base_url="http://192.168.50.232:3080",
    ) as client:
        response = client.get("/debug/external-url")

    assert response.json() == {
        "url": "https://calendar.example.com/from-service/healthz"
    }


def test_debug_google_callback_url_uses_production_service_builder(
    monkeypatch,
    tmp_path: Path,
) -> None:
    app_settings = importlib.import_module("calsync.services.app_settings")

    def fake_build_google_callback_url(
        request: Request,
        *,
        session: Session | None,
        settings: Settings,
    ) -> str:
        return "https://calendar.example.com/from-service/auth/google/callback"

    monkeypatch.setattr(
        app_settings,
        "build_google_callback_url",
        fake_build_google_callback_url,
        raising=False,
    )

    with _build_client_with_state(
        tmp_path,
        saved_public_base_url="https://calsync.neonbutterfly.net",
        base_url="http://192.168.50.232:3080",
    ) as client:
        response = client.get("/debug/google-callback-url")

    assert response.json() == {
        "url": "https://calendar.example.com/from-service/auth/google/callback"
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


def test_google_callback_url_uses_public_base_url_when_present() -> None:
    settings = Settings(
        public_base_url="https://calendar.example.com/base",
        google_oauth_redirect_path="/auth/google/callback",
    )
    app = FastAPI()

    @app.get("/callback-url")
    def callback_url(request: Request) -> dict[str, str]:
        return {"url": build_google_callback_url(request, settings=settings)}

    client = TestClient(app, base_url="http://internal.service.local:9999")

    response = client.get("/callback-url")

    assert response.status_code == 200
    assert response.json() == {
        "url": "https://calendar.example.com/base/auth/google/callback"
    }


def test_google_callback_url_uses_request_origin_when_public_base_url_is_unset() -> None:
    settings = Settings(google_oauth_redirect_path="/auth/google/callback")
    app = FastAPI()

    @app.get("/callback-url")
    def callback_url(request: Request) -> dict[str, str]:
        return {"url": build_google_callback_url(request, settings=settings)}

    client = TestClient(app, base_url="http://localhost:3080")

    response = client.get("/callback-url")

    assert response.status_code == 200
    assert response.json() == {"url": "http://localhost:3080/auth/google/callback"}


def test_google_callback_url_prefers_localhost_request_over_invalid_public_base_url() -> None:
    settings = Settings(
        public_base_url="http://192.168.50.232:3080",
        google_oauth_redirect_path="/auth/google/callback",
    )
    app = FastAPI()

    @app.get("/callback-url")
    def callback_url(request: Request) -> dict[str, str]:
        return {"url": build_google_callback_url(request, settings=settings)}

    client = TestClient(app, base_url="http://localhost:3080")

    response = client.get("/callback-url")

    assert response.status_code == 200
    assert response.json() == {"url": "http://localhost:3080/auth/google/callback"}


def test_saved_public_base_url_overrides_request_origin_when_present(tmp_path: Path) -> None:
    with _build_client_with_state(
        tmp_path,
        saved_public_base_url="https://calsync.neonbutterfly.net",
        base_url="http://192.168.50.232:3080",
    ) as client:
        response = client.get("/debug/external-url")

    assert response.json() == {
        "url": "https://calsync.neonbutterfly.net/healthz"
    }


def test_google_callback_prefers_saved_https_public_url_over_lan_origin(
    tmp_path: Path,
) -> None:
    with _build_client_with_state(
        tmp_path,
        saved_public_base_url="https://calsync.neonbutterfly.net",
        base_url="http://192.168.50.232:3080",
    ) as client:
        response = client.get("/debug/google-callback-url")

    assert response.json() == {
        "url": "https://calsync.neonbutterfly.net/auth/google/callback"
    }


def test_validate_google_callback_url_accepts_localhost_http() -> None:
    assert (
        validate_google_callback_url("http://localhost:3080/auth/google/callback")
        is None
    )


def test_validate_google_callback_url_accepts_https_hostname() -> None:
    assert (
        validate_google_callback_url(
            "https://calendar.example.com/auth/google/callback"
        )
        is None
    )


def test_validate_google_callback_url_rejects_raw_lan_ip() -> None:
    error = validate_google_callback_url(
        "http://192.168.50.232:3080/auth/google/callback"
    )

    assert error is not None
    assert "raw IP addresses" in error


def test_validate_google_callback_url_rejects_http_hostname() -> None:
    error = validate_google_callback_url(
        "http://calendar.example.com/auth/google/callback"
    )

    assert error is not None
    assert "HTTPS hostname" in error


def test_google_oauth_scopes_are_split_from_config_string() -> None:
    settings = Settings(google_oauth_scopes="openid,email, profile ")

    assert get_google_oauth_scopes(settings) == ("openid", "email", "profile")


@contextmanager
def _build_client_with_state(
    tmp_path: Path,
    *,
    saved_public_base_url: str | None,
    base_url: str,
) -> Iterator[TestClient]:
    database_path = tmp_path / "url-generation.sqlite3"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path.as_posix()}",
        session_secret="url-generation-session-secret",
        encryption_key="url-generation-encryption-key",
        google_oauth_redirect_path="/auth/google/callback",
    )
    engine = create_engine(
        settings.database_url,
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        if saved_public_base_url is not None:
            set_app_state(
                session,
                key="public_base_url",
                value_text=saved_public_base_url,
            )
        session.commit()

    app = create_app(settings=settings)

    @app.get("/debug/external-url")
    def debug_external_url(request: Request) -> dict[str, str]:
        with Session(engine) as session:
            url = _build_external_url_via_service(
                request,
                "/healthz",
                session=session,
                settings=settings,
            )
        return {"url": url}

    @app.get("/debug/google-callback-url")
    def debug_google_callback_url(request: Request) -> dict[str, str]:
        with Session(engine) as session:
            url = _build_google_callback_url_via_service(
                request,
                session=session,
                settings=settings,
            )
        return {"url": url}

    with TestClient(app, base_url=base_url) as client:
        yield client


def _build_external_url_via_service(
    request: Request,
    path: str,
    *,
    session: Session,
    settings: Settings,
) -> str:
    from calsync.services.app_settings import (
        build_external_url as service_build_external_url,
    )

    return service_build_external_url(
        request,
        path,
        session=session,
        settings=settings,
    )


def _build_google_callback_url_via_service(
    request: Request,
    *,
    session: Session,
    settings: Settings,
) -> str:
    from calsync.services.app_settings import (
        build_google_callback_url as service_build_google_callback_url,
    )

    return service_build_google_callback_url(
        request,
        session=session,
        settings=settings,
    )
