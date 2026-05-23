from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session, sessionmaker

from calsync.config import get_settings
from calsync.models import Event, EventGroup
from calsync.repos.events import upsert_event
from calsync.services.reconciliation import (
    list_duplicate_groups,
    prefer_event_in_group,
    rebuild_duplicate_groups,
    restore_hidden_duplicates_in_group,
)


@pytest.fixture()
def migrated_session_factory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> sessionmaker[Session]:
    database_path = tmp_path / "event-reconciliation.db"
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


def test_rebuild_duplicate_groups_creates_group_for_matching_events(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    with migrated_session_factory() as session:
        google_event = upsert_event(
            session,
            _make_event(
                provider_type="google",
                provider_account_id="g-1",
                provider_calendar_id="cal-a",
                provider_event_id="evt-google",
                title="Cardiology Follow-up",
                description="Main record from Google",
                location="Clinic East",
            ),
        )
        icloud_event = upsert_event(
            session,
            _make_event(
                provider_type="icloud_caldav",
                provider_account_id="i-1",
                provider_calendar_id="cal-b",
                provider_event_id="evt-icloud",
                title="Cardiology Follow-up",
            ),
        )

        groups = rebuild_duplicate_groups(session)
        session.commit()

        assert len(groups) == 1
        assert groups[0].preferred_event_id == google_event.id

    with migrated_session_factory() as session:
        stored_group = session.get(EventGroup, groups[0].id)
        stored_google = session.get(Event, google_event.id)
        stored_icloud = session.get(Event, icloud_event.id)

        assert stored_group is not None
        assert stored_google is not None
        assert stored_icloud is not None
        assert stored_google.canonical_group_id == stored_group.id
        assert stored_icloud.canonical_group_id == stored_group.id
        assert stored_google.event_visibility_state == "active"
        assert stored_icloud.event_visibility_state == "hidden_duplicate"


def test_rebuild_duplicate_groups_matches_small_time_and_title_drift(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    with migrated_session_factory() as session:
        first = upsert_event(
            session,
            _make_event(
                provider_type="google",
                provider_account_id="g-1",
                provider_calendar_id="cal-a",
                provider_event_id="evt-google",
                title="Dentist Appointment",
                starts_at=datetime(2026, 5, 24, 15, 0, tzinfo=UTC),
                ends_at=datetime(2026, 5, 24, 16, 0, tzinfo=UTC),
            ),
        )
        second = upsert_event(
            session,
            _make_event(
                provider_type="icloud_caldav",
                provider_account_id="i-1",
                provider_calendar_id="cal-b",
                provider_event_id="evt-icloud",
                title="Dentist Appt.",
                starts_at=datetime(2026, 5, 24, 15, 10, tzinfo=UTC),
                ends_at=datetime(2026, 5, 24, 16, 10, tzinfo=UTC),
            ),
        )

        groups = rebuild_duplicate_groups(session)
        session.commit()

        assert len(groups) == 1

    with migrated_session_factory() as session:
        stored_first = session.get(Event, first.id)
        stored_second = session.get(Event, second.id)

        assert stored_first is not None
        assert stored_second is not None
        assert stored_first.canonical_group_id == stored_second.canonical_group_id
        assert {stored_first.event_visibility_state, stored_second.event_visibility_state} == {
            "active",
            "hidden_duplicate",
        }


def test_rebuild_duplicate_groups_does_not_bridge_transitive_time_matches(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    with migrated_session_factory() as session:
        first = upsert_event(
            session,
            _make_event(
                provider_type="google",
                provider_account_id="g-1",
                provider_calendar_id="cal-a",
                provider_event_id="evt-google",
                title="Dermatology Follow-up",
                starts_at=datetime(2026, 5, 24, 15, 0, tzinfo=UTC),
                ends_at=datetime(2026, 5, 24, 16, 0, tzinfo=UTC),
            ),
        )
        second = upsert_event(
            session,
            _make_event(
                provider_type="icloud_caldav",
                provider_account_id="i-1",
                provider_calendar_id="cal-b",
                provider_event_id="evt-icloud",
                title="Dermatology Follow-up",
                starts_at=datetime(2026, 5, 24, 15, 10, tzinfo=UTC),
                ends_at=datetime(2026, 5, 24, 16, 10, tzinfo=UTC),
            ),
        )
        third = upsert_event(
            session,
            _make_event(
                provider_type="mock",
                provider_account_id="m-1",
                provider_calendar_id="cal-c",
                provider_event_id="evt-mock",
                title="Dermatology Follow-up",
                starts_at=datetime(2026, 5, 24, 15, 20, tzinfo=UTC),
                ends_at=datetime(2026, 5, 24, 16, 20, tzinfo=UTC),
            ),
        )

        groups = rebuild_duplicate_groups(session)
        session.commit()

        assert len(groups) == 1

    with migrated_session_factory() as session:
        stored_first = session.get(Event, first.id)
        stored_second = session.get(Event, second.id)
        stored_third = session.get(Event, third.id)

        assert stored_first is not None
        assert stored_second is not None
        assert stored_third is not None
        assert stored_first.canonical_group_id == stored_second.canonical_group_id
        assert stored_first.canonical_group_id is not None
        assert stored_third.canonical_group_id is None
        assert stored_third.event_visibility_state == "active"


def test_rebuild_duplicate_groups_promotes_hidden_duplicate_when_it_is_alone(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    with migrated_session_factory() as session:
        hidden_event = upsert_event(
            session,
            _make_event(
                provider_event_id="evt-hidden",
                event_visibility_state="hidden_duplicate",
            ),
        )
        session.commit()

        groups = rebuild_duplicate_groups(session)
        session.commit()

        assert groups == []

    with migrated_session_factory() as session:
        stored = session.get(Event, hidden_event.id)

        assert stored is not None
        assert stored.event_visibility_state == "active"
        assert stored.canonical_group_id is None


def test_prefer_event_in_group_hides_other_members(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    with migrated_session_factory() as session:
        first = upsert_event(
            session,
            _make_event(
                provider_type="google",
                provider_account_id="g-1",
                provider_calendar_id="cal-a",
                provider_event_id="evt-1",
                title="Pediatric Checkup",
            ),
        )
        second = upsert_event(
            session,
            _make_event(
                provider_type="icloud_caldav",
                provider_account_id="i-1",
                provider_calendar_id="cal-b",
                provider_event_id="evt-2",
                title="Pediatric Checkup",
                description="Has a better description",
            ),
        )
        rebuild_duplicate_groups(session)
        session.commit()

        groups = list_duplicate_groups(session)
        assert len(groups) == 1

        prefer_event_in_group(session, groups[0].group.id, second.id)
        session.commit()

    with migrated_session_factory() as session:
        stored_first = session.get(Event, first.id)
        stored_second = session.get(Event, second.id)
        stored_group = session.get(EventGroup, groups[0].group.id)

        assert stored_first is not None
        assert stored_second is not None
        assert stored_group is not None
        assert stored_group.preferred_event_id == second.id
        assert stored_second.event_visibility_state == "active"
        assert stored_first.event_visibility_state == "hidden_duplicate"


def test_restore_hidden_duplicates_in_group_persists_across_rebuilds(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    with migrated_session_factory() as session:
        first = upsert_event(
            session,
            _make_event(
                provider_type="google",
                provider_account_id="g-1",
                provider_calendar_id="cal-a",
                provider_event_id="evt-restore-1",
                title="Physical Therapy",
            ),
        )
        second = upsert_event(
            session,
            _make_event(
                provider_type="icloud_caldav",
                provider_account_id="i-1",
                provider_calendar_id="cal-b",
                provider_event_id="evt-restore-2",
                title="Physical Therapy",
            ),
        )
        rebuild_duplicate_groups(session)
        session.commit()

        groups = list_duplicate_groups(session)
        assert len(groups) == 1

        restore_hidden_duplicates_in_group(session, groups[0].group.id)
        session.commit()

        rebuild_duplicate_groups(session)
        session.commit()

    with migrated_session_factory() as session:
        stored_first = session.get(Event, first.id)
        stored_second = session.get(Event, second.id)

        assert stored_first is not None
        assert stored_second is not None
        assert stored_first.event_visibility_state == "active"
        assert stored_second.event_visibility_state == "active"
        assert stored_first.duplicate_visibility_override is False
        assert stored_second.duplicate_visibility_override is True


def _make_event(**overrides: object) -> dict[str, object]:
    payload = {
        "provider_type": "mock",
        "provider_account_id": "acct-1",
        "provider_calendar_id": "cal-1",
        "provider_event_id": "evt-1",
        "title": "Planning session",
        "starts_at": datetime(2026, 5, 24, 15, 0, tzinfo=UTC),
        "ends_at": datetime(2026, 5, 24, 16, 0, tzinfo=UTC),
        "all_day": False,
        "status": "confirmed",
        "source_payload": {"provider": "mock"},
    }
    payload.update(overrides)
    return payload
