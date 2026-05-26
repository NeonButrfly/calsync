from __future__ import annotations

from sqlalchemy.orm import Session

from calsync.models import Event, ProviderAccount, ProviderCalendar


def friendly_provider_name(provider_type: str) -> str:
    return {
        "google": "Google",
        "icloud_caldav": "Apple",
        "microsoft": "Microsoft",
        "mock": "Mock",
    }.get(provider_type, provider_type.replace("_", " ").title())


def account_label_for_event(session: Session, event: Event) -> str:
    if event.provider_account_pk:
        account = session.get(ProviderAccount, event.provider_account_pk)
        if account is not None and account.display_name:
            return account.display_name
    return event.provider_account_id


def calendar_label_for_event(session: Session, event: Event) -> str:
    if event.provider_calendar_pk:
        calendar = session.get(ProviderCalendar, event.provider_calendar_pk)
        if calendar is not None and calendar.name:
            return calendar.name
    return event.provider_calendar_id


def copy_label_for_event(session: Session, event: Event) -> str:
    return (
        f"{friendly_provider_name(event.provider_type)} - "
        f"{account_label_for_event(session, event)} - "
        f"{calendar_label_for_event(session, event)}"
    )


def source_line_for_event(session: Session, event: Event) -> str:
    return (
        f"{friendly_provider_name(event.provider_type)} · "
        f"{account_label_for_event(session, event)} · "
        f"{calendar_label_for_event(session, event)}"
    )
