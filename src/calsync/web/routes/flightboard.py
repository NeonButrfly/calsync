from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from calsync.models import AdminUser, Event, ProviderAccount, ProviderCalendar
from calsync.web.deps import get_db, get_templates, require_admin


router = APIRouter(prefix="/admin")


def _flightboard_now() -> datetime:
    return datetime.now(UTC)


def _status_for_event(starts_at: datetime, now: datetime) -> tuple[str, str]:
    if starts_at < now and starts_at.date() < now.date():
        return ("Complete", "complete")
    if starts_at.date() == now.date():
        return ("Now", "now")
    if starts_at <= now + timedelta(days=2):
        return ("Soon", "soon")
    return ("Later", "later")


def _format_board_time(starts_at: datetime, timezone_name: str | None) -> str:
    timezone = UTC
    if timezone_name:
        try:
            timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            timezone = UTC

    local_start = starts_at.astimezone(timezone)
    time_text = local_start.strftime("%I:%M %p").lstrip("0") or "12:00 AM"
    timezone_label = local_start.tzname() or "UTC"
    return (
        f"{local_start.strftime('%a')} {local_start.strftime('%b')} "
        f"{local_start.day} at {time_text} {timezone_label}"
    )


def _serialize_board_row(
    event: Event,
    account_name: str | None,
    calendar_name: str | None,
    timezone_name: str | None,
    now: datetime,
) -> dict[str, str]:
    status_label, status_tone = _status_for_event(event.starts_at, now)
    return {
        "title": event.title,
        "account_name": account_name or "Connected account",
        "calendar_name": calendar_name or "Unnamed calendar",
        "location": event.location or "Location pending",
        "starts_at_label": _format_board_time(event.starts_at, timezone_name),
        "status_label": status_label,
        "status_tone": status_tone,
    }


@router.get("/flightboard", response_class=HTMLResponse)
def flightboard_page(
    request: Request,
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
) -> HTMLResponse:
    now = _flightboard_now()
    events = session.execute(
        select(
            Event,
            ProviderAccount.display_name,
            ProviderCalendar.name,
            ProviderCalendar.timezone,
        )
        .join(ProviderAccount, Event.provider_account_pk == ProviderAccount.id)
        .join(ProviderCalendar, Event.provider_calendar_pk == ProviderCalendar.id)
        .where(ProviderCalendar.enabled.is_(True))
        .order_by(Event.starts_at, Event.id)
    ).all()

    return templates.TemplateResponse(
        request,
        "flightboard.html",
        {
            "current_admin": current_admin,
            "board_rows": [
                _serialize_board_row(
                    event,
                    account_name,
                    calendar_name,
                    timezone_name,
                    now,
                )
                for event, account_name, calendar_name, timezone_name in events
            ],
        },
    )
