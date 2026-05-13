from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from calsync.models import Event, ProviderAccount, ProviderCalendar


def _get_or_create_provider_account(
    session: Session,
    *,
    provider_type: str,
    provider_account_id: str,
) -> ProviderAccount:
    account = session.scalar(
        select(ProviderAccount).where(
            ProviderAccount.provider_type == provider_type,
            ProviderAccount.provider_account_id == provider_account_id,
        )
    )
    if account is None:
        account = ProviderAccount(
            provider_type=provider_type,
            provider_account_id=provider_account_id,
        )
        session.add(account)
        session.flush()
    return account


def _get_or_create_provider_calendar(
    session: Session,
    *,
    account: ProviderAccount,
    provider_calendar_id: str,
) -> ProviderCalendar:
    calendar = session.scalar(
        select(ProviderCalendar).where(
            ProviderCalendar.provider_account_pk == account.id,
            ProviderCalendar.provider_calendar_id == provider_calendar_id,
        )
    )
    if calendar is None:
        calendar = ProviderCalendar(
            provider_account_pk=account.id,
            provider_calendar_id=provider_calendar_id,
        )
        session.add(calendar)
        session.flush()
    return calendar


def upsert_event(session: Session, normalized_event: Mapping[str, Any]) -> Event:
    provider_type = str(normalized_event["provider_type"])
    provider_account_id = str(normalized_event["provider_account_id"])
    provider_calendar_id = str(normalized_event["provider_calendar_id"])
    provider_event_id = str(normalized_event["provider_event_id"])

    account = _get_or_create_provider_account(
        session,
        provider_type=provider_type,
        provider_account_id=provider_account_id,
    )
    calendar = _get_or_create_provider_calendar(
        session,
        account=account,
        provider_calendar_id=provider_calendar_id,
    )

    event = session.scalar(
        select(Event).where(
            Event.provider_type == provider_type,
            Event.provider_account_id == provider_account_id,
            Event.provider_calendar_id == provider_calendar_id,
            Event.provider_event_id == provider_event_id,
        )
    )

    if event is None:
        event = Event(
            provider_type=provider_type,
            provider_account_id=provider_account_id,
            provider_calendar_id=provider_calendar_id,
            provider_event_id=provider_event_id,
            provider_account_pk=account.id,
            provider_calendar_pk=calendar.id,
            title=str(normalized_event["title"]),
            description=_optional_str(normalized_event.get("description")),
            location=_optional_str(normalized_event.get("location")),
            starts_at=_required_datetime(normalized_event["starts_at"]),
            ends_at=_required_datetime(normalized_event["ends_at"]),
            all_day=bool(normalized_event.get("all_day", False)),
            status=str(normalized_event.get("status", "confirmed")),
            source_payload=_optional_dict(normalized_event.get("source_payload")),
        )
        session.add(event)
    else:
        event.provider_account_pk = account.id
        event.provider_calendar_pk = calendar.id
        event.title = str(normalized_event["title"])
        event.description = _optional_str(normalized_event.get("description"))
        event.location = _optional_str(normalized_event.get("location"))
        event.starts_at = _required_datetime(normalized_event["starts_at"])
        event.ends_at = _required_datetime(normalized_event["ends_at"])
        event.all_day = bool(normalized_event.get("all_day", False))
        event.status = str(normalized_event.get("status", "confirmed"))
        event.source_payload = _optional_dict(normalized_event.get("source_payload"))

    session.flush()
    return event


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _required_datetime(value: Any) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("Expected datetime value")
    return value


def _optional_dict(value: Any) -> dict[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError("Expected dict value")
    return dict(value)
