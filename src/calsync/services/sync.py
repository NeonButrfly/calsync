from __future__ import annotations

from sqlalchemy.orm import Session

from calsync.models import ProviderCalendar, SyncLog
from calsync.repos.events import upsert_event
from calsync.repos.providers import (
    begin_sync_run,
    list_enabled_provider_calendars,
    require_provider_account,
    upsert_provider_calendar,
)
from calsync.services.providers import get_provider_adapter


def discover_calendars(session: Session, account_pk: str) -> list[ProviderCalendar]:
    account = require_provider_account(session, account_pk)
    adapter = get_provider_adapter(account.provider_type)

    calendars = [
        upsert_provider_calendar(
            session,
            account=account,
            discovered_calendar=discovered_calendar,
        )
        for discovered_calendar in adapter.discover_calendars(account)
    ]
    session.flush()
    return calendars


def sync_account(
    session: Session,
    account_pk: str,
    *,
    trigger: str = "manual",
) -> SyncLog:
    account = require_provider_account(session, account_pk)
    adapter = get_provider_adapter(account.provider_type)

    with begin_sync_run(session, account=account, trigger=trigger) as sync_run:
        discover_calendars(session, account_pk)
        calendars = list_enabled_provider_calendars(session, account=account)

        events_seen = 0
        events_upserted = 0
        for calendar in calendars:
            for event in adapter.fetch_events(account, calendar):
                upsert_event(session, event.model_dump(mode="python"))
                events_seen += 1
                events_upserted += 1

        sync_run.mark_success(
            events_seen=events_seen,
            events_upserted=events_upserted,
        )

    session.flush()
    return sync_run.log
