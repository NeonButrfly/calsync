from __future__ import annotations

from sqlalchemy.orm import Session

from calsync.config import Settings
from calsync.models import ProviderCalendar, SyncLog
from calsync.repos.events import upsert_event
from calsync.repos.providers import (
    begin_sync_run,
    list_enabled_provider_calendars,
    reconcile_provider_calendars,
    require_provider_account,
    upsert_provider_calendar,
)
from calsync.services.providers import get_provider_adapter


def discover_calendars(
    session: Session,
    account_pk: str,
    *,
    settings: Settings | None = None,
) -> list[ProviderCalendar]:
    account = require_provider_account(session, account_pk)
    adapter = get_provider_adapter(account.provider_type, settings=settings, session=session)
    discovered_calendars = adapter.discover_calendars(account)

    calendars = [
        upsert_provider_calendar(
            session,
            account=account,
            discovered_calendar=discovered_calendar,
        )
        for discovered_calendar in discovered_calendars
    ]
    reconcile_provider_calendars(
        session,
        account=account,
        discovered_external_ids={
            discovered_calendar.external_id for discovered_calendar in discovered_calendars
        },
    )
    session.flush()
    return calendars


def sync_account(
    session: Session,
    account_pk: str,
    *,
    trigger: str = "manual",
    settings: Settings | None = None,
) -> SyncLog:
    account = require_provider_account(session, account_pk)
    adapter = get_provider_adapter(account.provider_type, settings=settings, session=session)

    with begin_sync_run(session, account=account, trigger=trigger) as sync_run:
        discover_calendars(session, account_pk, settings=settings)
        calendars = list_enabled_provider_calendars(session, account=account)

        for calendar in calendars:
            for event in adapter.fetch_events(account, calendar):
                sync_run.record_seen()
                upsert_event(session, event.model_dump(mode="python"))
                sync_run.record_upserted()

        sync_run.mark_success()

    session.flush()
    return sync_run.log
