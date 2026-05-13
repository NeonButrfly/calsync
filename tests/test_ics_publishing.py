from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from calsync.config import get_settings
from calsync.main import create_app
from calsync.repos.events import upsert_event
from calsync.services.publishing import (
    ensure_combined_feed,
    rotate_combined_feed_token,
)


@pytest.fixture()
def migrated_session_factory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> sessionmaker[Session]:
    database_path = tmp_path / "ics-publishing.db"
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
def client(
    migrated_session_factory: sessionmaker[Session],
) -> TestClient:
    del migrated_session_factory
    get_settings.cache_clear()
    with TestClient(create_app(get_settings())) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_combined_feed_returns_calendar_payload(
    migrated_session: Session,
    client: TestClient,
) -> None:
    _seed_normalized_events(migrated_session)
    feed = ensure_combined_feed(migrated_session)
    migrated_session.commit()

    response = client.get(f"/feeds/{feed.token}.ics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert "BEGIN:VCALENDAR" in response.text
    assert "BEGIN:VEVENT" in response.text
    assert "SUMMARY:Morning Standup" in response.text
    assert "SUMMARY:Roadmap Review" in response.text


def test_rotating_feed_token_invalidates_previous_token(
    migrated_session: Session,
    client: TestClient,
) -> None:
    _seed_normalized_events(migrated_session)
    original_feed = ensure_combined_feed(migrated_session)
    migrated_session.commit()
    previous_token = original_feed.token

    rotated_feed = rotate_combined_feed_token(migrated_session)
    migrated_session.commit()

    assert rotated_feed.token != previous_token

    old_response = client.get(f"/feeds/{previous_token}.ics")
    new_response = client.get(f"/feeds/{rotated_feed.token}.ics")

    assert old_response.status_code == 404
    assert new_response.status_code == 200
    assert "BEGIN:VCALENDAR" in new_response.text


def _seed_normalized_events(session: Session) -> None:
    upsert_event(
        session,
        {
            "provider_type": "mock",
            "provider_account_id": "mock-acct-1",
            "provider_calendar_id": "home",
            "provider_event_id": "home-standup",
            "title": "Morning Standup",
            "description": "Daily sync",
            "location": "Desk",
            "starts_at": datetime(2026, 5, 13, 16, 0, tzinfo=UTC),
            "ends_at": datetime(2026, 5, 13, 16, 15, tzinfo=UTC),
            "all_day": False,
            "status": "confirmed",
            "source_payload": {"seed": "phase1"},
        },
    )
    upsert_event(
        session,
        {
            "provider_type": "mock",
            "provider_account_id": "mock-acct-1",
            "provider_calendar_id": "work",
            "provider_event_id": "work-roadmap",
            "title": "Roadmap Review",
            "description": "Review priorities",
            "location": "Conference Room",
            "starts_at": datetime(2026, 5, 13, 18, 0, tzinfo=UTC),
            "ends_at": datetime(2026, 5, 13, 19, 0, tzinfo=UTC),
            "all_day": False,
            "status": "confirmed",
            "source_payload": {"seed": "phase1"},
        },
    )
    session.flush()
