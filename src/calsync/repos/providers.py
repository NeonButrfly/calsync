from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from calsync.models import ProviderAccount, ProviderCalendar, SyncLog, utcnow
from calsync.schemas.providers import DiscoveredCalendar


def get_provider_account(session: Session, account_pk: str) -> ProviderAccount | None:
    return session.get(ProviderAccount, account_pk)


def require_provider_account(session: Session, account_pk: str) -> ProviderAccount:
    account = get_provider_account(session, account_pk)
    if account is None:
        raise LookupError(f"Provider account not found: {account_pk}")
    return account


def upsert_provider_calendar(
    session: Session,
    *,
    account: ProviderAccount,
    discovered_calendar: DiscoveredCalendar,
) -> ProviderCalendar:
    calendar = session.scalar(
        select(ProviderCalendar).where(
            ProviderCalendar.provider_account_pk == account.id,
            ProviderCalendar.provider_calendar_id == discovered_calendar.external_id,
        )
    )
    if calendar is None:
        calendar = ProviderCalendar(
            provider_account_pk=account.id,
            provider_calendar_id=discovered_calendar.external_id,
            enabled=True,
        )
        session.add(calendar)

    calendar.name = discovered_calendar.name
    calendar.timezone = discovered_calendar.timezone
    calendar.provider_metadata = (
        dict(discovered_calendar.metadata)
        if discovered_calendar.metadata is not None
        else None
    )
    session.flush()
    return calendar


def list_enabled_provider_calendars(
    session: Session,
    *,
    account: ProviderAccount,
) -> list[ProviderCalendar]:
    return list(
        session.scalars(
            select(ProviderCalendar)
            .where(
                ProviderCalendar.provider_account_pk == account.id,
                ProviderCalendar.enabled.is_(True),
            )
            .order_by(ProviderCalendar.provider_calendar_id)
        )
    )


@dataclass
class SyncRunHandle:
    log: SyncLog

    def mark_success(
        self,
        *,
        events_seen: int,
        events_upserted: int,
    ) -> None:
        self.log.status = "success"
        self.log.events_seen = events_seen
        self.log.events_upserted = events_upserted
        self.log.error_text = None
        self.log.finished_at = utcnow()

    def mark_failure(
        self,
        *,
        error_text: str,
        events_seen: int = 0,
        events_upserted: int = 0,
    ) -> None:
        self.log.status = "failed"
        self.log.events_seen = events_seen
        self.log.events_upserted = events_upserted
        self.log.error_text = error_text
        self.log.finished_at = utcnow()


@contextmanager
def begin_sync_run(
    session: Session,
    *,
    account: ProviderAccount,
    trigger: str,
) -> Iterator[SyncRunHandle]:
    log = SyncLog(
        provider_account_pk=account.id,
        provider_type=account.provider_type,
        trigger=trigger,
        status="pending",
        started_at=utcnow(),
    )
    session.add(log)
    session.flush()

    handle = SyncRunHandle(log=log)
    try:
        yield handle
    except Exception as exc:
        handle.mark_failure(error_text=str(exc))
        session.flush()
        raise
    else:
        session.flush()
