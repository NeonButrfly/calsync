from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from calsync.config import Settings, get_settings


def _engine_kwargs(database_url: str) -> dict[str, object]:
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


def create_db_engine(settings: Settings | None = None) -> Engine:
    resolved_settings = settings or get_settings()
    return create_engine(
        resolved_settings.database_url,
        future=True,
        **_engine_kwargs(resolved_settings.database_url),
    )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_db_engine()


def create_session_factory(
    settings: Settings | None = None,
) -> sessionmaker[Session]:
    engine = create_db_engine(settings) if settings else get_engine()
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


SessionLocal = create_session_factory()


def get_db_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
