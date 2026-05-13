from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from calsync.models import Event, ProviderAccount, ProviderCalendar, SyncLog
from calsync.config import get_settings
from calsync.schemas.providers import DiscoveredCalendar, NormalizedEvent
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


def test_mock_sync_failure_records_partial_progress(
    migrated_session: Session,
    mock_account: ProviderAccount,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingAdapter:
        provider_type = "mock"

        def discover_calendars(
            self,
            account: ProviderAccount,
        ) -> list[DiscoveredCalendar]:
            return [
                DiscoveredCalendar(external_id="home", name="Home", timezone="America/Anchorage"),
                DiscoveredCalendar(external_id="work", name="Work", timezone="America/Anchorage"),
            ]

        def fetch_events(
            self,
            account: ProviderAccount,
            calendar: ProviderCalendar,
        ) -> list[NormalizedEvent]:
            if calendar.provider_calendar_id == "home":
                return [
                    NormalizedEvent(
                        provider_type="mock",
                        provider_account_id=account.provider_account_id,
                        provider_calendar_id="home",
                        provider_event_id="home-standup",
                        title="Morning Standup",
                        starts_at=datetime(2026, 5, 13, 16, 0, tzinfo=UTC),
                        ends_at=datetime(2026, 5, 13, 16, 15, tzinfo=UTC),
                    )
                ]
            raise RuntimeError("provider fetch failed")

    monkeypatch.setattr(
        "calsync.services.sync.get_provider_adapter",
        lambda provider_type: FailingAdapter(),
    )

    with pytest.raises(RuntimeError, match="provider fetch failed"):
        sync_account(migrated_session, mock_account.id, trigger="manual")

    migrated_session.commit()

    logs = migrated_session.scalars(select(SyncLog).order_by(SyncLog.started_at)).all()
    events = migrated_session.scalars(select(Event)).all()

    assert len(logs) == 1
    assert logs[0].status == "failed"
    assert logs[0].events_seen == 1
    assert logs[0].events_upserted == 1
    assert logs[0].error_text == "provider fetch failed"
    assert len(events) == 1


def test_discovery_disables_calendars_missing_from_provider(
    migrated_session: Session,
    mock_account: ProviderAccount,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    discover_calendars(migrated_session, mock_account.id)
    migrated_session.commit()

    class ReducedAdapter:
        provider_type = "mock"

        def discover_calendars(
            self,
            account: ProviderAccount,
        ) -> list[DiscoveredCalendar]:
            return [
                DiscoveredCalendar(external_id="home", name="Home", timezone="America/Anchorage"),
                DiscoveredCalendar(external_id="work", name="Work", timezone="America/Anchorage"),
            ]

        def fetch_events(
            self,
            account: ProviderAccount,
            calendar: ProviderCalendar,
        ) -> list[NormalizedEvent]:
            return []

    monkeypatch.setattr(
        "calsync.services.sync.get_provider_adapter",
        lambda provider_type: ReducedAdapter(),
    )

    discover_calendars(migrated_session, mock_account.id)
    migrated_session.commit()

    calendars = migrated_session.scalars(
        select(ProviderCalendar)
        .where(ProviderCalendar.provider_account_pk == mock_account.id)
        .order_by(ProviderCalendar.provider_calendar_id)
    ).all()

    assert [calendar.provider_calendar_id for calendar in calendars] == [
        "home",
        "shared",
        "work",
    ]
    assert [calendar.enabled for calendar in calendars] == [True, False, True]


def test_discovery_preserves_manual_disabled_state_on_rediscovery(
    migrated_session: Session,
    mock_account: ProviderAccount,
) -> None:
    discover_calendars(migrated_session, mock_account.id)
    migrated_session.commit()

    work_calendar = migrated_session.scalar(
        select(ProviderCalendar).where(
            ProviderCalendar.provider_account_pk == mock_account.id,
            ProviderCalendar.provider_calendar_id == "work",
        )
    )
    assert work_calendar is not None

    work_calendar.enabled = False
    migrated_session.commit()

    discover_calendars(migrated_session, mock_account.id)
    migrated_session.commit()

    calendars = migrated_session.scalars(
        select(ProviderCalendar)
        .where(ProviderCalendar.provider_account_pk == mock_account.id)
        .order_by(ProviderCalendar.provider_calendar_id)
    ).all()

    assert [calendar.provider_calendar_id for calendar in calendars] == [
        "home",
        "shared",
        "work",
    ]
    assert [calendar.enabled for calendar in calendars] == [True, True, False]
