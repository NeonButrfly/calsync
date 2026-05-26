from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from calsync.config import Settings
from calsync.models import Event, ProviderAccount, ProviderCalendar, utcnow
from calsync.repos.events import upsert_event
from calsync.repos.providers import (
    get_provider_account,
    provider_calendar_supports_write,
)
from calsync.schemas.providers import WritableEventInput
from calsync.services.providers.base import get_provider_adapter
from calsync.services.reconciliation import rebuild_duplicate_groups
from calsync.services.source_labels import friendly_provider_name
from calsync.web.timezones import ALASKA_TIMEZONE


WRITABLE_CALENDAR_ROLE = "writable_booking_target"


@dataclass
class WritableCalendarOption:
    calendar_pk: str
    account_pk: str
    provider_type: str
    provider_label: str
    account_label: str
    calendar_label: str
    description: str


def list_writable_calendar_options(session: Session) -> list[WritableCalendarOption]:
    calendars = session.scalars(
        select(ProviderCalendar)
        .join(ProviderAccount, ProviderCalendar.provider_account_pk == ProviderAccount.id)
        .where(
            ProviderCalendar.enabled.is_(True),
            ProviderCalendar.calendar_role == WRITABLE_CALENDAR_ROLE,
        )
        .order_by(
            ProviderAccount.provider_type,
            ProviderAccount.display_name,
            ProviderCalendar.name,
            ProviderCalendar.provider_calendar_id,
        )
    ).all()

    options: list[WritableCalendarOption] = []
    for calendar in calendars:
        account = calendar.account or session.get(ProviderAccount, calendar.provider_account_pk)
        if account is None:
            continue
        if not account.can_write:
            continue
        if not provider_calendar_supports_write(account, calendar):
            continue
        account_label = account.display_name or account.provider_account_id
        calendar_label = calendar.name or calendar.provider_calendar_id
        provider_label = friendly_provider_name(account.provider_type)
        options.append(
            WritableCalendarOption(
                calendar_pk=calendar.id,
                account_pk=account.id,
                provider_type=account.provider_type,
                provider_label=provider_label,
                account_label=account_label,
                calendar_label=calendar_label,
                description=f"{provider_label} · {account_label} · {calendar_label}",
            )
        )
    return options


def require_writable_calendar(
    session: Session,
    calendar_pk: str,
) -> tuple[ProviderAccount, ProviderCalendar]:
    calendar = session.get(ProviderCalendar, calendar_pk)
    if calendar is None:
        raise LookupError("Writable target calendar not found.")
    account = calendar.account or get_provider_account(session, calendar.provider_account_pk)
    if account is None:
        raise LookupError("Writable target account not found.")
    if not calendar.enabled:
        raise ValueError("Writable target calendar is currently disabled.")
    if calendar.calendar_role != WRITABLE_CALENDAR_ROLE:
        raise ValueError("Writable target calendar is not configured to receive appointments.")
    if not account.can_write or not provider_calendar_supports_write(account, calendar):
        raise ValueError("Writable target calendar does not support calendar writes.")
    return account, calendar


def create_writable_appointment(
    session: Session,
    *,
    calendar_pk: str,
    event_input: WritableEventInput,
    settings: Settings,
) -> Event:
    account, calendar = require_writable_calendar(session, calendar_pk)
    adapter = get_provider_adapter(
        account.provider_type,
        settings=settings,
        session=session,
    )
    normalized_event = adapter.create_event(account, calendar, event_input)
    event = upsert_event(session, normalized_event.model_dump())
    rebuild_duplicate_groups(session)
    session.flush()
    return event


def update_writable_appointment(
    session: Session,
    *,
    event_id: str,
    event_input: WritableEventInput,
    settings: Settings,
) -> Event:
    event = require_writable_event(session, event_id)
    account, calendar = _require_event_write_context(session, event)
    adapter = get_provider_adapter(
        account.provider_type,
        settings=settings,
        session=session,
    )
    normalized_event = adapter.update_event(
        account,
        calendar,
        event.provider_event_id,
        event_input,
        source_payload=dict(event.source_payload or {}),
    )
    updated_event = upsert_event(session, normalized_event.model_dump())
    rebuild_duplicate_groups(session)
    session.flush()
    return updated_event


def cancel_writable_appointment(
    session: Session,
    *,
    event_id: str,
    settings: Settings,
) -> Event:
    event = require_writable_event(session, event_id)
    account, calendar = _require_event_write_context(session, event)
    adapter = get_provider_adapter(
        account.provider_type,
        settings=settings,
        session=session,
    )
    normalized_event = adapter.cancel_event(
        account,
        calendar,
        event.provider_event_id,
        source_payload=dict(event.source_payload or {}),
    )
    if normalized_event is None:
        event.status = "cancelled"
        event.event_visibility_state = "deleted_upstream"
        event.removed_upstream_at = utcnow()
        event.last_seen_upstream_at = utcnow()
        cancelled_event = event
    else:
        cancelled_event = upsert_event(session, normalized_event.model_dump())
    rebuild_duplicate_groups(session)
    session.flush()
    return cancelled_event


def require_writable_event(session: Session, event_id: str) -> Event:
    event = session.get(Event, event_id)
    if event is None:
        raise LookupError(f"Event not found: {event_id}")
    return event


def _require_event_write_context(
    session: Session,
    event: Event,
) -> tuple[ProviderAccount, ProviderCalendar]:
    if event.provider_calendar_pk is None:
        raise ValueError("This appointment is not linked to a writable calendar record.")
    account, calendar = require_writable_calendar(session, event.provider_calendar_pk)
    if (
        event.provider_type != account.provider_type
        or event.provider_account_id != account.provider_account_id
        or event.provider_calendar_id != calendar.provider_calendar_id
    ):
        raise ValueError("This appointment no longer matches the writable calendar that owns it.")
    return account, calendar


def event_local_input_defaults(event: Event) -> dict[str, object]:
    return {
        "title": event.title,
        "description": event.description or "",
        "location": event.location or "",
        "starts_at_local": _format_datetime_local(event.starts_at),
        "ends_at_local": _format_datetime_local(event.ends_at),
        "all_day": event.all_day,
    }


def parse_local_datetime_input(
    *,
    title: str,
    description: str | None,
    location: str | None,
    starts_at_local: str,
    ends_at_local: str,
    all_day: bool,
    display_timezone,
) -> WritableEventInput:
    starts_at = _parse_local_datetime(starts_at_local, display_timezone)
    ends_at = _parse_local_datetime(ends_at_local, display_timezone)
    if ends_at <= starts_at:
        raise ValueError("End time must be later than the start time.")
    return WritableEventInput(
        title=title.strip(),
        description=(description or "").strip() or None,
        location=(location or "").strip() or None,
        starts_at=starts_at,
        ends_at=ends_at,
        all_day=all_day,
    )


def _parse_local_datetime(value: str, display_timezone) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=display_timezone)
    else:
        parsed = parsed.astimezone(display_timezone)
    return parsed.astimezone(UTC)


def _format_datetime_local(value: datetime) -> str:
    return value.astimezone(ALASKA_TIMEZONE).replace(second=0, microsecond=0).strftime(
        "%Y-%m-%dT%H:%M"
    )
