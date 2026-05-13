from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from calsync.config import Settings
from calsync.main import create_app
from calsync.models import Base
from calsync.repos.state import set_app_state
from calsync.repos.users import create_admin_user
from calsync.services.auth import (
    generate_recovery_codes,
    hash_password,
    store_recovery_codes,
    store_totp_secret,
)


ENCRYPTION_KEY = "phase1-login-test-key"


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    database_path = tmp_path / "auth-login.sqlite3"
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

    with Session(engine) as session:
        set_app_state(session, key="setup_completed", value_text="true")
        admin_user = create_admin_user(
            session,
            username="admin",
            email="admin@example.com",
            password_hash=hash_password("StrongPassword1!"),
        )
        totp_secret = pyotp.random_base32()
        store_totp_secret(
            session,
            admin_user,
            totp_secret,
            encryption_key=ENCRYPTION_KEY,
        )
        admin_user.mfa_enrolled = True
        recovery_codes = generate_recovery_codes(count=2)
        store_recovery_codes(session, admin_user, recovery_codes)
        session.commit()

    app = create_app(settings)
    app.state.encryption_key = ENCRYPTION_KEY
    app.state.test_totp_secret = totp_secret
    app.state.test_recovery_codes = recovery_codes

    with TestClient(app) as test_client:
        yield test_client


def test_login_requires_password_then_totp_before_session_is_established(
    client: TestClient,
) -> None:
    login_page = client.get("/login")
    assert login_page.status_code == 200

    password_step = client.post(
        "/login",
        data={
            "identifier": "admin",
            "password": "StrongPassword1!",
        },
        follow_redirects=False,
    )

    assert password_step.status_code == 303
    assert password_step.headers["location"] == "/login/mfa"
    assert client.get("/login/mfa").status_code == 200

    mfa_step = client.post(
        "/login/mfa",
        data={
            "code": pyotp.TOTP(client.app.state.test_totp_secret).now(),
        },
        follow_redirects=False,
    )

    assert mfa_step.status_code == 303
    assert mfa_step.headers["location"] == "/"

    home = client.get("/")
    assert home.status_code == 200
    assert home.json() == {"status": "ok"}


def test_login_allows_recovery_code_as_second_factor(
    client: TestClient,
) -> None:
    password_step = client.post(
        "/login",
        data={
            "identifier": "admin@example.com",
            "password": "StrongPassword1!",
        },
        follow_redirects=False,
    )

    assert password_step.status_code == 303

    recovery_step = client.post(
        "/login/mfa",
        data={
            "code": client.app.state.test_recovery_codes[0].lower(),
        },
        follow_redirects=False,
    )

    assert recovery_step.status_code == 303
    assert recovery_step.headers["location"] == "/"

    reused_code = client.post(
        "/login/mfa",
        data={
            "code": client.app.state.test_recovery_codes[0].lower(),
        },
    )
    assert reused_code.status_code == 400
