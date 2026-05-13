from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from calsync.config import Settings
from calsync.main import create_app
from calsync.models import AdminUser, AppState, Base


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    database_path = tmp_path / "setup-flow.sqlite3"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        public_base_url="http://testserver",
    )
    engine = create_engine(
        settings.database_url,
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)

    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_first_run_setup_creates_initial_admin_and_locks_route(
    client: TestClient,
) -> None:
    setup_page = client.get("/setup")

    assert setup_page.status_code == 200
    secret = _extract_input_value(setup_page.text, "totp_secret")
    assert secret

    setup_response = client.post(
        "/setup",
        data={
            "username": "admin",
            "email": "admin@example.com",
            "password": "StrongPassword1!",
            "password_confirmation": "StrongPassword1!",
            "totp_code": pyotp.TOTP(secret).now(),
            "recovery_acknowledged": "on",
        },
        follow_redirects=False,
    )

    assert setup_response.status_code == 303
    assert setup_response.headers["location"] == "/login"

    locked_response = client.get("/setup")
    assert locked_response.status_code == 404

    with _db_session(client) as session:
        admin_user = session.scalar(
            select(AdminUser).where(AdminUser.username == "admin")
        )
        assert admin_user is not None
        assert admin_user.email == "admin@example.com"
        assert admin_user.password_hash is not None
        assert admin_user.mfa_enrolled is True
        assert admin_user.mfa_secret_encrypted is not None
        assert admin_user.recovery_codes_json is not None

        setup_state = session.get(AppState, "setup_completed")
        assert setup_state is not None
        assert setup_state.value_text == "true"


def test_setup_requires_valid_totp_and_recovery_acknowledgement(
    client: TestClient,
) -> None:
    setup_page = client.get("/setup")

    assert setup_page.status_code == 200
    secret = _extract_input_value(setup_page.text, "totp_secret")

    missing_ack_response = client.post(
        "/setup",
        data={
            "username": "admin",
            "email": "admin@example.com",
            "password": "StrongPassword1!",
            "password_confirmation": "StrongPassword1!",
            "totp_code": pyotp.TOTP(secret).now(),
        },
    )

    assert missing_ack_response.status_code == 200
    assert "Acknowledge that you stored at least one recovery code." in (
        missing_ack_response.text
    )

    invalid_totp_response = client.post(
        "/setup",
        data={
            "username": "admin",
            "email": "admin@example.com",
            "password": "StrongPassword1!",
            "password_confirmation": "StrongPassword1!",
            "totp_code": "000000",
            "recovery_acknowledged": "on",
        },
    )

    assert invalid_totp_response.status_code == 200
    assert "Enter a valid MFA code to finish setup." in invalid_totp_response.text

    with _db_session(client) as session:
        assert session.scalar(select(AdminUser)) is None


def test_setup_requires_matching_password_confirmation(
    client: TestClient,
) -> None:
    setup_page = client.get("/setup")

    assert setup_page.status_code == 200
    secret = _extract_input_value(setup_page.text, "totp_secret")

    mismatched_password_response = client.post(
        "/setup",
        data={
            "username": "admin",
            "email": "admin@example.com",
            "password": "StrongPassword1!",
            "password_confirmation": "DifferentPassword1!",
            "totp_code": pyotp.TOTP(secret).now(),
            "recovery_acknowledged": "on",
        },
    )

    assert mismatched_password_response.status_code == 200
    assert "Password confirmation must match." in mismatched_password_response.text

    with _db_session(client) as session:
        assert session.scalar(select(AdminUser)) is None


def _extract_input_value(html: str, name: str) -> str:
    parser = _InputValueParser(name)
    parser.feed(html)
    assert parser.value is not None
    return parser.value


def _db_session(client: TestClient) -> Session:
    settings = client.app.state.settings
    engine = create_engine(
        settings.database_url,
        future=True,
        connect_args={"check_same_thread": False},
    )
    return Session(engine)


class _InputValueParser(HTMLParser):
    def __init__(self, field_name: str) -> None:
        super().__init__()
        self.field_name = field_name
        self.value: str | None = None

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag != "input" or self.value is not None:
            return

        attr_map = dict(attrs)
        if attr_map.get("name") != self.field_name:
            return

        value = attr_map.get("value")
        if value is not None:
            self.value = value
