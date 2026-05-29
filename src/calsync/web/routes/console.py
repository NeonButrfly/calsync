from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from importlib.resources import files
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo
from zipfile import ZipFile

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import SQLAlchemyError

from calsync.schemas.appointments import (
    AppointmentDetailResponse,
    AppointmentListItem,
    CreateAppointmentRequest,
    UpdateAppointmentRequest,
)
from calsync.services.apple_caldav import AppleCalDAVError
from calsync.services.alexa_simulator import AlexaSimulatorService
from calsync.services.appointments import AppointmentService
from calsync.services.apple_runtime_config import AppleRuntimeConfigService
from calsync.services.cloudflare_worker_config import CloudflareWorkerConfigService
from calsync.services.operator_settings import OperatorSettingsService
from calsync.services.readiness import ReadinessService


router = APIRouter(tags=["console"])

_templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)

_WINDOWS: dict[str, tuple[str, int]] = {
    "day": ("Today", 0),
    "week": ("Next 7 days", 6),
    "month": ("Next 30 days", 29),
}


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


@router.get("/alexa/setup")
def alexa_setup_page(request: Request):
    readiness = ReadinessService().build()
    edge_settings = CloudflareWorkerConfigService().get_alexa_settings()
    cloudflare_credentials = OperatorSettingsService().describe_cloudflare_worker_credentials()
    return _templates.TemplateResponse(
        request,
        "alexa_setup.html",
        {
            "request": request,
            "readiness": readiness,
            "edge_settings": edge_settings,
            "cloudflare_credentials": cloudflare_credentials,
            "alexa_endpoint": "https://edge-calsync.neonbutterfly.net/alexa",
            "privacy_url": "https://calsync.neonbutterfly.net/privacy",
            "terms_url": "https://calsync.neonbutterfly.net/terms",
            "simulator_url": "/alexa/simulator",
            "flash_message": None,
            "error_message": None,
        },
    )


@router.get("/calendar/setup")
def calendar_setup_page(request: Request):
    apple_settings = OperatorSettingsService().describe_apple_calendar_settings()
    runtime_service = AppleRuntimeConfigService()
    runtime_config = runtime_service.resolve()
    return _templates.TemplateResponse(
        request,
        "calendar_setup.html",
        {
            "request": request,
            "apple_settings": apple_settings,
            "runtime_config": runtime_config,
            "calendar_catalog": runtime_service.list_calendars(),
            "flash_message": None,
            "error_message": None,
        },
    )


@router.post("/calendar/setup")
def calendar_setup_update(
    request: Request,
    apple_account_label: str = Form(""),
    apple_username: str = Form(""),
    apple_app_specific_password: str = Form(""),
    apple_primary_calendar_url: str = Form(""),
    apple_primary_calendar_name: str = Form(""),
):
    operator_settings = OperatorSettingsService()
    try:
        operator_settings.set_apple_calendar_settings(
            account_label=apple_account_label,
            username=apple_username,
            app_specific_password=apple_app_specific_password,
            primary_calendar_url=apple_primary_calendar_url,
            primary_calendar_name=apple_primary_calendar_name,
            preserve_existing_password=True,
        )
        flash_message = "Apple calendar settings saved securely."
        error_message = None
    except ValueError as exc:
        flash_message = None
        error_message = str(exc)

    apple_settings = operator_settings.describe_apple_calendar_settings()
    runtime_service = AppleRuntimeConfigService(
        operator_settings=operator_settings
    )
    runtime_config = runtime_service.resolve()
    return _templates.TemplateResponse(
        request,
        "calendar_setup.html",
        {
            "request": request,
            "apple_settings": apple_settings,
            "runtime_config": runtime_config,
            "calendar_catalog": runtime_service.list_calendars(),
            "flash_message": flash_message,
            "error_message": error_message,
        },
        status_code=200 if error_message is None else 400,
    )


