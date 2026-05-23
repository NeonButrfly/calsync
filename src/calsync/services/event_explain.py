from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from calsync.models import Event, EventGroup, SyncLog
from calsync.services.reconciliation import list_group_events


@dataclass
class EventExplainCopy:
    id: str
    title: str
    provider_type: str
    provider_account_id: str
    provider_calendar_id: str
    visibility_state: str
    is_preferred: bool


@dataclass
class EventExplainView:
    event: Event
    copies: list[EventExplainCopy]
    preferred_copy_id: str
    preferred_reason: str
    latest_sync: SyncLog | None


def build_event_explain_view(session: Session, event_id: str) -> EventExplainView:
    event = session.get(Event, event_id)
    if event is None:
        raise LookupError(f"Event not found: {event_id}")

    group = session.get(EventGroup, event.canonical_group_id) if event.canonical_group_id else None
    copies = list_group_events(session, event.canonical_group_id) if event.canonical_group_id else [event]
    preferred_copy = next(
        (copy for copy in copies if copy.id == (group.preferred_event_id if group else event.id)),
        event,
    )
    latest_sync = _latest_sync_log(session, event)

    return EventExplainView(
        event=event,
        copies=[
            EventExplainCopy(
                id=copy.id,
                title=copy.title,
                provider_type=copy.provider_type,
                provider_account_id=copy.provider_account_id,
                provider_calendar_id=copy.provider_calendar_id,
                visibility_state=copy.event_visibility_state,
                is_preferred=copy.id == preferred_copy.id,
            )
            for copy in copies
        ],
        preferred_copy_id=preferred_copy.id,
        preferred_reason=_describe_preference(event=event, preferred_copy=preferred_copy),
        latest_sync=latest_sync,
    )


def _latest_sync_log(session: Session, event: Event) -> SyncLog | None:
    if event.provider_account_pk:
        return session.scalar(
            select(SyncLog)
            .where(SyncLog.provider_account_pk == event.provider_account_pk)
            .order_by(SyncLog.started_at.desc(), SyncLog.id.desc())
        )

    return session.scalar(
        select(SyncLog)
        .where(SyncLog.provider_type == event.provider_type)
        .order_by(SyncLog.started_at.desc(), SyncLog.id.desc())
    )


def _describe_preference(*, event: Event, preferred_copy: Event) -> str:
    if event.id != preferred_copy.id:
        if event.duplicate_visibility_override and event.event_visibility_state == "active":
            return "This copy is also visible because you chose to show all copies for this appointment."
        return "This copy is currently not the preferred one for the combined calendar."

    if event.duplicate_visibility_override:
        return "This copy stays visible because you asked CalSync to keep all duplicate copies visible."
    if event.location or event.description:
        return "This copy is preferred because it carries the clearest appointment details."
    if event.provider_type == "google":
        return "This copy is preferred because Google copies currently rank highest when details are otherwise equal."
    if event.provider_type == "icloud_caldav":
        return "This copy is preferred because it is the best remaining iCloud match for this appointment."
    return "This copy is preferred based on the current duplicate grouping rules."
