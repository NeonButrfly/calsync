from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import IntegrityError

from calsync.config import get_settings
from calsync.models import ProviderAccount, ProviderCalendar
from calsync.repos.providers import get_provider_account, upsert_provider_account


@pytest.fixture()
def migrated_session_factory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> sessionmaker[Session]:
    database_path = tmp_path / "calendar-roles.db"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"

    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", database_url)

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_config, "head")

    try:
        engine = create_engine(database_url, future=True)
        yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    finally:
        get_settings.cache_clear()


def test_provider_account_capabilities_round_trip(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    with migrated_session_factory() as write_session:
        account = ProviderAccount(
            provider_type="google",
            provider_account_id="acct-1",
            display_name="Primary",
            auth_mode="service_account",
            can_read=True,
            can_write=True,
            requires_reconnect=True,
        )
        write_session.add(account)
        write_session.commit()
        account_id = account.id

    with migrated_session_factory() as read_session:
        reloaded = read_session.get(ProviderAccount, account_id)

        assert reloaded is not None
        assert reloaded.auth_mode == "service_account"
        assert reloaded.can_read is True
        assert reloaded.can_write is True
        assert reloaded.requires_reconnect is True


def test_provider_calendar_role_round_trip(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    with migrated_session_factory() as write_session:
        account = ProviderAccount(
            provider_type="mock",
            provider_account_id="acct-2",
            display_name="Mock Account",
        )
        write_session.add(account)
        write_session.flush()

        calendar = ProviderCalendar(
            provider_account_pk=account.id,
            provider_calendar_id="cal-1",
            name="Bookings",
            calendar_role="writable_booking_target",
        )
        write_session.add(calendar)
        write_session.commit()
        calendar_id = calendar.id

    with migrated_session_factory() as read_session:
        reloaded = read_session.get(ProviderCalendar, calendar_id)

        assert reloaded is not None
        assert reloaded.calendar_role == "writable_booking_target"


def test_provider_calendar_role_rejects_unknown_values(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    with migrated_session_factory() as write_session:
        account = ProviderAccount(
            provider_type="mock",
            provider_account_id="acct-3",
            display_name="Constraint Test",
        )
        write_session.add(account)
        write_session.flush()

        write_session.add(
            ProviderCalendar(
                provider_account_pk=account.id,
                provider_calendar_id="cal-invalid",
                name="Bad Role",
                calendar_role="typo_role",
            )
        )

        with pytest.raises(IntegrityError):
            write_session.commit()


def test_provider_role_migration_backfills_defaults_for_existing_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "calendar-roles-upgrade.db"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"

    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", database_url)

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", database_url)

    try:
        command.upgrade(alembic_config, "20260523_01")

        engine = create_engine(database_url, future=True)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO provider_accounts (
                        id,
                        provider_type,
                        provider_account_id,
                        display_name,
                        created_at,
                        updated_at
                    ) VALUES (
                        :id,
                        :provider_type,
                        :provider_account_id,
                        :display_name,
                        CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "id": "acct-existing",
                    "provider_type": "google",
                    "provider_account_id": "acct-legacy",
                    "display_name": "Legacy Account",
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO provider_calendars (
                        id,
                        provider_account_pk,
                        provider_calendar_id,
                        name,
                        enabled,
                        created_at,
                        updated_at
                    ) VALUES (
                        :id,
                        :provider_account_pk,
                        :provider_calendar_id,
                        :name,
                        :enabled,
                        CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "id": "cal-existing",
                    "provider_account_pk": "acct-existing",
                    "provider_calendar_id": "cal-legacy",
                    "name": "Legacy Calendar",
                    "enabled": True,
                },
            )

        command.upgrade(alembic_config, "head")

        session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with session_factory() as read_session:
            account = read_session.get(ProviderAccount, "acct-existing")
            calendar = read_session.get(ProviderCalendar, "cal-existing")

            assert account is not None
            assert account.auth_mode == "oauth"
            assert account.can_read is True
            assert account.can_write is False
            assert account.requires_reconnect is False

            assert calendar is not None
            assert calendar.calendar_role == "personal_reference"
    finally:
        get_settings.cache_clear()


def test_icloud_account_defaults(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    encrypted_secret = "existing-encrypted-secret"

    with migrated_session_factory() as write_session:
        account = ProviderAccount(
            provider_type="icloud_caldav",
            provider_account_id="kay@icloud.com",
            display_name="Kay iCloud",
            credential_secret_encrypted=encrypted_secret,
        )
        write_session.add(account)
        write_session.commit()
        account_id = account.id

    with migrated_session_factory() as read_session:
        existing_account = read_session.get(ProviderAccount, account_id)
        assert existing_account is not None

        updated = upsert_provider_account(
            read_session,
            provider_type="icloud_caldav",
            provider_account_id="kay@icloud.com",
            display_name="Kay iCloud",
            provider_metadata={"principal_url": "https://caldav.icloud.com/123/principal/"},
        )
        read_session.commit()

        assert updated.id == account_id
        assert updated.auth_mode == "caldav"
        assert updated.can_read is True
        assert updated.can_write is False
        assert updated.credential_secret_encrypted == encrypted_secret


def test_upsert_provider_account_preserves_existing_metadata_keys(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    with migrated_session_factory() as write_session:
        account = ProviderAccount(
            provider_type="icloud_caldav",
            provider_account_id="kay@icloud.com",
            display_name="Kay iCloud",
            provider_metadata={
                "principal_url": "https://caldav.icloud.com/123/principal/",
                "calendar_home_url": "https://caldav.icloud.com/123/calendars/",
                "auth_status": "connected",
            },
        )
        write_session.add(account)
        write_session.commit()

    with migrated_session_factory() as read_session:
        updated = upsert_provider_account(
            read_session,
            provider_type="icloud_caldav",
            provider_account_id="kay@icloud.com",
            display_name="Kay iCloud",
            provider_metadata={"last_auth_error": None},
        )
        read_session.commit()

        assert updated.provider_metadata == {
            "principal_url": "https://caldav.icloud.com/123/principal/",
            "calendar_home_url": "https://caldav.icloud.com/123/calendars/",
            "auth_status": "connected",
            "last_auth_error": None,
        }


def test_google_account_capabilities(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    with migrated_session_factory() as session:
        account = upsert_provider_account(
            session,
            provider_type="google",
            provider_account_id="google-sub",
            display_name="owner@example.com",
            provider_metadata={
                "google_scopes": [
                    "openid",
                    "email",
                    "https://www.googleapis.com/auth/calendar",
                ]
            },
        )
        session.commit()

        assert account.auth_mode == "oauth"
        assert account.can_read is True
        assert account.can_write is True


def test_get_provider_account_hydrates_google_capabilities_from_current_scopes(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    with migrated_session_factory() as write_session:
        account = ProviderAccount(
            provider_type="google",
            provider_account_id="google-sub",
            display_name="owner@example.com",
            can_write=True,
            provider_metadata={
                "google_scopes": [
                    "openid",
                    "email",
                    "https://www.googleapis.com/auth/calendar.readonly",
                ]
            },
        )
        write_session.add(account)
        write_session.commit()
        account_id = account.id

    with migrated_session_factory() as read_session:
        hydrated = get_provider_account(read_session, account_id)

        assert hydrated is not None
        assert hydrated.auth_mode == "oauth"
        assert hydrated.can_read is True
        assert hydrated.can_write is False


def test_get_provider_account_hydrates_icloud_defaults(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    encrypted_secret = "existing-encrypted-secret"

    with migrated_session_factory() as write_session:
        account = ProviderAccount(
            provider_type="icloud_caldav",
            provider_account_id="kay@icloud.com",
            display_name="Kay iCloud",
            auth_mode="oauth",
            can_read=False,
            can_write=True,
            credential_secret_encrypted=encrypted_secret,
            provider_metadata={},
        )
        write_session.add(account)
        write_session.commit()
        account_id = account.id

    with migrated_session_factory() as read_session:
        hydrated = get_provider_account(read_session, account_id)

        assert hydrated is not None
        assert hydrated.auth_mode == "caldav"
        assert hydrated.can_read is True
        assert hydrated.can_write is False
        assert hydrated.credential_secret_encrypted == encrypted_secret
