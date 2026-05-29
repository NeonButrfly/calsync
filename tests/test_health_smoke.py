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
    assert "Add to calendars through CalSync" in response.text


def test_api_info_returns_service_identity() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/info")

    assert response.status_code == 200
    assert response.json()["service"] == "calsync"
    assert response.json()["mode"] == "apple-first"
