from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from calsync.models import AdminUser, ProviderAccount, ProviderCalendar
from calsync.web.deps import get_db, get_templates, require_admin


router = APIRouter(prefix="/admin/calendars")


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
