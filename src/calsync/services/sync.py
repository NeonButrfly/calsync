from __future__ import annotations

from sqlalchemy.orm import Session

from calsync.config import Settings
from calsync.models import ProviderCalendar, SyncLog
from calsync.repos.events import mark_events_missing_from_sync, upsert_event
from calsync.repos.providers import (
    begin_sync_run,
    list_enabled_provider_calendars,
    reconcile_provider_calendars,
    require_provider_account,
    upsert_provider_calendar,
)
from calsync.services.providers import get_provider_adapter
from calsync.services.reconciliation import rebuild_duplicate_groups


def discover_calendars(
    session: Session,
    account_pk: str,
    *,
    settings: Settings | None = None,
) -> list[ProviderCalendar]:
    account = require_provider_account(session, account_pk)
    adapter = get_provider_adapter(account.provider_type, settings=settings, session=session)
    discovered_calendars = adapter.discover_calendars(account)
    was_incremental_discovery = bool(
        getattr(adapter, "last_calendar_discovery_was_incremental", False)
    )
    disabled_calendars: list[ProviderCalendar] = []

    calendars: list[ProviderCalendar] = []
    for discovered_calendar in discovered_calendars:
        calendar = upsert_provider_calendar(
            session,
            account=account,
            discovered_calendar=discovered_calendar,
        )
        if discovered_calendar.deleted:
            calendar.enabled = False
        calendars.append(calendar)

    if not was_incremental_discovery:
        disabled_calendars = reconcile_provider_calendars(
            session,
            account=account,
            discovered_external_ids={
                discovered_calendar.external_id for discovered_calendar in discovered_calendars
            },
        )
        for disabled_calendar in disabled_calendars:
            mark_events_missing_from_sync(
                session,
                provider_type=account.provider_type,
                provider_account_id=account.provider_account_id,
                provider_calendar_id=disabled_calendar.provider_calendar_id,
                seen_provider_event_ids=set(),
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
            fetched_events = adapter.fetch_events(account, calendar)
            seen_provider_event_ids: set[str] = set()

            for event in fetched_events:
                sync_run.record_seen()
                payload = event.model_dump(mode="python")
                seen_provider_event_ids.add(str(payload["provider_event_id"]))
                upsert_event(session, payload)
                sync_run.record_upserted()

            if not getattr(adapter, "last_events_fetch_was_incremental", False):
                mark_events_missing_from_sync(
                    session,
                    provider_type=account.provider_type,
                    provider_account_id=account.provider_account_id,
                    provider_calendar_id=calendar.provider_calendar_id,
                    seen_provider_event_ids=seen_provider_event_ids,
                )

        rebuild_duplicate_groups(session)
        sync_run.mark_success()

    session.flush()
    return sync_run.log
