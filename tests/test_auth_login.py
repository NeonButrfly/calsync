from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from calsync.config import Settings
from calsync.main import create_app
from calsync.models import AdminUser, Base
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
        session_secret="phase1-login-session-secret",
        encryption_key=ENCRYPTION_KEY,
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


def test_login_rejects_replayed_totp_code_after_counter_is_persisted(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference_time = datetime(2026, 5, 12, 18, 0, tzinfo=UTC)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return reference_time.replace(tzinfo=None)
            return reference_time.astimezone(tz)

    monkeypatch.setattr("calsync.services.auth.datetime", FrozenDateTime)
    replay_code = pyotp.TOTP(client.app.state.test_totp_secret).at(reference_time)

    first_password_step = client.post(
        "/login",
        data={
            "identifier": "admin",
            "password": "StrongPassword1!",
        },
        follow_redirects=False,
    )
    assert first_password_step.status_code == 303

    first_mfa_step = client.post(
        "/login/mfa",
        data={"code": replay_code},
        follow_redirects=False,
    )
    assert first_mfa_step.status_code == 303

    second_password_step = client.post(
        "/login",
        data={
            "identifier": "admin@example.com",
            "password": "StrongPassword1!",
        },
        follow_redirects=False,
    )
    assert second_password_step.status_code == 303

    replay_attempt = client.post("/login/mfa", data={"code": replay_code})
    assert replay_attempt.status_code == 400
    assert "Enter a valid MFA code or recovery code." in replay_attempt.text

    with _db_session(client) as session:
        admin_user = session.scalar(
            select(AdminUser).where(AdminUser.username == "admin")
        )
        assert admin_user is not None
        assert admin_user.mfa_last_accepted_counter == pyotp.TOTP(
            client.app.state.test_totp_secret
        ).timecode(reference_time)


def test_login_fails_closed_without_session_secret(tmp_path: Path) -> None:
    database_path = tmp_path / "login-no-session-secret.sqlite3"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        public_base_url="http://testserver",
        encryption_key=ENCRYPTION_KEY,
    )
    engine = create_engine(
        settings.database_url,
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    _seed_admin_user(engine)

    with TestClient(create_app(settings)) as test_client:
        with pytest.raises(RuntimeError, match="session_secret"):
            test_client.post(
                "/login",
                data={
                    "identifier": "admin",
                    "password": "StrongPassword1!",
                },
            )


def _seed_admin_user(engine) -> None:
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
        store_recovery_codes(session, admin_user, generate_recovery_codes(count=2))
        session.commit()


def _db_session(client: TestClient) -> Session:
    settings = client.app.state.settings
    engine = create_engine(
        settings.database_url,
        future=True,
        connect_args={"check_same_thread": False},
    )
    return Session(engine)
