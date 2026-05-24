from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session, sessionmaker

from calsync.config import get_settings
from calsync.models import ProviderAccount, ProviderCalendar


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
        from sqlalchemy import create_engine

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
