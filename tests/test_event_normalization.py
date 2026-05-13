from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from calsync.models import Base, Event
from calsync.repos.events import upsert_event


@pytest.fixture()
def session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as db_session:
        yield db_session


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
    session: Session,
    normalized_event: dict[str, object],
) -> None:
    first = upsert_event(session, normalized_event)
    second = upsert_event(session, normalized_event)

    assert first.id == second.id
    assert session.query(Event).count() == 1
