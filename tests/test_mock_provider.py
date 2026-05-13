from __future__ import annotations

from datetime import UTC
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from calsync.models import Event, ProviderAccount, ProviderCalendar, SyncLog
from calsync.config import get_settings
from calsync.services.sync import discover_calendars, sync_account


EXPECTED_MOCK_EVENT_COUNT = 5


@pytest.fixture()
def migrated_session_factory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> sessionmaker[Session]:
    database_path = tmp_path / "mock-provider.db"
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


@pytest.fixture()
def migrated_session(
    migrated_session_factory: sessionmaker[Session],
) -> Session:
    with migrated_session_factory() as session:
        yield session


@pytest.fixture()
def mock_account(migrated_session: Session) -> ProviderAccount:
    account = ProviderAccount(
        provider_type="mock",
        provider_account_id="mock-acct-1",
        display_name="Mock Account",
        provider_metadata={"seed": "phase1"},
    )
    migrated_session.add(account)
    migrated_session.commit()
    migrated_session.refresh(account)
    return account


def test_mock_provider_discovers_calendars(
    migrated_session: Session,
    mock_account: ProviderAccount,
) -> None:
    discovered = discover_calendars(migrated_session, mock_account.id)

    assert [calendar.name for calendar in discovered] == ["Home", "Work", "Shared"]
    assert [calendar.provider_calendar_id for calendar in discovered] == [
        "home",
        "work",
        "shared",
    ]
    assert migrated_session.scalars(
        select(ProviderCalendar).where(
            ProviderCalendar.provider_account_pk == mock_account.id,
        )
    ).all()


def test_mock_sync_populates_events_without_duplicates(
    migrated_session: Session,
    mock_account: ProviderAccount,
) -> None:
    first_log = sync_account(migrated_session, mock_account.id, trigger="manual")
    migrated_session.commit()

    second_log = sync_account(migrated_session, mock_account.id, trigger="manual")
    migrated_session.commit()

    events = migrated_session.scalars(select(Event)).all()
    logs = migrated_session.scalars(select(SyncLog).order_by(SyncLog.started_at)).all()

    assert len(events) == EXPECTED_MOCK_EVENT_COUNT
    assert len(logs) == 2
    assert first_log.id != second_log.id
    assert {event.provider_event_id for event in events} == {
        "home-standup",
        "home-dinner",
        "work-planning",
        "work-demo",
        "shared-game-night",
    }


def test_mock_sync_logging_is_recorded(
    migrated_session: Session,
    mock_account: ProviderAccount,
) -> None:
    log = sync_account(migrated_session, mock_account.id, trigger="manual")
    migrated_session.commit()

    stored = migrated_session.get(SyncLog, log.id)

    assert stored is not None
    assert stored.provider_account_pk == mock_account.id
    assert stored.provider_type == "mock"
    assert stored.trigger == "manual"
    assert stored.status == "success"
    assert stored.events_seen == EXPECTED_MOCK_EVENT_COUNT
    assert stored.events_upserted == EXPECTED_MOCK_EVENT_COUNT
    assert stored.error_text is None
    assert stored.started_at <= stored.finished_at
