from importlib.resources import files

from fastapi.testclient import TestClient

from calsync.main import create_app


def test_healthz_returns_ok() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_returns_service_identity() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "CalSync Scheduler" in response.text
    assert "See the household schedule clearly" in response.text


def test_api_info_returns_service_identity() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/info")

    assert response.status_code == 200
    assert response.json()["service"] == "calsync"
    assert response.json()["mode"] == "apple-first"


def test_readiness_api_returns_origin_and_edge_summary(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_USERNAME", "family@example.com")
    monkeypatch.setenv("APPLE_APP_SPECIFIC_PASSWORD", "secret")
    monkeypatch.setenv("APPLE_PRIMARY_CALENDAR_URL", "https://caldav.icloud.com/calendar/")
    monkeypatch.setenv("APPLE_PRIMARY_CALENDAR_NAME", "Family")
    monkeypatch.setenv("EDGE_BASE_URL", "https://edge-calsync.neonbutterfly.net")
    from calsync.config import get_settings

    get_settings.cache_clear()
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["origin"]["apple_ready"] is True
    assert body["origin"]["calendar_name"] == "Family"
    assert "alexa" in body["channel_tokens"]
    assert "reachable" in body["edge"]


def test_web_console_assets_are_packaged() -> None:
    web_package = files("calsync.web")

    assert (web_package / "templates" / "console.html").is_file()
    assert (web_package / "templates" / "appointment_edit.html").is_file()
    assert (web_package / "static" / "app.css").is_file()
