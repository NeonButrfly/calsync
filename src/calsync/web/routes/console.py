from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from calsync.schemas.appointments import CreateAppointmentRequest, UpdateAppointmentRequest
from calsync.services.apple_caldav import AppleCalDAVError
from calsync.services.appointments import AppointmentService


router = APIRouter(tags=["console"])

_templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)
_templates.env.filters["console_datetime"] = lambda value: _format_console_datetime(value)


@router.get("/privacy")
def privacy_page(request: Request):
    return _templates.TemplateResponse(
        request,
        "privacy.html",
        {
            "request": request,
        },
    )


@router.get("/terms")
def terms_page(request: Request):
    return _templates.TemplateResponse(
        request,
        "terms.html",
        {
            "request": request,
        },
    )


@router.get("/")
def scheduling_console(
    request: Request,
    created: str | None = None,
    updated: str | None = None,
    cancelled: str | None = None,
):
    service = AppointmentService()
    appointments = service.list_range(
        date_from=_today_in_alaska().isoformat(),
        date_to=(_today_in_alaska() + timedelta(days=30)).isoformat(),
    ).items
    return _templates.TemplateResponse(
        request,
        "console.html",
        _build_console_context(
            request,
            service=service,
            appointments=appointments,
            flash_message=_flash_message(created, updated, cancelled),
            error_message=None,
            form_values=_empty_form_values(),
        ),
    )


@router.post("/appointments")
def create_appointment_from_console(
    request: Request,
    title: str = Form(...),
    date_value: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    timezone: str = Form(...),
    location: str = Form(""),
    notes: str = Form(""),
    attendees_text: str = Form(""),
    all_day: bool = Form(False),
):
    payload = CreateAppointmentRequest(
        title=title,
        date=date_value,
        start_time=start_time,
        end_time=end_time,
        timezone=timezone,
        location=location or None,
        notes=notes or None,
        attendees_text=attendees_text or None,
        all_day=all_day,
    )
    service = AppointmentService()
    try:
        service.create(payload, actor="console")
        return RedirectResponse(url="/?created=1", status_code=303)
    except (AppleCalDAVError, ValueError) as exc:
        appointments = service.list_range(
            date_from=_today_in_alaska().isoformat(),
            date_to=(_today_in_alaska() + timedelta(days=30)).isoformat(),
        ).items
        return _templates.TemplateResponse(
            request,
            "console.html",
            _build_console_context(
                request,
                service=service,
                appointments=appointments,
                flash_message=None,
                error_message=str(exc),
                form_values={
                    "title": title,
                    "date": date_value,
                    "start_time": start_time,
                    "end_time": end_time,
                    "timezone": timezone,
                    "location": location,
                    "notes": notes,
                    "attendees_text": attendees_text,
                    "all_day": all_day,
                },
            ),
            status_code=400,
        )


@router.get("/appointments/{appointment_id}/edit")
def edit_appointment_page(appointment_id: str, request: Request):
    service = AppointmentService()
    try:
        appointment = service.get(appointment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _templates.TemplateResponse(
        request,
        "appointment_edit.html",
        {
            "request": request,
            "appointment": appointment,
            "form_values": {
                "title": appointment.title,
                "date": appointment.date,
                "start_time": appointment.start_time,
                "end_time": appointment.end_time,
                "timezone": appointment.timezone,
                "location": appointment.location or "",
                "notes": appointment.notes or "",
                "attendees_text": appointment.attendees_text or "",
                "all_day": appointment.all_day,
            },
            "error_message": None,
        },
    )


@router.post("/appointments/{appointment_id}/edit")
def edit_appointment_from_console(
    appointment_id: str,
    request: Request,
    title: str = Form(...),
    date_value: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    timezone: str = Form(...),
    location: str = Form(""),
    notes: str = Form(""),
    attendees_text: str = Form(""),
    all_day: bool = Form(False),
):
    payload = UpdateAppointmentRequest(
        title=title,
        date=date_value,
        start_time=start_time,
        end_time=end_time,
        timezone=timezone,
        location=location or None,
        notes=notes or None,
        attendees_text=attendees_text or None,
        all_day=all_day,
    )
    service = AppointmentService()
    try:
        service.update(appointment_id, payload)
        return RedirectResponse(url="/?updated=1", status_code=303)
    except ValueError as exc:
        if "not found" in str(exc).lower():
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        appointment = service.get(appointment_id)
        return _templates.TemplateResponse(
            request,
            "appointment_edit.html",
            {
                "request": request,
                "appointment": appointment,
                "form_values": {
                    "title": title,
                    "date": date_value,
                    "start_time": start_time,
                    "end_time": end_time,
                    "timezone": timezone,
                    "location": location,
                    "notes": notes,
                    "attendees_text": attendees_text,
                    "all_day": all_day,
                },
                "error_message": str(exc),
            },
            status_code=400,
        )
    except AppleCalDAVError as exc:
        appointment = service.get(appointment_id)
        return _templates.TemplateResponse(
            request,
            "appointment_edit.html",
            {
                "request": request,
                "appointment": appointment,
                "form_values": {
                    "title": title,
                    "date": date_value,
                    "start_time": start_time,
                    "end_time": end_time,
                    "timezone": timezone,
                    "location": location,
                    "notes": notes,
                    "attendees_text": attendees_text,
                    "all_day": all_day,
                },
                "error_message": str(exc),
            },
            status_code=400,
        )


@router.post("/appointments/{appointment_id}/cancel")
def cancel_appointment_from_console(appointment_id: str):
    service = AppointmentService()
    try:
        service.cancel(appointment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RedirectResponse(url="/?cancelled=1", status_code=303)


def _today_in_alaska() -> date:
    return datetime.now(UTC).astimezone(ZoneInfo("America/Anchorage")).date()


def _build_console_context(
    request: Request,
    *,
    service: AppointmentService,
    appointments,
    flash_message: str | None,
    error_message: str | None,
    form_values: dict[str, object],
) -> dict[str, object]:
    return {
        "request": request,
        "appointments": appointments,
        "flash_message": flash_message,
        "error_message": error_message,
        "form_values": form_values,
        "appointment_count": len(appointments),
        "active_count": sum(1 for item in appointments if item.status == "active"),
        "cancelled_count": sum(1 for item in appointments if item.status == "cancelled"),
        "calendar_label": service.settings.apple_primary_calendar_name,
        "account_label": service.settings.apple_account_label,
    }


def _flash_message(
    created: str | None,
    updated: str | None,
    cancelled: str | None,
) -> str | None:
    if created:
        return "Appointment created on your Apple calendar."
    if updated:
        return "Appointment updated on your Apple calendar."
    if cancelled:
        return "Appointment cancelled on your Apple calendar."
    return None


def _empty_form_values() -> dict[str, object]:
    next_day = _today_in_alaska() + timedelta(days=1)
    return {
        "title": "",
        "date": next_day.isoformat(),
        "start_time": "10:00",
        "end_time": "11:00",
        "timezone": "America/Anchorage",
        "location": "",
        "notes": "",
        "attendees_text": "",
        "all_day": False,
    }


def _format_console_datetime(value: str) -> str:
    return value