@router.post("/calendar/setup/calendars")
def calendar_setup_add_calendar(
    request: Request,
    calendar_name: str = Form(""),
    calendar_url: str = Form(""),
    is_default: str | None = Form(None),
):
    operator_settings = OperatorSettingsService()
    runtime_service = AppleRuntimeConfigService(operator_settings=operator_settings)
    try:
        catalog = operator_settings.get_apple_calendar_catalog()
        if not catalog:
            catalog = runtime_service.list_calendars()
        catalog.append(
            {
                "calendar_name": calendar_name,
                "calendar_url": calendar_url,
                "is_default": is_default == "true",
            }
        )
        operator_settings.set_apple_calendar_catalog(catalog)
        flash_message = "Apple calendar target added."
        error_message = None
    except ValueError as exc:
        flash_message = None
        error_message = str(exc)

    apple_settings = operator_settings.describe_apple_calendar_settings()
    runtime_config = runtime_service.resolve()
    return _templates.TemplateResponse(
        request,
        "calendar_setup.html",
        {
            "request": request,
            "apple_settings": apple_settings,
            "runtime_config": runtime_config,
            "calendar_catalog": runtime_service.list_calendars(),
            "flash_message": flash_message,
            "error_message": error_message,
        },
        status_code=200 if error_message is None else 400,
    )


@router.post("/alexa/setup")
def alexa_setup_update(
    request: Request,
    allowed_skill_ids: str = Form(""),
    enable_alexa: str | None = Form(None),
):
    readiness = ReadinessService().build()
    service = CloudflareWorkerConfigService()
    try:
        edge_settings = service.update_alexa_settings(
            enable_alexa=enable_alexa == "true",
            allowed_skill_ids=[
                value.strip() for value in allowed_skill_ids.split(",") if value.strip()
            ],
        )
        flash_message = "Edge Worker settings updated."
        error_message = None
    except ValueError as exc:
        edge_settings = service.get_alexa_settings()
        flash_message = None
        error_message = str(exc)

    cloudflare_credentials = OperatorSettingsService().describe_cloudflare_worker_credentials()
    return _templates.TemplateResponse(
        request,
        "alexa_setup.html",
        {
            "request": request,
            "readiness": readiness,
            "edge_settings": edge_settings,
            "cloudflare_credentials": cloudflare_credentials,
            "alexa_endpoint": "https://edge-calsync.neonbutterfly.net/alexa",
            "privacy_url": "https://calsync.neonbutterfly.net/privacy",
            "terms_url": "https://calsync.neonbutterfly.net/terms",
            "simulator_url": "/alexa/simulator",
            "flash_message": flash_message,
            "error_message": error_message,
        },
        status_code=200 if error_message is None else 400,
    )


@router.post("/alexa/setup/cloudflare")
def alexa_setup_update_cloudflare_credentials(
    request: Request,
    cloudflare_account_id: str = Form(""),
    cloudflare_api_token: str = Form(""),
):
    readiness = ReadinessService().build()
    operator_settings = OperatorSettingsService()
    try:
        operator_settings.set_cloudflare_worker_credentials(
            account_id=cloudflare_account_id,
            api_token=cloudflare_api_token,
            preserve_existing_token=True,
        )
        flash_message = "Cloudflare Worker credentials saved securely."
        error_message = None
    except ValueError as exc:
        flash_message = None
        error_message = str(exc)

    edge_settings = CloudflareWorkerConfigService().get_alexa_settings()
    cloudflare_credentials = operator_settings.describe_cloudflare_worker_credentials()
    return _templates.TemplateResponse(
        request,
        "alexa_setup.html",
        {
            "request": request,
            "readiness": readiness,
            "edge_settings": edge_settings,
            "cloudflare_credentials": cloudflare_credentials,
            "alexa_endpoint": "https://edge-calsync.neonbutterfly.net/alexa",
            "privacy_url": "https://calsync.neonbutterfly.net/privacy",
            "terms_url": "https://calsync.neonbutterfly.net/terms",
            "simulator_url": "/alexa/simulator",
            "flash_message": flash_message,
            "error_message": error_message,
        },
        status_code=200 if error_message is None else 400,
    )


@router.get("/alexa/simulator")
def alexa_simulator_page(request: Request):
    return _templates.TemplateResponse(
        request,
        "alexa_simulator.html",
        {
            "request": request,
            "simulation_result": None,
            "error_message": None,
            "form_values": _default_alexa_simulator_values(),
        },
    )


