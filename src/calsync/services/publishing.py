from __future__ import annotations

from secrets import token_urlsafe

from icalendar import Calendar, Event as IcsEvent
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from calsync.models import Event, ProviderCalendar, PublishedFeed, utcnow
from calsync.repos.publishing import (
    get_active_published_feed_by_token,
    get_published_feed_by_scope,
    get_published_feed_by_token,
)


COMBINED_FEED_SCOPE_TYPE = "combined"
COMBINED_FEED_SCOPE_KEY = "all"


def ensure_combined_feed(session: Session) -> PublishedFeed:
    feed = get_published_feed_by_scope(
        session,
        scope_type=COMBINED_FEED_SCOPE_TYPE,
        scope_key=COMBINED_FEED_SCOPE_KEY,
    )
    if feed is None:
        feed = PublishedFeed(
            scope_type=COMBINED_FEED_SCOPE_TYPE,
            scope_key=COMBINED_FEED_SCOPE_KEY,
            token=_generate_feed_token(session),
            is_active=True,
        )
        session.add(feed)
    elif not feed.is_active:
        feed.is_active = True

    session.flush()
    return feed


def rotate_combined_feed_token(session: Session) -> PublishedFeed:
    feed = ensure_combined_feed(session)
    feed.token = _generate_feed_token(session)
    feed.rotated_at = utcnow()
    feed.is_active = True
    session.flush()
    return feed


def render_feed_for_token(session: Session, token: str) -> str:
    feed = get_active_published_feed_by_token(session, token=token)
    if feed is None:
        raise LookupError("Published feed not found.")

    if (
        feed.scope_type != COMBINED_FEED_SCOPE_TYPE
        or feed.scope_key != COMBINED_FEED_SCOPE_KEY
    ):
        raise LookupError("Published feed scope is not supported.")

    calendar = Calendar()
    calendar.add("prodid", "-//CalSync//Read-Only Feed//EN")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("method", "PUBLISH")
    calendar.add("x-wr-calname", "CalSync Combined")

    for event in _list_combined_feed_events(session):
        calendar.add_component(_build_ics_event(event))

    return calendar.to_ical().decode("utf-8")


def _generate_feed_token(session: Session) -> str:
    for _ in range(10):
        token = token_urlsafe(32)
        if get_published_feed_by_token(session, token=token) is None:
            return token
    raise RuntimeError("Unable to allocate a unique feed token.")


def _list_combined_feed_events(session: Session) -> list[Event]:
    return list(
        session.scalars(
            select(Event)
            .outerjoin(ProviderCalendar, Event.provider_calendar_pk == ProviderCalendar.id)
            .where(
                or_(
                    Event.provider_calendar_pk.is_(None),
                    ProviderCalendar.enabled.is_(True),
                )
            )
            .order_by(Event.starts_at, Event.id)
        )
    )


def _build_ics_event(event: Event) -> IcsEvent:
    ics_event = IcsEvent()
    ics_event.add(
        "uid",
        (
            f"{event.provider_type}-"
            f"{event.provider_account_id}-"
            f"{event.provider_calendar_id}-"
            f"{event.provider_event_id}@calsync.local"
        ),
    )
    ics_event.add("summary", event.title)
    if event.description:
        ics_event.add("description", event.description)
    if event.location:
        ics_event.add("location", event.location)
    if event.all_day:
        ics_event.add("dtstart", event.starts_at.date())
        ics_event.add("dtend", event.ends_at.date())
    else:
        ics_event.add("dtstart", event.starts_at)
        ics_event.add("dtend", event.ends_at)
    ics_event.add("dtstamp", event.updated_at)
    ics_event.add("status", event.status.upper())
    return ics_event
