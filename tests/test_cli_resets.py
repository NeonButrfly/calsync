from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from calsync.config import Settings
from calsync.models import AdminUser, Base, ProviderAccount, ProviderCalendar, PublishedFeed
from calsync.repos.state import set_app_state
from calsync.repos.users import create_admin_user
from calsync.services.auth import (
    generate_recovery_codes,
    hash_password,
    store_recovery_codes,
    store_totp_secret,
    verify_password,
)


ENCRYPTION_KEY = "phase1-cli-reset-test-key"


@pytest.fixture()
def database_path(tmp_path: Path) -> Path:
    database_path = tmp_path / "cli-resets.sqlite3"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        encryption_key=ENCRYPTION_KEY,
        session_secret="phase1-cli-reset-session-secret",
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
        store_totp_secret(
            session,
            admin_user,
            "JBSWY3DPEHPK3PXP",
            encryption_key=ENCRYPTION_KEY,
        )
        admin_user.mfa_enrolled = True
        admin_user.mfa_last_accepted_counter = 41
        admin_user.session_version = 4
        store_recovery_codes(session, admin_user, generate_recovery_codes(count=2))

        provider_account = ProviderAccount(
            provider_type="google",
            provider_account_id="acct-123",
            display_name="Primary Google",
            provider_metadata={"tenant": "primary"},
        )
        session.add(provider_account)
        session.flush()
        session.add(
            ProviderCalendar(
                provider_account_pk=provider_account.id,
                provider_calendar_id="cal-123",
                name="Team Calendar",
                timezone="UTC",
                enabled=True,
                provider_metadata={"color": "blue"},
            )
        )
        session.add(
            PublishedFeed(
                scope_type="calendar",
                scope_key="acct-123:cal-123",
                token="feed-token-123",
                is_active=True,
                feed_metadata={"label": "external"},
            )
        )
        session.commit()

    return database_path


def test_reset_admin_password_preserves_provider_state_and_invalidates_sessions(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{database_path}")
    monkeypatch.setenv("ENCRYPTION_KEY", ENCRYPTION_KEY)
    from calsync.cli import app

    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "reset-admin-password",
            "--identifier",
            "admin",
            "--password",
            "NewStrongPassword1!",
        ],
    )

    assert result.exit_code == 0
    assert "NewStrongPassword1!" not in result.output

    with _db_session(database_path) as session:
        admin_user = session.scalar(
            select(AdminUser).where(AdminUser.username == "admin")
        )
        assert admin_user is not None
        assert verify_password("NewStrongPassword1!", admin_user.password_hash or "")
        assert admin_user.mfa_enrolled is True
        assert admin_user.mfa_secret_encrypted is not None
        assert admin_user.recovery_codes_json is not None
        assert admin_user.mfa_last_accepted_counter == 41
        assert admin_user.session_version == 5

        provider_account = session.scalar(select(ProviderAccount))
        assert provider_account is not None
        assert provider_account.provider_account_id == "acct-123"
        assert provider_account.provider_metadata == {"tenant": "primary"}

        provider_calendar = session.scalar(select(ProviderCalendar))
        assert provider_calendar is not None
        assert provider_calendar.provider_calendar_id == "cal-123"
        assert provider_calendar.provider_metadata == {"color": "blue"}

        published_feed = session.scalar(select(PublishedFeed))
        assert published_feed is not None
        assert published_feed.token == "feed-token-123"
        assert published_feed.feed_metadata == {"label": "external"}


def test_reset_admin_mfa_clears_only_mfa_state_and_preserves_password_and_config(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{database_path}")
    monkeypatch.setenv("ENCRYPTION_KEY", ENCRYPTION_KEY)
    from calsync.cli import app

    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "reset-admin-mfa",
            "--identifier",
            "admin@example.com",
        ],
    )

    assert result.exit_code == 0
    assert "JBSWY3DPEHPK3PXP" not in result.output

    with _db_session(database_path) as session:
        admin_user = session.scalar(
            select(AdminUser).where(AdminUser.username == "admin")
        )
        assert admin_user is not None
        assert verify_password("StrongPassword1!", admin_user.password_hash or "")
        assert admin_user.mfa_secret_encrypted is None
        assert admin_user.mfa_enrolled is False
        assert admin_user.recovery_codes_json is None
        assert admin_user.mfa_last_accepted_counter is None
        assert admin_user.session_version == 5

        provider_account = session.scalar(select(ProviderAccount))
        assert provider_account is not None
        assert provider_account.provider_account_id == "acct-123"

        provider_calendar = session.scalar(select(ProviderCalendar))
        assert provider_calendar is not None
        assert provider_calendar.provider_calendar_id == "cal-123"

        published_feed = session.scalar(select(PublishedFeed))
        assert published_feed is not None
        assert published_feed.token == "feed-token-123"


def _db_session(database_path: Path) -> Session:
    engine = create_engine(
        f"sqlite+pysqlite:///{database_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    return Session(engine)