@router.post("/alexa/simulator")
def alexa_simulator_run(
    request: Request,
    request_type: str = Form(...),
    intent_name: str = Form(""),
    title: str = Form(""),
    date: str = Form(""),
    start_time: str = Form(""),
    end_time: str = Form(""),
    location: str = Form(""),
    notes: str = Form(""),
    new_date: str = Form(""),
    new_start_time: str = Form(""),
    new_end_time: str = Form(""),
):
    form_values = {
        "request_type": request_type,
        "intent_name": intent_name,
        "title": title,
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "location": location,
        "notes": notes,
        "new_date": new_date,
        "new_start_time": new_start_time,
        "new_end_time": new_end_time,
    }
    slots = {
        "title": title,
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "location": location,
        "notes": notes,
        "new_date": new_date,
        "new_start_time": new_start_time,
        "new_end_time": new_end_time,
    }
    try:
        simulation_result = AlexaSimulatorService().simulate(
            request_type=request_type,
            intent_name=intent_name or None,
            slots=slots,
        )
        error_message = None
    except ValueError as exc:
        simulation_result = None
        error_message = str(exc)

    return _templates.TemplateResponse(
        request,
        "alexa_simulator.html",
        {
            "request": request,
            "simulation_result": simulation_result,
            "error_message": error_message,
            "form_values": form_values,
        },
        status_code=200 if simulation_result is not None else 400,
    )


@router.get("/alexa/skill-package.zip")
def alexa_skill_package_zip() -> StreamingResponse:
    package_root = files("calsync.alexa_setup")
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, "w") as archive:
        archive.writestr(
            "skill-package/skill.json",
            (package_root / "skill-package" / "skill.json").read_text(encoding="utf-8"),
        )
        archive.writestr(
            "skill-package/interactionModels/custom/en-US.json",
            (
                package_root
                / "skill-package"
                / "interactionModels"
                / "custom"
                / "en-US.json"
            ).read_text(encoding="utf-8"),
        )
    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="calsync-alexa-skill-package.zip"'
        },
    )


@router.get("/")
def scheduling_console(
    request: Request,
    created: str | None = None,
    updated: str | None = None,
    cancelled: str | None = None,
    view: str = "week",
    appointment_id: str | None = None,
    show_cancelled: bool = False,
):
    service = AppointmentService()
    readiness = ReadinessService().build()
    date_from, date_to, selected_window = _resolve_window(view)
    try:
        appointments = service.list_range(
            date_from=date_from.isoformat(),
            date_to=date_to.isoformat(),
            include_cancelled=show_cancelled,
        ).items
        selected_detail = _resolve_selected_detail(service, appointments, appointment_id)
        schedule_error = None
    except (AppleCalDAVError, ModuleNotFoundError, SQLAlchemyError, ValueError):
        appointments = []
        selected_detail = None
        schedule_error = "Schedule data is unavailable right now."
    return _templates.TemplateResponse(
        request,
        "console.html",
        _build_console_context(
            request,
            service=service,
            appointments=appointments,
            selected_detail=selected_detail,
            flash_message=_flash_message(created, updated, cancelled),
            error_message=schedule_error,
            form_values=_empty_form_values(),
            selected_window=selected_window,
            show_cancelled=show_cancelled,
            readiness=readiness,
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
    target_calendar_url: str = Form(""),
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
        target_calendar_url=target_calendar_url or None,
        all_day=all_day,
    )
    service = AppointmentService()
    try:
        created = service.create(payload, actor="console")
        return RedirectResponse(
            url=f"/?created=1&view=week&appointment_id={created.appointment_id}",
            status_code=303,
        )
    except (AppleCalDAVError, ValueError) as exc:
        date_from, date_to, selected_window = _resolve_window("week")
        appointments = service.list_range(
            date_from=date_from.isoformat(),
            date_to=date_to.isoformat(),
        ).items
        selected_detail = _resolve_selected_detail(service, appointments, None)
        return _templates.TemplateResponse(
            request,
            "console.html",
            _build_console_context(
                request,
                service=service,
                appointments=appointments,
                selected_detail=selected_detail,
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
                    "target_calendar_url": target_calendar_url,
                    "all_day": all_day,
                },
                selected_window=selected_window,
                show_cancelled=False,
                readiness=ReadinessService().build(),
            ),
            status_code=400,
        )


