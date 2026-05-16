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
VALID_FLIGHTBOARD_VIEWS = {"day": timedelta(days=1), "week": timedelta(days=7), "month": timedelta(days=31)}


def _flightboard_now() -> datetime:
    return datetime.now(UTC)


def _resolve_board_timezone(timezone_name: str | None) -> ZoneInfo:
    if timezone_name:
        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            return ZoneInfo("UTC")
    return ZoneInfo("UTC")


def _status_for_event(
    starts_at: datetime,
    ends_at: datetime,
    now: datetime,
    timezone: ZoneInfo,
) -> tuple[str, str]:
    local_start = starts_at.astimezone(timezone)
    local_now = now.astimezone(timezone)
    local_end = ends_at.astimezone(timezone)
    if local_start <= local_now < local_end:
        return ("Now", "now")
    if local_start.date() == local_now.date():
        return ("Today", "today")
    if local_start <= local_now + timedelta(days=2):
        return ("Soon", "soon")
    return ("Later", "later")


def _format_board_time(starts_at: datetime, timezone: ZoneInfo) -> str:
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
    timezone = _resolve_board_timezone(timezone_name)
    status_label, status_tone = _status_for_event(
        event.starts_at,
        event.ends_at,
        now,
        timezone,
    )
    return {
        "title": event.title,
        "account_name": account_name or "Connected account",
        "calendar_name": calendar_name or "Unnamed calendar",
        "location": event.location or "Location pending",
        "starts_at_label": _format_board_time(event.starts_at, timezone),
        "status_label": status_label,
        "status_tone": status_tone,
    }


def _resolve_flightboard_view(view_name: str | None) -> str:
    if view_name in VALID_FLIGHTBOARD_VIEWS:
        return view_name
    return "week"


def _build_view_options(active_view: str) -> list[dict[str, str]]:
    labels = {
        "day": "Day",
        "week": "Week",
        "month": "Month",
    }
    return [
        {
            "value": value,
            "label": labels[value],
            "href": f"/admin/flightboard?view={value}",
            "active_class": " flightboard-view-toggle--active" if value == active_view else "",
            "aria_current": "page" if value == active_view else "",
        }
        for value in ("day", "week", "month")
    ]


def _summarize_view(active_view: str) -> str:
    if active_view == "day":
        return "Upcoming activity in the next 24 hours."
    if active_view == "month":
        return "Upcoming activity in the next 31 days."
    return "Upcoming activity in the next 7 days."


@router.get("/flightboard", response_class=HTMLResponse)
def flightboard_page(
    request: Request,
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
    view: str | None = None,
) -> HTMLResponse:
    now = _flightboard_now()
    active_view = _resolve_flightboard_view(view)
    horizon_end = now + VALID_FLIGHTBOARD_VIEWS[active_view]
    events = session.execute(
        select(
            Event,
            ProviderAccount.display_name,
            ProviderCalendar.name,
            ProviderCalendar.timezone,
        )
        .join(ProviderAccount, Event.provider_account_pk == ProviderAccount.id)
        .join(ProviderCalendar, Event.provider_calendar_pk == ProviderCalendar.id)
        .where(ProviderCalendar.enabled.is_(True), Event.ends_at > now, Event.starts_at < horizon_end)
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
            "view_options": _build_view_options(active_view),
            "active_view": active_view,
            "view_summary": _summarize_view(active_view),
        },
    )
