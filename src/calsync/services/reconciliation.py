from __future__ import annotations

from dataclasses import dataclass
import re

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from calsync.models import Event, EventGroup, ProviderCalendar


VISIBLE_RECONCILIATION_STATES = frozenset({"active", "hidden_duplicate"})


@dataclass
class DuplicateGroupView:
    group: EventGroup
    events: list[Event]


def rebuild_duplicate_groups(session: Session) -> list[EventGroup]:
    candidate_events = _list_candidate_events(session)

    for event in candidate_events:
        event.canonical_group_id = None

    session.execute(delete(EventGroup))
    session.flush()

    grouped_events: dict[tuple[str, bool, object, object], list[Event]] = {}
    for event in candidate_events:
        key = (
            _normalize_title(event.title),
            event.all_day,
            event.starts_at,
            event.ends_at,
        )
        grouped_events.setdefault(key, []).append(event)

    created_groups: list[EventGroup] = []
    for events in grouped_events.values():
        ordered_events = sorted(events, key=_event_sort_key)
        if len(ordered_events) == 1:
            lone_event = ordered_events[0]
            if lone_event.event_visibility_state == "hidden_duplicate":
                lone_event.event_visibility_state = "active"
            continue

        preferred_event = max(ordered_events, key=_preferred_event_score)
        group = EventGroup(
            display_title=preferred_event.title,
            preferred_starts_at=preferred_event.starts_at,
            preferred_ends_at=preferred_event.ends_at,
            preferred_location=preferred_event.location,
        )
        session.add(group)
        session.flush()

        group.preferred_event_id = preferred_event.id
        for event in ordered_events:
            event.canonical_group_id = group.id
            if event.id == preferred_event.id and event.event_visibility_state == "hidden_duplicate":
                event.event_visibility_state = "active"
        created_groups.append(group)

    session.flush()
    return created_groups


def list_duplicate_groups(session: Session) -> list[DuplicateGroupView]:
    groups = session.scalars(
        select(EventGroup).order_by(EventGroup.preferred_starts_at, EventGroup.display_title, EventGroup.id)
    ).all()

    duplicate_groups: list[DuplicateGroupView] = []
    for group in groups:
        events = session.scalars(
            select(Event)
            .where(Event.canonical_group_id == group.id)
            .order_by(Event.starts_at, Event.provider_type, Event.provider_account_id, Event.provider_event_id)
        ).all()
        if len(events) < 2:
            continue
        duplicate_groups.append(
            DuplicateGroupView(
                group=group,
                events=sorted(events, key=lambda event: (event.id != group.preferred_event_id, *_event_sort_key(event))),
            )
        )
    return duplicate_groups


def prefer_event_in_group(session: Session, group_id: str, preferred_event_id: str) -> EventGroup:
    group = session.get(EventGroup, group_id)
    if group is None:
        raise LookupError(f"Duplicate group not found: {group_id}")

    events = session.scalars(select(Event).where(Event.canonical_group_id == group_id)).all()
    if not events:
        raise LookupError(f"Duplicate group has no events: {group_id}")

    selected = next((event for event in events if event.id == preferred_event_id), None)
    if selected is None:
        raise LookupError(f"Event {preferred_event_id} is not part of duplicate group {group_id}")

    for event in events:
        if event.id == preferred_event_id:
            event.event_visibility_state = "active"
        elif event.event_visibility_state in VISIBLE_RECONCILIATION_STATES:
            event.event_visibility_state = "hidden_duplicate"

    group.preferred_event_id = preferred_event_id
    group.display_title = selected.title
    group.preferred_starts_at = selected.starts_at
    group.preferred_ends_at = selected.ends_at
    group.preferred_location = selected.location
    session.flush()
    return group


def restore_hidden_duplicate(session: Session, event_id: str) -> Event:
    event = session.get(Event, event_id)
    if event is None:
        raise LookupError(f"Event not found: {event_id}")
    if event.event_visibility_state != "hidden_duplicate":
        raise ValueError("Only hidden duplicate events can be restored.")
    event.event_visibility_state = "active"
    session.flush()
    return event


def collect_trust_metrics(session: Session) -> dict[str, int]:
    return {
        "duplicate_groups": len(list_duplicate_groups(session)),
        "hidden_duplicates": _count_events_in_state(session, "hidden_duplicate"),
        "deleted_upstream": _count_events_in_state(session, "deleted_upstream"),
        "cancelled": _count_events_in_state(session, "cancelled"),
        "stale_unverified": _count_events_in_state(session, "stale_unverified"),
    }


def _list_candidate_events(session: Session) -> list[Event]:
    return session.scalars(
        select(Event)
        .outerjoin(ProviderCalendar, Event.provider_calendar_pk == ProviderCalendar.id)
        .where(
            Event.event_visibility_state.in_(VISIBLE_RECONCILIATION_STATES),
            or_(
                Event.provider_calendar_pk.is_(None),
                ProviderCalendar.enabled.is_(True),
            ),
        )
        .order_by(Event.starts_at, Event.provider_type, Event.provider_account_id, Event.provider_event_id)
    ).all()


def _normalize_title(title: str) -> str:
    normalized = re.sub(r"\s+", " ", title.casefold()).strip()
    return normalized


def _preferred_event_score(event: Event) -> tuple[int, int, int, int, tuple[object, ...]]:
    return (
        1 if event.event_visibility_state == "active" else 0,
        1 if event.location else 0,
        1 if event.description else 0,
        _provider_priority(event.provider_type),
        tuple(_event_sort_key(event)),
    )


def _provider_priority(provider_type: str) -> int:
    return {
        "google": 3,
        "icloud_caldav": 2,
        "mock": 1,
    }.get(provider_type, 0)


def _event_sort_key(event: Event) -> tuple[object, ...]:
    return (
        event.starts_at,
        event.provider_type,
        event.provider_account_id,
        event.provider_calendar_id,
        event.provider_event_id,
        event.id,
    )


def _count_events_in_state(session: Session, state: str) -> int:
    return len(
        session.scalars(
            select(Event.id).where(Event.event_visibility_state == state)
        ).all()
    )