@router.get("/appointments/{appointment_id}/edit")
def edit_appointment_page(appointment_id: str, request: Request):
    service = AppointmentService()
    try:
        appointment = service.get_detail(appointment_id)
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
                "target_calendar_url": appointment.calendar_url or "",
                "all_day": appointment.all_day,
            },
            "calendar_options": _calendar_options(
                service,
                selected_calendar_url=appointment.calendar_url,
            ),
            "error_message": None,
            "window_options": _window_options(
                selected_window="week",
                show_cancelled=False,
                selected_appointment_id=appointment_id,
            ),
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
    target_calendar_url: str = Form(""),
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
        target_calendar_url=target_calendar_url or None,
        all_day=all_day,
    )
    service = AppointmentService()
    try:
        service.update(appointment_id, payload, actor="console")
        return RedirectResponse(
            url=f"/?updated=1&view=week&appointment_id={appointment_id}",
            status_code=303,
        )
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
                    "target_calendar_url": target_calendar_url,
                    "all_day": all_day,
                },
                "calendar_options": _calendar_options(
                    service,
                    selected_calendar_url=target_calendar_url or None,
                ),
                "error_message": str(exc),
                "window_options": _window_options(
                    selected_window="week",
                    show_cancelled=False,
                    selected_appointment_id=appointment_id,
                ),
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
                    "target_calendar_url": target_calendar_url,
                    "all_day": all_day,
                },
                "calendar_options": _calendar_options(
                    service,
                    selected_calendar_url=target_calendar_url or None,
                ),
                "error_message": str(exc),
                "window_options": _window_options(
                    selected_window="week",
                    show_cancelled=False,
                    selected_appointment_id=appointment_id,
                ),
            },
            status_code=400,
        )


@router.post("/appointments/{appointment_id}/cancel")
def cancel_appointment_from_console(appointment_id: str):
    service = AppointmentService()
    try:
        service.cancel(appointment_id, actor="console")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RedirectResponse(url="/?cancelled=1&view=week", status_code=303)


def _today_in_alaska() -> date:
    return datetime.now(UTC).astimezone(ZoneInfo("America/Anchorage")).date()


def _resolve_window(view: str) -> tuple[date, date, str]:
    selected_window = view if view in _WINDOWS else "week"
    label, day_span = _WINDOWS[selected_window]
    del label
    start = _today_in_alaska()
    return start, start + timedelta(days=day_span), selected_window


def _resolve_selected_detail(
    service: AppointmentService,
    appointments: list[AppointmentListItem],
    appointment_id: str | None,
) -> AppointmentDetailResponse | None:
    selected_appointment_id = appointment_id or (appointments[0].appointment_id if appointments else None)
    if not selected_appointment_id:
        return None
    try:
        return service.get_detail(selected_appointment_id)
    except ValueError:
        return None


def _build_console_context(
    request: Request,
    *,
    service: AppointmentService,
    appointments: list[AppointmentListItem],
    selected_detail: AppointmentDetailResponse | None,
    flash_message: str | None,
    error_message: str | None,
    form_values: dict[str, object],
    selected_window: str,
    show_cancelled: bool,
    readiness: dict[str, object],
) -> dict[str, object]:
    hero_subject = appointments[0] if appointments else None
    return {
        "request": request,
        "flash_message": flash_message,
        "error_message": error_message,
        "reference_message": (
            "Showing cancelled appointments for reference."
            if show_cancelled
            else None
        ),
        "form_values": form_values,
        "calendar_label": service.display_calendar_name,
        "account_label": service.display_account_label,
        "calendar_options": _calendar_options(
            service,
            selected_calendar_url=str(form_values.get("target_calendar_url") or ""),
        ),
        "selected_window": selected_window,
        "show_cancelled": show_cancelled,
        "window_options": _window_options(
            selected_window=selected_window,
            show_cancelled=show_cancelled,
            selected_appointment_id=selected_detail.appointment_id if selected_detail else None,
        ),
        "window_label": _WINDOWS[selected_window][0],
        "window_summary": _window_summary(selected_window),
        "schedule_sections": _build_schedule_sections(
            appointments,
            selected_window=selected_window,
            show_cancelled=show_cancelled,
            selected_appointment_id=selected_detail.appointment_id if selected_detail else None,
        ),
        "selected_appointment": _serialize_detail(selected_detail),
        "appointment_count": len(appointments),
        "active_count": len(appointments),
        "cancelled_count": sum(1 for item in appointments if item.status == "cancelled"),
        "next_up_label": _next_up_label(hero_subject),
        "readiness": readiness,
    }


