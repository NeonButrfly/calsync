from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from calsync.config import get_settings


@pytest.fixture()
def migrated_session_factory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> sessionmaker[Session]:
    database_path = tmp_path / "migration-schema.db"
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


def test_event_lifecycle_fields_round_trip(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    from calsync.models import Event, EventGroup
    from calsync.repos.events import upsert_event

    last_seen_upstream_at = datetime(2026, 5, 22, 19, 5, tzinfo=UTC)
    removed_upstream_at = datetime(2026, 5, 23, 1, 30, tzinfo=UTC)

    payload = {
        "provider_type": "mock",
        "provider_account_id": "acct-1",
        "provider_calendar_id": "cal-1",
        "provider_event_id": "evt-1",
        "title": "Dental Cleaning",
        "starts_at": datetime(2026, 5, 22, 18, 0, tzinfo=UTC),
        "ends_at": datetime(2026, 5, 22, 19, 0, tzinfo=UTC),
        "all_day": False,
        "status": "confirmed",
        "event_visibility_state": "deleted_upstream",
        "last_seen_upstream_at": last_seen_upstream_at,
        "removed_upstream_at": removed_upstream_at,
        "source_payload": {"provider": "mock"},
    }

    with migrated_session_factory() as session:
        event_group = EventGroup(
            display_title="Dental Cleaning",
            preferred_starts_at=payload["starts_at"],
            preferred_ends_at=payload["ends_at"],
            preferred_location=None,
        )
        session.add(event_group)
        session.flush()
        payload["canonical_group_id"] = event_group.id

        event = upsert_event(session, payload)
        session.commit()
        event_id = event.id

    with migrated_session_factory() as session:
        reloaded = session.get(Event, event_id)

        assert reloaded is not None
        assert reloaded.event_visibility_state == "deleted_upstream"
        assert reloaded.last_seen_upstream_at == last_seen_upstream_at
        assert reloaded.removed_upstream_at == removed_upstream_at
        assert reloaded.canonical_group_id == payload["canonical_group_id"]


def test_event_lifecycle_defaults_for_fresh_event(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    from calsync.models import Event
    from calsync.repos.events import upsert_event

    payload = {
        "provider_type": "mock",
        "provider_account_id": "acct-defaults",
        "provider_calendar_id": "cal-defaults",
        "provider_event_id": "evt-defaults",
        "title": "Fresh Event",
        "starts_at": datetime(2026, 5, 24, 15, 0, tzinfo=UTC),
        "ends_at": datetime(2026, 5, 24, 16, 0, tzinfo=UTC),
        "all_day": False,
        "status": "confirmed",
        "source_payload": {"provider": "mock"},
    }

    with migrated_session_factory() as session:
        event = upsert_event(session, payload)
        session.commit()
        event_id = event.id

    with migrated_session_factory() as session:
        reloaded = session.get(Event, event_id)

        assert reloaded is not None
        assert reloaded.event_visibility_state == "active"
        assert reloaded.removed_upstream_at is None
        assert reloaded.last_seen_upstream_at is not None
        assert reloaded.last_seen_upstream_at.tzinfo is not None
        assert reloaded.last_seen_upstream_at.utcoffset() == UTC.utcoffset(None)


def test_upsert_event_rejects_unknown_event_visibility_state(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    from calsync.repos.events import upsert_event

    payload = {
        "provider_type": "mock",
        "provider_account_id": "acct-invalid",
        "provider_calendar_id": "cal-invalid",
        "provider_event_id": "evt-invalid",
        "title": "Invalid Lifecycle",
        "starts_at": datetime(2026, 5, 24, 17, 0, tzinfo=UTC),
        "ends_at": datetime(2026, 5, 24, 18, 0, tzinfo=UTC),
        "all_day": False,
        "status": "confirmed",
        "event_visibility_state": "definitely-not-a-real-state",
        "source_payload": {"provider": "mock"},
    }

    with migrated_session_factory() as session:
        with pytest.raises(ValueError, match="event visibility state"):
            upsert_event(session, payload)


def test_upsert_event_rejects_active_event_with_removed_timestamp(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    from calsync.repos.events import upsert_event

    payload = {
        "provider_type": "mock",
        "provider_account_id": "acct-invalid-active",
        "provider_calendar_id": "cal-invalid-active",
        "provider_event_id": "evt-invalid-active",
        "title": "Inconsistent Active Event",
        "starts_at": datetime(2026, 5, 24, 19, 0, tzinfo=UTC),
        "ends_at": datetime(2026, 5, 24, 20, 0, tzinfo=UTC),
        "all_day": False,
        "status": "confirmed",
        "event_visibility_state": "active",
        "removed_upstream_at": datetime(2026, 5, 24, 21, 0, tzinfo=UTC),
        "source_payload": {"provider": "mock"},
    }

    with migrated_session_factory() as session:
        with pytest.raises(ValueError, match="Active events cannot have removed_upstream_at"):
            upsert_event(session, payload)


def test_upsert_event_rejects_deleted_event_without_removed_timestamp(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    from calsync.repos.events import upsert_event

    payload = {
        "provider_type": "mock",
        "provider_account_id": "acct-invalid-deleted",
        "provider_calendar_id": "cal-invalid-deleted",
        "provider_event_id": "evt-invalid-deleted",
        "title": "Inconsistent Deleted Event",
        "starts_at": datetime(2026, 5, 24, 19, 0, tzinfo=UTC),
        "ends_at": datetime(2026, 5, 24, 20, 0, tzinfo=UTC),
        "all_day": False,
        "status": "confirmed",
        "event_visibility_state": "deleted_upstream",
        "source_payload": {"provider": "mock"},
    }

    with migrated_session_factory() as session:
        with pytest.raises(ValueError, match="Deleted-upstream events require removed_upstream_at"):
            upsert_event(session, payload)


def test_database_rejects_invalid_event_visibility_state(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    from calsync.repos.events import upsert_event

    payload = {
        "provider_type": "mock",
        "provider_account_id": "acct-db-constraint",
        "provider_calendar_id": "cal-db-constraint",
        "provider_event_id": "evt-db-constraint",
        "title": "Constraint Event",
        "starts_at": datetime(2026, 5, 24, 19, 0, tzinfo=UTC),
        "ends_at": datetime(2026, 5, 24, 20, 0, tzinfo=UTC),
        "all_day": False,
        "status": "confirmed",
        "source_payload": {"provider": "mock"},
    }

    with migrated_session_factory() as session:
        event = upsert_event(session, payload)
        session.commit()

        with pytest.raises(IntegrityError):
            session.execute(
                text(
                    "UPDATE events SET event_visibility_state = :state WHERE id = :event_id"
                ),
                {"state": "bogus-direct-write", "event_id": event.id},
            )
            session.commit()


def test_upgrade_backfills_last_seen_upstream_at_for_existing_events(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "migration-backfill.db"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"

    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", database_url)

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_config, "20260514_01")

    from sqlalchemy import create_engine

    engine = create_engine(database_url, future=True)
    try:
        with Session(engine) as session:
            created_at = datetime(2026, 5, 20, 17, 0, tzinfo=UTC)
            updated_at = datetime(2026, 5, 21, 18, 30, tzinfo=UTC)
            session.execute(
                text(
                    """
                    INSERT INTO events (
                        id, provider_type, provider_account_id, provider_calendar_id,
                        provider_event_id, provider_account_pk, provider_calendar_pk,
                        title, description, location, starts_at, ends_at, all_day,
                        status, source_payload, created_at, updated_at
                    ) VALUES (
                        :id, :provider_type, :provider_account_id, :provider_calendar_id,
                        :provider_event_id, NULL, NULL,
                        :title, NULL, NULL, :starts_at, :ends_at, :all_day,
                        :status, NULL, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": "event-pre-upgrade",
                    "provider_type": "mock",
                    "provider_account_id": "acct-pre-upgrade",
                    "provider_calendar_id": "cal-pre-upgrade",
                    "provider_event_id": "evt-pre-upgrade",
                    "title": "Pre-upgrade Event",
                    "starts_at": created_at,
                    "ends_at": updated_at,
                    "all_day": False,
                    "status": "confirmed",
                    "created_at": created_at,
                    "updated_at": updated_at,
                },
            )
            session.commit()

        command.upgrade(alembic_config, "head")

        with Session(engine) as session:
            row = session.execute(
                text(
                    "SELECT event_visibility_state, last_seen_upstream_at FROM events WHERE id = :id"
                ),
                {"id": "event-pre-upgrade"},
            ).one()

            assert row.event_visibility_state == "active"
            assert row.last_seen_upstream_at is not None
            assert str(row.last_seen_upstream_at).startswith("2026-05-21 18:30:00")
    finally:
        get_settings.cache_clear()
