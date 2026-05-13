import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from calsync.models import AdminUser, Base
from calsync.repos.users import create_admin_user
from calsync.services.auth import (
    consume_recovery_code,
    generate_recovery_codes,
    store_recovery_codes,
)


@pytest.fixture()
def session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with SessionLocal() as db_session:
        yield db_session


@pytest.fixture()
def admin_user(session: Session) -> AdminUser:
    return create_admin_user(
        session,
        username="admin",
        email="admin@example.com",
    )


def test_recovery_codes_are_one_time_use(
    session: Session,
    admin_user: AdminUser,
) -> None:
    codes = generate_recovery_codes(count=3)
    store_recovery_codes(session, admin_user, codes)
    session.flush()
    stored_payload = json.loads(admin_user.recovery_codes_json or "[]")

    assert len(stored_payload) == 3
    assert all(entry["code_hash"] != codes[index] for index, entry in enumerate(stored_payload))
    assert consume_recovery_code(session, admin_user, codes[0].lower()) is True
    assert consume_recovery_code(session, admin_user, codes[0].lower()) is False
    assert consume_recovery_code(session, admin_user, "not-a-real-code") is False
