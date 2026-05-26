from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from calsync.models import (
    AdminUser,
    CALENDAR_ROLE_AVAILABILITY_ONLY,
    CALENDAR_ROLE_CONFLICT_ONLY,
    CALENDAR_ROLE_HIDDEN,
    CALENDAR_ROLE_PERSONAL_REFERENCE,
    CALENDAR_ROLE_WRITABLE_BOOKING_TARGET,
    ProviderAccount,
    ProviderCalendar,
)
from calsync.repos.providers import (
    hydrate_provider_account_capabilities,
    provider_calendar_supports_write,
    set_provider_calendar_role,
)
from calsync.services.source_labels import compact_identifier
from calsync.web.deps import get_db, get_templates, require_admin


router = APIRouter(prefix="/admin/calendars")

CALENDAR_ROLE_OPTIONS = (
    (CALENDAR_ROLE_AVAILABILITY_ONLY, "Check availability"),
    (CALENDAR_ROLE_CONFLICT_ONLY, "Conflict checking only"),
    (CALENDAR_ROLE_WRITABLE_BOOKING_TARGET, "Receive new bookings"),
    (CALENDAR_ROLE_PERSONAL_REFERENCE, "Personal reference"),
    (CALENDAR_ROLE_HIDDEN, "Hidden"),
)

CALENDAR_ROLE_HELP = {
    CALENDAR_ROLE_AVAILABILITY_ONLY: "Check availability helps CalSync avoid collisions while keeping the calendar read-only.",
    CALENDAR_ROLE_CONFLICT_ONLY: "Conflict checking only watches this calendar for overlaps without using it as a preferred personal source.",
    CALENDAR_ROLE_WRITABLE_BOOKING_TARGET: "Receive new bookings means CalSync can write new appointments here when provider write-back is supported.",
    CALENDAR_ROLE_PERSONAL_REFERENCE: "Personal reference keeps the calendar visible for context without using it for booking writes.",
    CALENDAR_ROLE_HIDDEN: "Hidden keeps the calendar connected but removes it from normal scheduling views.",
}


def _calendar_role_options_for_calendar(
    account: ProviderAccount,
    calendar: ProviderCalendar,
) -> tuple[tuple[str, str], ...]:
    if account.can_write and provider_calendar_supports_write(account, calendar):
        return CALENDAR_ROLE_OPTIONS
    return tuple(
        option
        for option in CALENDAR_ROLE_OPTIONS
        if option[0] != CALENDAR_ROLE_WRITABLE_BOOKING_TARGET
    )


@router.get("")
def calendars_page(
    request: Request,
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
):
    accounts = session.scalars(
        select(ProviderAccount)
        .options(selectinload(ProviderAccount.calendars))
        .order_by(ProviderAccount.display_name, ProviderAccount.provider_account_id)
    ).all()
    for account in accounts:
        hydrate_provider_account_capabilities(account)
    return templates.TemplateResponse(
        request,
        "calendars.html",
        {
            "current_admin": current_admin,
            "accounts": accounts,
            "calendar_role_help": CALENDAR_ROLE_HELP,
            "calendar_role_options_by_calendar": {
                calendar.id: _calendar_role_options_for_calendar(account, calendar)
                for account in accounts
                for calendar in account.calendars
            },
            "provider_names": {
                "google": "Google",
                "icloud_caldav": "Apple Calendar",
                "microsoft": "Outlook / Microsoft 365",
                "mock": "Mock provider",
            },
            "compact_identifier": compact_identifier,
        },
    )


@router.post("/{calendar_id}/toggle")
def toggle_calendar(
    calendar_id: str,
    session: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    calendar = session.get(ProviderCalendar, calendar_id)
    if calendar is None:
        raise HTTPException(status_code=404, detail="Calendar not found.")

    calendar.enabled = not calendar.enabled
    session.add(calendar)
    session.commit()
    return RedirectResponse(url="/admin/calendars", status_code=303)


@router.post("/{calendar_id}/role")
def update_calendar_role(
    calendar_id: str,
    calendar_role: str = Form(...),
    session: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    calendar = session.get(ProviderCalendar, calendar_id)
    if calendar is None:
        raise HTTPException(status_code=404, detail="Calendar not found.")

    try:
        set_provider_calendar_role(
            session,
            calendar=calendar,
            calendar_role=calendar_role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session.commit()
    return RedirectResponse(url="/admin/calendars", status_code=303)
