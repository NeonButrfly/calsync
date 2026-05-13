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
    return _get_engine_for_url(resolved_settings.database_url)


@lru_cache(maxsize=None)
def _get_engine_for_url(database_url: str) -> Engine:
    return create_engine(
        database_url,
        future=True,
        **_engine_kwargs(database_url),
    )


def get_engine(settings: Settings | None = None) -> Engine:
    return create_db_engine(settings)


def create_session_factory(
    settings: Settings | None = None,
) -> sessionmaker[Session]:
    resolved_settings = settings or get_settings()
    return _get_session_factory_for_url(resolved_settings.database_url)


@lru_cache(maxsize=None)
def _get_session_factory_for_url(database_url: str) -> sessionmaker[Session]:
    return sessionmaker(
        bind=_get_engine_for_url(database_url),
        autoflush=False,
        expire_on_commit=False,
    )


def get_db_session(settings: Settings | None = None) -> Iterator[Session]:
    session = create_session_factory(settings)()
    try:
        yield session
    finally:
        session.close()