def _build_schedule_sections(
    appointments: list[AppointmentListItem],
    *,
    selected_window: str,
    show_cancelled: bool,
    selected_appointment_id: str | None,
) -> list[dict[str, object]]:
    sections: list[dict[str, object]] = []
    grouped: dict[str, list[AppointmentListItem]] = {}
    for item in appointments:
        grouped.setdefault(item.date, []).append(item)

    for day, items in grouped.items():
        sections.append(
            {
                "date_label": _friendly_date_label(day),
                "eyebrow": _schedule_eyebrow(day),
                "entries": [
                    {
                        "appointment_id": item.appointment_id,
                        "title": item.title,
                        "status": item.status,
                        "time_label": _time_label(item),
                        "people_label": item.attendees_text,
                        "location_label": item.location,
                        "detail_href": _detail_href(
                            selected_window=selected_window,
                            appointment_id=item.appointment_id,
                            show_cancelled=show_cancelled,
                        ),
                        "is_selected": item.appointment_id == selected_appointment_id,
                    }
                    for item in items
                ],
            }
        )
    return sections


def _serialize_detail(detail: AppointmentDetailResponse | None) -> dict[str, object] | None:
    if detail is None:
        return None
    return {
        "appointment_id": detail.appointment_id,
        "title": detail.title,
        "status": detail.status,
        "date_label": _friendly_date_label(detail.date, include_weekday=True),
        "time_label": _time_label(detail),
        "timezone": detail.timezone,
        "location": detail.location,
        "notes": detail.notes,
        "attendees_text": detail.attendees_text,
        "calendar_name": detail.calendar_name,
        "account_label": detail.account_label,
        "provider_type_label": _provider_label(detail.provider_type),
        "provider_event_id": detail.provider_event_id,
        "provider_href": detail.provider_href,
        "created_label": _friendly_timestamp(detail.created_at),
        "updated_label": _friendly_timestamp(detail.updated_at),
        "audit_entries": [
            {
                "timestamp_label": _friendly_timestamp(item.created_at),
                "actor_label": _actor_label(item.actor),
                "action_label": _action_label(item.action),
                "summary": _audit_summary(item.action, item.payload_json),
            }
            for item in detail.audit_entries
        ],
    }


def _next_up_label(item: AppointmentListItem | None) -> str:
    if item is None:
        return "No appointments in this window yet."
    return f"{item.title} · {_friendly_date_label(item.date, include_weekday=True)} · {_time_label(item)}"


def _window_summary(selected_window: str) -> str:
    if selected_window == "day":
        return "Today only, so you can sanity-check the immediate family schedule."
    if selected_window == "month":
        return "The next 30 days, for a fuller planning view without falling into raw provider clutter."
    return "The next 7 days, for a useful planning horizon that still feels lightweight."


def _window_options(
    *,
    selected_window: str,
    show_cancelled: bool,
    selected_appointment_id: str | None,
) -> list[dict[str, object]]:
    options: list[dict[str, object]] = []
    for value, (label, _) in _WINDOWS.items():
        href = f"/?view={value}"
        if show_cancelled:
            href = f"{href}&show_cancelled=1"
        if selected_appointment_id:
            href = f"{href}&appointment_id={selected_appointment_id}"
        options.append(
            {
                "label": label,
                "href": href,
                "is_active": value == selected_window,
            }
        )
    return options


def _detail_href(
    *,
    selected_window: str,
    appointment_id: str,
    show_cancelled: bool,
) -> str:
    href = f"/?view={selected_window}&appointment_id={appointment_id}"
    if show_cancelled:
        href = f"{href}&show_cancelled=1"
    return href


