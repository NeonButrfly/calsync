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
from calsync.repos.providers import set_provider_calendar_role
from calsync.web.deps import get_db, get_templates, require_admin


router = APIRouter(prefix="/admin/calendars")

CALENDAR_ROLE_OPTIONS = (
    (CALENDAR_ROLE_AVAILABILITY_ONLY, "Check availability"),
    (CALENDAR_ROLE_CONFLICT_ONLY, "Conflict checking only"),
    (CALENDAR_ROLE_WRITABLE_BOOKING_TARGET, "Receive new bookings"),
    (CALENDAR_ROLE_PERSONAL_REFERENCE, "Personal reference"),
    (CALENDAR_ROLE_HIDDEN, "Hidden"),
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
    return templates.TemplateResponse(
        request,
        "calendars.html",
        {
            "current_admin": current_admin,
            "accounts": accounts,
            "calendar_role_options": CALENDAR_ROLE_OPTIONS,
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
