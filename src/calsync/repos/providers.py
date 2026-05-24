from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from calsync.models import ProviderAccount, ProviderCalendar, SyncLog, utcnow
from calsync.schemas.providers import DiscoveredCalendar


def infer_provider_capabilities(account: ProviderAccount) -> tuple[str, bool, bool]:
    if account.provider_type == "icloud_caldav":
        from calsync.services.providers.icloud import (
            infer_icloud_account_capabilities,
        )

        return infer_icloud_account_capabilities(account)
    if account.provider_type == "google":
        from calsync.services.providers.google import infer_google_account_capabilities

        return infer_google_account_capabilities(account)
    return account.auth_mode, account.can_read, account.can_write


def hydrate_provider_account_capabilities(account: ProviderAccount) -> ProviderAccount:
    auth_mode, can_read, can_write = infer_provider_capabilities(account)
    account.auth_mode = auth_mode
    account.can_read = can_read
    account.can_write = can_write
    return account


def get_provider_account_by_identity(
    session: Session,
    *,
    provider_type: str,
    provider_account_id: str,
) -> ProviderAccount | None:
    account = session.scalar(
        select(ProviderAccount).where(
            ProviderAccount.provider_type == provider_type,
            ProviderAccount.provider_account_id == provider_account_id,
        )
    )
    if account is None:
        return None
    return hydrate_provider_account_capabilities(account)


def get_provider_account(session: Session, account_pk: str) -> ProviderAccount | None:
    account = session.get(ProviderAccount, account_pk)
    if account is None:
        return None
    return hydrate_provider_account_capabilities(account)


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
            enabled=discovered_calendar.default_enabled,
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


def upsert_provider_account(
    session: Session,
    *,
    provider_type: str,
    provider_account_id: str,
    display_name: str | None = None,
    provider_metadata: dict[str, object] | None = None,
) -> ProviderAccount:
    account = get_provider_account_by_identity(
        session,
        provider_type=provider_type,
        provider_account_id=provider_account_id,
    )
    if account is None:
        account = ProviderAccount(
            provider_type=provider_type,
            provider_account_id=provider_account_id,
        )
        session.add(account)

    account.display_name = display_name
    account.provider_metadata = (
        dict(provider_metadata)
        if provider_metadata is not None
        else None
    )
    hydrate_provider_account_capabilities(account)
    session.flush()
    return account


def reconcile_provider_calendars(
    session: Session,
    *,
    account: ProviderAccount,
    discovered_external_ids: set[str],
) -> list[ProviderCalendar]:
    calendars = session.scalars(
        select(ProviderCalendar).where(
            ProviderCalendar.provider_account_pk == account.id,
        )
    ).all()

    disabled_calendars: list[ProviderCalendar] = []
    for calendar in calendars:
        if calendar.provider_calendar_id not in discovered_external_ids:
            calendar.enabled = False
            disabled_calendars.append(calendar)

    session.flush()
    return disabled_calendars


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


def list_provider_calendars(
    session: Session,
    *,
    account: ProviderAccount,
) -> list[ProviderCalendar]:
    return list(
        session.scalars(
            select(ProviderCalendar)
            .where(ProviderCalendar.provider_account_pk == account.id)
            .order_by(ProviderCalendar.provider_calendar_id)
        )
    )


@dataclass
class SyncRunHandle:
    log: SyncLog
    events_seen: int = field(default=0, init=False)
    events_upserted: int = field(default=0, init=False)

    def record_seen(self, count: int = 1) -> None:
        self.events_seen += count
        self.log.events_seen = self.events_seen

    def record_upserted(self, count: int = 1) -> None:
        self.events_upserted += count
        self.log.events_upserted = self.events_upserted

    def mark_success(
        self,
        *,
        events_seen: int | None = None,
        events_upserted: int | None = None,
    ) -> None:
        self.log.status = "success"
        self.log.events_seen = self.events_seen if events_seen is None else events_seen
        self.log.events_upserted = (
            self.events_upserted if events_upserted is None else events_upserted
        )
        self.log.error_text = None
        self.log.finished_at = utcnow()

    def mark_failure(
        self,
        *,
        error_text: str,
        events_seen: int | None = None,
        events_upserted: int | None = None,
    ) -> None:
        self.log.status = "failed"
        self.log.events_seen = self.events_seen if events_seen is None else events_seen
        self.log.events_upserted = (
            self.events_upserted if events_upserted is None else events_upserted
        )
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
