from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from calsync.models import Event, ProviderAccount, ProviderCalendar, utcnow
from calsync.models.events import EVENT_VISIBILITY_STATES


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


def get_event_by_provider_identity(
    session: Session,
    *,
    provider_type: str,
    provider_account_id: str,
    provider_calendar_id: str,
    provider_event_id: str,
) -> Event | None:
    return session.scalar(
        select(Event).where(
            Event.provider_type == provider_type,
            Event.provider_account_id == provider_account_id,
            Event.provider_calendar_id == provider_calendar_id,
            Event.provider_event_id == provider_event_id,
        )
    )


def upsert_event(session: Session, normalized_event: Mapping[str, Any]) -> Event:
    provider_type = str(normalized_event["provider_type"])
    provider_account_id = str(normalized_event["provider_account_id"])
    provider_calendar_id = str(normalized_event["provider_calendar_id"])
    provider_event_id = str(normalized_event["provider_event_id"])
    all_day = _required_bool(normalized_event.get("all_day", False))
    starts_at = _required_datetime(normalized_event["starts_at"])
    ends_at = _required_datetime(normalized_event["ends_at"])
    status = str(normalized_event.get("status", "confirmed"))
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

    event = get_event_by_provider_identity(
        session,
        provider_type=provider_type,
        provider_account_id=provider_account_id,
        provider_calendar_id=provider_calendar_id,
        provider_event_id=provider_event_id,
    )
    event_visibility_state = _resolved_event_visibility_state(
        normalized_event=normalized_event,
        status=status,
        existing_event=event,
    )
    last_seen_upstream_at = _resolved_last_seen_upstream_at(normalized_event)
    removed_upstream_at = _resolved_removed_upstream_at(
        normalized_event=normalized_event,
        existing_event=event,
        event_visibility_state=event_visibility_state,
    )
    _validate_lifecycle_consistency(
        event_visibility_state=event_visibility_state,
        removed_upstream_at=removed_upstream_at,
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
            starts_at=starts_at,
            ends_at=ends_at,
            all_day=all_day,
            status=status,
            event_visibility_state=event_visibility_state,
            last_seen_upstream_at=last_seen_upstream_at,
            removed_upstream_at=removed_upstream_at,
            canonical_group_id=_optional_str(normalized_event.get("canonical_group_id")),
            source_payload=_optional_dict(normalized_event.get("source_payload")),
        )
        session.add(event)
    else:
        event.provider_account_pk = account.id
        event.provider_calendar_pk = calendar.id
        event.title = str(normalized_event["title"])
        event.description = _optional_str(normalized_event.get("description"))
        event.location = _optional_str(normalized_event.get("location"))
        event.starts_at = starts_at
        event.ends_at = ends_at
        event.all_day = all_day
        event.status = status
        event.event_visibility_state = event_visibility_state
        event.last_seen_upstream_at = last_seen_upstream_at
        event.removed_upstream_at = removed_upstream_at
        if "canonical_group_id" in normalized_event:
            event.canonical_group_id = _optional_str(normalized_event.get("canonical_group_id"))
        event.source_payload = _optional_dict(normalized_event.get("source_payload"))

    session.flush()
    return event


def mark_events_missing_from_sync(
    session: Session,
    *,
    provider_type: str,
    provider_account_id: str,
    provider_calendar_id: str,
    seen_provider_event_ids: set[str],
) -> int:
    removed_at = utcnow()
    events = session.scalars(
        select(Event).where(
            Event.provider_type == provider_type,
            Event.provider_account_id == provider_account_id,
            Event.provider_calendar_id == provider_calendar_id,
        )
    ).all()

    updated_count = 0
    for event in events:
        if event.provider_event_id in seen_provider_event_ids:
            continue
        if event.event_visibility_state == "deleted_upstream":
            continue
        event.event_visibility_state = "deleted_upstream"
        event.removed_upstream_at = removed_at
        updated_count += 1

    session.flush()
    return updated_count


def _validated_event_visibility_state(value: Any) -> str:
    visibility_state = str(value)
    if visibility_state not in EVENT_VISIBILITY_STATES:
        allowed_values = ", ".join(sorted(EVENT_VISIBILITY_STATES))
        raise ValueError(
            f"Unknown event visibility state '{visibility_state}'. Expected one of: {allowed_values}"
        )
    return visibility_state


def _resolved_event_visibility_state(
    *,
    normalized_event: Mapping[str, Any],
    status: str,
    existing_event: Event | None,
) -> str:
    if "event_visibility_state" in normalized_event:
        return _validated_event_visibility_state(normalized_event["event_visibility_state"])
    if status.lower() == "cancelled":
        return "cancelled"
    if existing_event is not None and existing_event.event_visibility_state in {
        "hidden_duplicate",
        "stale_unverified",
    }:
        return existing_event.event_visibility_state
    return "active"


def _resolved_last_seen_upstream_at(normalized_event: Mapping[str, Any]) -> datetime | None:
    if "last_seen_upstream_at" in normalized_event:
        return _optional_datetime(normalized_event.get("last_seen_upstream_at"))
    return utcnow()


def _resolved_removed_upstream_at(
    *,
    normalized_event: Mapping[str, Any],
    existing_event: Event | None,
    event_visibility_state: str,
) -> datetime | None:
    if "removed_upstream_at" in normalized_event:
        return _optional_datetime(normalized_event.get("removed_upstream_at"))
    explicit_visibility_state = normalized_event.get("event_visibility_state")
    if explicit_visibility_state == "deleted_upstream":
        if existing_event is not None:
            return existing_event.removed_upstream_at
        return None
    if event_visibility_state == "deleted_upstream":
        if existing_event is not None and existing_event.removed_upstream_at is not None:
            return existing_event.removed_upstream_at
        return utcnow()
    return None


def _validate_lifecycle_consistency(
    *,
    event_visibility_state: str,
    removed_upstream_at: datetime | None,
) -> None:
    if event_visibility_state == "active" and removed_upstream_at is not None:
        raise ValueError("Active events cannot have removed_upstream_at set.")
    if event_visibility_state == "deleted_upstream" and removed_upstream_at is None:
        raise ValueError("Deleted-upstream events require removed_upstream_at.")


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _required_datetime(value: Any) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("Expected datetime value")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Expected timezone-aware datetime value")
    return value


def _optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    return _required_datetime(value)


def _required_bool(value: Any) -> bool:
    if not isinstance(value, bool):
        raise TypeError("Expected bool value")
    return value


def _optional_dict(value: Any) -> dict[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError("Expected dict value")
    return dict(value)
