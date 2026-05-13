from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from calsync.config import get_settings
from calsync.models import Event
from calsync.repos.events import upsert_event


def _build_session(database_url: str) -> Iterator[Session]:
    engine = create_engine(database_url, future=True)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as db_session:
        yield db_session


@pytest.fixture()
def migrated_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Session]:
    database_path = tmp_path / "migration-schema.db"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"

    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", database_url)

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_config, "head")

    try:
        yield from _build_session(database_url)
    finally:
        get_settings.cache_clear()


@pytest.fixture()
def normalized_event() -> dict[str, object]:
    return {
        "provider_type": "mock",
        "provider_account_id": "acct-1",
        "provider_calendar_id": "cal-1",
        "provider_event_id": "evt-1",
        "title": "Planning session",
        "description": "Review upcoming work.",
        "location": "Conference room",
        "starts_at": datetime(2026, 5, 12, 18, 0, tzinfo=UTC),
        "ends_at": datetime(2026, 5, 12, 19, 0, tzinfo=UTC),
        "all_day": False,
        "status": "confirmed",
        "source_payload": {"provider": "mock"},
    }


def test_upsert_event_reuses_existing_provider_identity(
    migrated_session: Session,
    normalized_event: dict[str, object],
) -> None:
    first = upsert_event(migrated_session, normalized_event)
    second = upsert_event(migrated_session, normalized_event)

    assert first.id == second.id
    assert migrated_session.query(Event).count() == 1


def test_upsert_event_rejects_non_boolean_all_day(
    migrated_session: Session,
    normalized_event: dict[str, object],
) -> None:
    normalized_event["all_day"] = "false"

    with pytest.raises(TypeError, match="Expected bool value"):
        upsert_event(migrated_session, normalized_event)


def test_upsert_event_rejects_naive_required_datetime(
    migrated_session: Session,
    normalized_event: dict[str, object],
) -> None:
    normalized_event["starts_at"] = datetime(2026, 5, 12, 18, 0)

    with pytest.raises(ValueError, match="timezone-aware datetime"):
        upsert_event(migrated_session, normalized_event)
