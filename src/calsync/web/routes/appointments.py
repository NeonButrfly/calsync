from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from calsync.models import AdminUser
from calsync.services.appointments import (
    cancel_writable_appointment,
    create_writable_appointment,
    event_local_input_defaults,
    list_writable_calendar_options,
    parse_local_datetime_input,
    require_writable_event,
    update_writable_appointment,
)
from calsync.web.deps import get_db, get_templates, require_admin
from calsync.web.timezones import ALASKA_TIMEZONE


router = APIRouter(prefix="/admin")


@router.get("/appointments/new")
def create_appointment_page(
    request: Request,
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
):
    writable_calendars = list_writable_calendar_options(session)
    return templates.TemplateResponse(
        request,
        "appointment_form.html",
        {
            "current_admin": current_admin,
            "page_mode": "create",
            "writable_calendars": writable_calendars,
            "selected_calendar_pk": writable_calendars[0].calendar_pk if writable_calendars else None,
            "form_values": {
                "title": "",
                "description": "",
                "location": "",
                "starts_at_local": "",
                "ends_at_local": "",
                "all_day": False,
            },
            "error_text": None,
            "event_id": None,
        },
    )


@router.post("/appointments/new")
def create_appointment_action(
    request: Request,
    calendar_pk: str = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    location: str = Form(""),
    starts_at_local: str = Form(...),
    ends_at_local: str = Form(...),
    all_day: bool = Form(False),
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
):
    writable_calendars = list_writable_calendar_options(session)
    try:
        event_input = parse_local_datetime_input(
            title=title,
            description=description,
            location=location,
            starts_at_local=starts_at_local,
            ends_at_local=ends_at_local,
            all_day=all_day,
            display_timezone=ALASKA_TIMEZONE,
        )
        created_event = create_writable_appointment(
            session,
            calendar_pk=calendar_pk,
            event_input=event_input,
            settings=request.app.state.settings,
        )
        session.commit()
        return RedirectResponse(url=f"/admin/events/{created_event.id}", status_code=303)
    except (LookupError, ValueError) as exc:
        session.rollback()
        return templates.TemplateResponse(
            request,
            "appointment_form.html",
            {
                "current_admin": current_admin,
                "page_mode": "create",
                "writable_calendars": writable_calendars,
                "selected_calendar_pk": calendar_pk,
                "form_values": {
                    "title": title,
                    "description": description,
                    "location": location,
                    "starts_at_local": starts_at_local,
                    "ends_at_local": ends_at_local,
                    "all_day": all_day,
                },
                "error_text": str(exc),
                "event_id": None,
            },
            status_code=400,
        )


@router.get("/events/{event_id}/edit")
def edit_appointment_page(
    event_id: str,
    request: Request,
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
):
    try:
        event = require_writable_event(session, event_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    writable_calendars = list_writable_calendar_options(session)
    return templates.TemplateResponse(
        request,
        "appointment_form.html",
        {
            "current_admin": current_admin,
            "page_mode": "edit",
            "writable_calendars": writable_calendars,
            "selected_calendar_pk": event.provider_calendar_pk,
            "form_values": event_local_input_defaults(event),
            "error_text": None,
            "event_id": event.id,
        },
    )


@router.post("/events/{event_id}/edit")
def edit_appointment_action(
    event_id: str,
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    location: str = Form(""),
    starts_at_local: str = Form(...),
    ends_at_local: str = Form(...),
    all_day: bool = Form(False),
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
):
    writable_calendars = list_writable_calendar_options(session)
    try:
        event_input = parse_local_datetime_input(
            title=title,
            description=description,
            location=location,
            starts_at_local=starts_at_local,
            ends_at_local=ends_at_local,
            all_day=all_day,
            display_timezone=ALASKA_TIMEZONE,
        )
        updated_event = update_writable_appointment(
            session,
            event_id=event_id,
            event_input=event_input,
            settings=request.app.state.settings,
        )
        session.commit()
        return RedirectResponse(url=f"/admin/events/{updated_event.id}", status_code=303)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        session.rollback()
        return templates.TemplateResponse(
            request,
            "appointment_form.html",
            {
                "current_admin": current_admin,
                "page_mode": "edit",
                "writable_calendars": writable_calendars,
                "selected_calendar_pk": None,
                "form_values": {
                    "title": title,
                    "description": description,
                    "location": location,
                    "starts_at_local": starts_at_local,
                    "ends_at_local": ends_at_local,
                    "all_day": all_day,
                },
                "error_text": str(exc),
                "event_id": event_id,
            },
            status_code=400,
        )


@router.post("/events/{event_id}/cancel")
def cancel_appointment_action(
    event_id: str,
    request: Request,
    session: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    try:
        cancelled_event = cancel_writable_appointment(
            session,
            event_id=event_id,
            settings=request.app.state.settings,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.commit()
    return RedirectResponse(url=f"/admin/events/{cancelled_event.id}", status_code=303)