def _friendly_date_label(day: str, *, include_weekday: bool = False) -> str:
    parsed = date.fromisoformat(day)
    current_year = _today_in_alaska().year
    month_day = parsed.strftime("%b %d").replace(" 0", " ")
    if include_weekday:
        weekday = parsed.strftime("%A")
        base = f"{weekday}, {month_day}"
    else:
        base = month_day
    if parsed.year != current_year:
        return f"{base}, {parsed.year}"
    return base


def _schedule_eyebrow(day: str) -> str:
    parsed = date.fromisoformat(day)
    today = _today_in_alaska()
    if parsed == today:
        return "Today"
    if parsed == today + timedelta(days=1):
        return "Tomorrow"
    return parsed.strftime("%A").upper()


def _time_label(item: AppointmentListItem | AppointmentDetailResponse) -> str:
    if item.all_day:
        return "All day"
    start = _to_12_hour(item.start_time)
    end = _to_12_hour(item.end_time)
    return f"{start} - {end}"


def _to_12_hour(value: str) -> str:
    parsed = datetime.strptime(value, "%H:%M")
    return parsed.strftime("%I:%M %p").lstrip("0")


def _friendly_timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    timezone = ZoneInfo(parsed.tzinfo.key if parsed.tzinfo and hasattr(parsed.tzinfo, "key") else "America/Anchorage")
    localized = parsed.astimezone(timezone)
    month_day = localized.strftime("%b %d").replace(" 0", " ")
    return f"{month_day}, {localized.year} at {localized.strftime('%I:%M %p').lstrip('0')} {localized.tzname()}"


def _provider_label(provider_type: str) -> str:
    if provider_type == "icloud_caldav":
        return "Apple Calendar"
    return provider_type.replace("_", " ").title()


def _actor_label(actor: str) -> str:
    if actor == "console":
        return "CalSync workspace"
    if actor == "api":
        return "CalSync API"
    if actor.startswith("worker:"):
        channel = actor.split(":", 1)[1]
        if channel == "chatgpt":
            return "ChatGPT"
        if channel == "shortcuts":
            return "Apple Shortcuts"
        if channel == "alexa":
            return "Alexa"
        return f"Worker {channel}"
    return actor.replace("_", " ").title()


def _action_label(action: str) -> str:
    if action == "create_appointment":
        return "Created appointment"
    if action == "update_appointment":
        return "Updated appointment"
    if action == "cancel_appointment":
        return "Cancelled appointment"
    return action.replace("_", " ").title()


def _audit_summary(action: str, payload_json: dict[str, object] | None) -> str:
    payload = payload_json or {}
    if action == "create_appointment":
        title = payload.get("title")
        if isinstance(title, str) and title:
            return f"Created with the title “{title}”."
        return "Created in CalSync and written to the Apple calendar."
    if action == "update_appointment":
        changed_fields = []
        for key in ("title", "date", "start_time", "end_time", "location", "notes"):
            if key in payload:
                changed_fields.append(key.replace("_", " "))
        if changed_fields:
            readable = ", ".join(changed_fields)
            return f"Updated {readable} and synced the same Apple calendar event."
        return "Updated this appointment and synced the same Apple calendar event."
    if action == "cancel_appointment":
        return "Cancelled in CalSync and removed from the Apple calendar."
    return "Recorded activity for this appointment."


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
        "target_calendar_url": "",
        "all_day": False,
    }


def _calendar_options(
    service: AppointmentService,
    *,
    selected_calendar_url: str | None,
) -> list[dict[str, object]]:
    selected_value = selected_calendar_url or ""
    options: list[dict[str, object]] = []
    for item in service.available_calendars:
        calendar_url = str(item["calendar_url"])
        options.append(
            {
                "label": str(item["calendar_name"]),
                "value": calendar_url,
                "is_selected": calendar_url == selected_value
                or (not selected_value and bool(item.get("is_default"))),
            }
        )
    return options


def _default_alexa_simulator_values() -> dict[str, str]:
    next_day = _today_in_alaska() + timedelta(days=1)
    return {
        "request_type": "IntentRequest",
        "intent_name": "CreateAppointmentIntent",
        "title": "",
        "date": next_day.isoformat(),
        "start_time": "10:00",
        "end_time": "11:00",
        "location": "",
        "notes": "",
        "new_date": next_day.isoformat(),
        "new_start_time": "13:00",
        "new_end_time": "14:00",
    }
