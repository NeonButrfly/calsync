from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from importlib.resources import files
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode, urlparse
from uuid import uuid4
from zoneinfo import ZoneInfo
from zipfile import ZipFile

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import SQLAlchemyError

from calsync.schemas.appointments import (
    AppointmentDetailResponse,
    AppointmentListItem,
    AvailabilitySlot,
    CreateAppointmentRequest,
    UpdateAppointmentRequest,
)
from calsync.services.apple_caldav import (
    AppleCalDAVClient,
    AppleCalDAVConfig,
    AppleCalDAVError,
)
from calsync.services.alexa_simulator import AlexaSimulatorService
from calsync.services.appointments import AppointmentService
from calsync.services.apple_runtime_config import AppleRuntimeConfigService
from calsync.services.cloudflare_worker_config import CloudflareWorkerConfigService
from calsync.services.google_calendar import (
    GoogleCalendarClient,
    GoogleCalendarError,
    GoogleOAuthConfig,
)
from calsync.services.google_runtime_config import GoogleRuntimeConfigService
from calsync.services.legacy_backup_recovery import LegacyBackupRecoveryService
from calsync.services.microsoft_calendar import (
    MicrosoftCalendarClient,
    MicrosoftCalendarError,
    MicrosoftOAuthConfig,
)
from calsync.services.microsoft_runtime_config import MicrosoftRuntimeConfigService
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


@router.get("/book")
def public_booking_page(
    request: Request,
    availability_date_from: str | None = None,
    availability_date_to: str | None = None,
    availability_duration_minutes: int | None = None,
):
    return _render_public_booking_page(
        request,
        booking_slug=None,
        availability_date_from=availability_date_from,
        availability_date_to=availability_date_to,
        availability_duration_minutes=availability_duration_minutes,
    )


@router.get("/book/{booking_slug}")
def public_booking_type_page(
    request: Request,
    booking_slug: str,
    availability_date_from: str | None = None,
    availability_date_to: str | None = None,
    availability_duration_minutes: int | None = None,
):
    return _render_public_booking_page(
        request,
        booking_slug=booking_slug,
        availability_date_from=availability_date_from,
        availability_date_to=availability_date_to,
        availability_duration_minutes=availability_duration_minutes,
    )


def _render_public_booking_page(
    request: Request,
    *,
    booking_slug: str | None,
    availability_date_from: str | None,
    availability_date_to: str | None,
    availability_duration_minutes: int | None,
):
    service = AppointmentService()
    operator_settings = OperatorSettingsService()
    booking_types = operator_settings.describe_public_booking_types()
    if booking_slug is None and len(booking_types) > 1:
        return _templates.TemplateResponse(
            request,
            "booking.html",
            {
                "request": request,
                "flash_message": None,
                "error_message": None,
                "booking_confirmation": None,
                "booking_form_values": _empty_booking_form_values(),
                "booking_settings": operator_settings.describe_public_booking_settings(),
                "public_booking_url": "/book",
                "calendar_target": None,
                "calendar_ready": False,
                "availability_form_values": {},
                "availability_results": [],
                "booking_catalog_mode": True,
                "booking_types": booking_types,
            },
        )
    booking_settings = _load_public_booking_settings(
        operator_settings,
        booking_slug=booking_slug,
    )
    return _templates.TemplateResponse(
        request,
        "booking.html",
        _build_booking_context(
            request,
            service=service,
            booking_settings=booking_settings,
            availability_date_from=availability_date_from,
            availability_date_to=availability_date_to,
            availability_duration_minutes=availability_duration_minutes,
            booking_form_values=_empty_booking_form_values(),
            flash_message=None,
            error_message=None,
            booking_confirmation=None,
            booking_types=booking_types,
        ),
    )


@router.post("/book")
def public_booking_submit(
    request: Request,
    title: str = Form(...),
    requester_name: str = Form(...),
    requester_contact: str = Form(...),
    attendees_text: str = Form(""),
    location: str = Form(""),
    notes: str = Form(""),
    slot_value: str = Form(""),
    availability_date_from: str = Form(""),
    availability_date_to: str = Form(""),
    availability_duration_minutes: int = Form(60),
):
    return _handle_public_booking_submit(
        request,
        booking_slug=None,
        title=title,
        requester_name=requester_name,
        requester_contact=requester_contact,
        attendees_text=attendees_text,
        location=location,
        notes=notes,
        slot_value=slot_value,
        availability_date_from=availability_date_from,
        availability_date_to=availability_date_to,
        availability_duration_minutes=availability_duration_minutes,
    )


@router.post("/book/{booking_slug}")
def public_booking_type_submit(
    request: Request,
    booking_slug: str,
    title: str = Form(...),
    requester_name: str = Form(...),
    requester_contact: str = Form(...),
    attendees_text: str = Form(""),
    location: str = Form(""),
    notes: str = Form(""),
    slot_value: str = Form(""),
    availability_date_from: str = Form(""),
    availability_date_to: str = Form(""),
    availability_duration_minutes: int = Form(60),
):
    return _handle_public_booking_submit(
        request,
        booking_slug=booking_slug,
        title=title,
        requester_name=requester_name,
        requester_contact=requester_contact,
        attendees_text=attendees_text,
        location=location,
        notes=notes,
        slot_value=slot_value,
        availability_date_from=availability_date_from,
        availability_date_to=availability_date_to,
        availability_duration_minutes=availability_duration_minutes,
    )


def _handle_public_booking_submit(
    request: Request,
    *,
    booking_slug: str | None,
    title: str,
    requester_name: str,
    requester_contact: str,
    attendees_text: str,
    location: str,
    notes: str,
    slot_value: str,
    availability_date_from: str,
    availability_date_to: str,
    availability_duration_minutes: int,
):
    service = AppointmentService()
    operator_settings = OperatorSettingsService()
    booking_settings = _load_public_booking_settings(
        operator_settings,
        booking_slug=booking_slug,
    )
    booking_form_values = {
        "title": title,
        "requester_name": requester_name,
        "requester_contact": requester_contact,
        "attendees_text": attendees_text,
        "location": location,
        "notes": notes,
        "slot_value": slot_value,
    }
    target = _default_booking_target(
        service,
        configured_target_calendar_url=str(
            booking_settings.get("target_calendar_url") or ""
        ),
    )
    if target is None:
        return _templates.TemplateResponse(
            request,
            "booking.html",
            _build_booking_context(
                request,
                service=service,
                booking_settings=booking_settings,
                availability_date_from=availability_date_from or None,
                availability_date_to=availability_date_to or None,
                availability_duration_minutes=availability_duration_minutes,
                booking_form_values=booking_form_values,
                flash_message=None,
                error_message="No writable calendar target is ready for public booking yet.",
                booking_confirmation=None,
            ),
            status_code=400,
        )
    try:
        date_value, start_time, end_time, timezone = _parse_booking_slot_value(slot_value)
        created = service.create(
            CreateAppointmentRequest(
                title=title,
                date=date_value,
                start_time=start_time,
                end_time=end_time,
                timezone=timezone,
                location=location or None,
                notes=_public_booking_notes(
                    requester_name=requester_name,
                    requester_contact=requester_contact,
                    notes=notes,
                ),
                attendees_text=attendees_text or None,
                target_calendar_url=str(target["value"]),
            ),
            actor="public_booking",
        )
        detail = service.get_detail(created.appointment_id)
        return _templates.TemplateResponse(
            request,
            "booking.html",
            _build_booking_context(
                request,
                service=service,
                booking_settings=booking_settings,
                availability_date_from=availability_date_from or None,
                availability_date_to=availability_date_to or None,
                availability_duration_minutes=availability_duration_minutes,
                booking_form_values=_empty_booking_form_values(),
                flash_message=str(booking_settings["success_message"]),
                error_message=None,
                booking_confirmation={
                    "title": detail.title,
                    "date_label": _friendly_date_label(detail.date, include_weekday=True),
                    "time_label": _time_label(detail),
                    "timezone": detail.timezone,
                    "calendar_label": str(target["label"]),
                    "attendees_text": detail.attendees_text,
                    "requester_name": requester_name,
                    "requester_contact": requester_contact,
                },
            ),
        )
    except (ValueError, AppleCalDAVError, GoogleCalendarError, MicrosoftCalendarError) as exc:
        return _templates.TemplateResponse(
            request,
            "booking.html",
            _build_booking_context(
                request,
                service=service,
                booking_settings=booking_settings,
                availability_date_from=availability_date_from or None,
                availability_date_to=availability_date_to or None,
                availability_duration_minutes=availability_duration_minutes,
                booking_form_values=booking_form_values,
                flash_message=None,
                error_message=str(exc),
                booking_confirmation=None,
            ),
            status_code=400,
        )


@router.get("/booking/setup")
def booking_setup_page(request: Request, booking_slug: str | None = None):
    operator_settings = OperatorSettingsService()
    booking_settings = _load_public_booking_settings(
        operator_settings,
        booking_slug=booking_slug,
    )
    return _templates.TemplateResponse(
        request,
        "booking_setup.html",
        _build_booking_setup_context(
            request,
            operator_settings=operator_settings,
            booking_settings=booking_settings,
            flash_message=None,
            error_message=None,
        ),
    )


def _booking_setup_response(
    request: Request,
    *,
    operator_settings: OperatorSettingsService,
    booking_settings: dict[str, object],
    flash_message: str | None,
    error_message: str | None,
    status_code: int = 200,
):
    return _templates.TemplateResponse(
        request,
        "booking_setup.html",
        _build_booking_setup_context(
            request,
            operator_settings=operator_settings,
            booking_settings=booking_settings,
            flash_message=flash_message,
            error_message=error_message,
        ),
        status_code=status_code,
    )


def _build_booking_setup_context(
    request: Request,
    *,
    operator_settings: OperatorSettingsService,
    booking_settings: dict[str, object],
    flash_message: str | None,
    error_message: str | None,
) -> dict[str, object]:
    service = AppointmentService()
    legacy_apple_recovery_hints = operator_settings.describe_legacy_apple_recovery_hints()
    calendar_options = _calendar_options(
        service,
        selected_calendar_url=str(booking_settings.get("target_calendar_url") or "")
        or None,
    )
    booking_setup_ready = bool(calendar_options)
    booking_setup_recovery_mode = (
        not booking_setup_ready
        and str(legacy_apple_recovery_hints.get("source") or "missing") != "missing"
    )
    booking_setup_block_message = _describe_booking_setup_block_message(
        recovery_mode=booking_setup_recovery_mode,
    )
    return {
        "request": request,
        "booking_settings": booking_settings,
        "calendar_options": calendar_options,
        "booking_types": operator_settings.describe_public_booking_types(),
        "flash_message": flash_message,
        "error_message": error_message,
        "public_booking_url": str(booking_settings.get("public_url") or "/book"),
        "booking_setup_ready": booking_setup_ready,
        "booking_setup_recovery_mode": booking_setup_recovery_mode,
        "booking_setup_block_message": (
            None if booking_setup_ready else booking_setup_block_message
        ),
    }


@router.post("/booking/setup")
def booking_setup_update(
    request: Request,
    booking_slug: str = Form(""),
    page_title: str = Form(""),
    page_description: str = Form(""),
    duration_minutes: int = Form(60),
    search_window_days: int = Form(7),
    success_message: str = Form(""),
    target_calendar_url: str = Form(""),
    booking_weekdays: list[str] = Form([]),
    day_start_time: str = Form("08:00"),
    day_end_time: str = Form("18:00"),
    set_as_default: str = Form(""),
):
    operator_settings = OperatorSettingsService()
    service = AppointmentService()
    recovery_mode = _booking_setup_recovery_mode(operator_settings=operator_settings)
    try:
        if not _calendar_options(
            service,
            selected_calendar_url=target_calendar_url.strip() or None,
        ):
            raise ValueError(
                _describe_booking_setup_save_error(recovery_mode=recovery_mode)
            )
        if booking_slug.strip():
            operator_settings.upsert_public_booking_type(
                slug=booking_slug,
                page_title=page_title,
                page_description=page_description,
                duration_minutes=duration_minutes,
                search_window_days=search_window_days,
                success_message=success_message,
                target_calendar_url=target_calendar_url,
                booking_weekdays=[int(item) for item in booking_weekdays],
                day_start_time=day_start_time,
                day_end_time=day_end_time,
                set_as_default=bool(set_as_default),
            )
        else:
            operator_settings.set_public_booking_settings(
                page_title=page_title,
                page_description=page_description,
                duration_minutes=duration_minutes,
                search_window_days=search_window_days,
                success_message=success_message,
                target_calendar_url=target_calendar_url,
                booking_weekdays=[int(item) for item in booking_weekdays],
                day_start_time=day_start_time,
                day_end_time=day_end_time,
            )
        flash_message = "Public booking settings saved securely."
        error_message = None
    except (TypeError, ValueError) as exc:
        flash_message = None
        error_message = str(exc)
    booking_settings = _load_public_booking_settings(
        operator_settings,
        booking_slug=booking_slug or None,
    )
    return _booking_setup_response(
        request,
        operator_settings=operator_settings,
        booking_settings=booking_settings,
        flash_message=flash_message,
        error_message=error_message,
        status_code=200 if error_message is None else 400,
    )


@router.post("/booking/setup/types")
def booking_type_create(
    request: Request,
    booking_slug: str = Form(""),
    new_page_title: str = Form(""),
    new_booking_slug: str = Form(""),
):
    operator_settings = OperatorSettingsService()
    service = AppointmentService()
    recovery_mode = _booking_setup_recovery_mode(operator_settings=operator_settings)
    current_settings = _load_public_booking_settings(
        operator_settings,
        booking_slug=booking_slug or None,
    )
    requested_slug = new_booking_slug.strip() or new_page_title.strip()
    try:
        if not _calendar_options(
            service,
            selected_calendar_url=str(current_settings.get("target_calendar_url") or "")
            or None,
        ):
            raise ValueError(
                _describe_booking_setup_type_error(recovery_mode=recovery_mode)
            )
        operator_settings.upsert_public_booking_type(
            slug=requested_slug,
            page_title=new_page_title.strip() or str(current_settings["page_title"]),
            page_description=str(current_settings["page_description"]),
            duration_minutes=int(current_settings["duration_minutes"]),
            search_window_days=int(current_settings["search_window_days"]),
            success_message=str(current_settings["success_message"]),
            target_calendar_url=str(current_settings["target_calendar_url"]),
            booking_weekdays=[
                int(item) for item in current_settings.get("booking_weekdays", [])
            ],
            day_start_time=str(current_settings["day_start_time"]),
            day_end_time=str(current_settings["day_end_time"]),
            set_as_default=False,
        )
        created_settings = _load_public_booking_settings(
            operator_settings,
            booking_slug=requested_slug,
        )
        flash_message = "Public booking type saved securely."
        error_message = None
    except (TypeError, ValueError) as exc:
        created_settings = current_settings
        flash_message = None
        error_message = str(exc)

    return _booking_setup_response(
        request,
        operator_settings=operator_settings,
        booking_settings=created_settings,
        flash_message=flash_message,
        error_message=error_message,
        status_code=200 if error_message is None else 400,
    )


@router.post("/booking/setup/types/default")
def booking_type_set_default(
    request: Request,
    booking_slug: str = Form(""),
):
    operator_settings = OperatorSettingsService()
    try:
        operator_settings.set_default_public_booking_type(booking_slug)
        booking_settings = _load_public_booking_settings(
            operator_settings,
            booking_slug=booking_slug or None,
        )
        flash_message = "Default booking type updated."
        error_message = None
    except (TypeError, ValueError) as exc:
        booking_settings = _load_public_booking_settings(operator_settings)
        flash_message = None
        error_message = str(exc)

    return _booking_setup_response(
        request,
        operator_settings=operator_settings,
        booking_settings=booking_settings,
        flash_message=flash_message,
        error_message=error_message,
        status_code=200 if error_message is None else 400,
    )


@router.post("/booking/setup/types/delete")
def booking_type_delete(
    request: Request,
    booking_slug: str = Form(""),
):
    operator_settings = OperatorSettingsService()
    try:
        operator_settings.delete_public_booking_type(booking_slug)
        booking_settings = _load_public_booking_settings(
            operator_settings,
            booking_slug=None,
        )
        flash_message = "Booking type deleted."
        error_message = None
    except (TypeError, ValueError) as exc:
        booking_settings = _load_public_booking_settings(
            operator_settings,
            booking_slug=booking_slug or None,
        )
        flash_message = None
        error_message = str(exc)

    return _booking_setup_response(
        request,
        operator_settings=operator_settings,
        booking_settings=booking_settings,
        flash_message=flash_message,
        error_message=error_message,
        status_code=200 if error_message is None else 400,
    )


@router.get("/alexa/setup")
def alexa_setup_page(request: Request):
    readiness = ReadinessService().build()
    operator_settings = OperatorSettingsService()
    edge_settings = CloudflareWorkerConfigService().get_alexa_settings()
    return _render_alexa_setup_page(
        request,
        readiness=readiness,
        operator_settings=operator_settings,
        edge_settings=edge_settings,
        flash_message=None,
        error_message=None,
        status_code=200,
    )


def _render_alexa_setup_page(
    request: Request,
    *,
    readiness: dict[str, object],
    operator_settings: OperatorSettingsService,
    edge_settings: dict[str, object],
    flash_message: str | None,
    error_message: str | None,
    status_code: int,
):
    desired_settings = operator_settings.describe_desired_alexa_settings()
    account_linking_settings = operator_settings.describe_alexa_account_linking_settings()
    cloudflare_credentials = operator_settings.describe_cloudflare_worker_credentials()
    legacy_apple_recovery_hints = operator_settings.describe_legacy_apple_recovery_hints()
    alexa_action_copy = _describe_alexa_action_copy(edge_settings=edge_settings)
    return _templates.TemplateResponse(
        request,
        "alexa_setup.html",
        {
            "request": request,
            "readiness": readiness,
            "edge_settings": edge_settings,
            "desired_alexa_settings": desired_settings,
            "alexa_drift": _describe_alexa_settings_drift(
                desired_settings=desired_settings,
                edge_settings=edge_settings,
            ),
            "alexa_next_action": _describe_alexa_next_action(
                readiness=readiness,
                desired_settings=desired_settings,
                account_linking_settings=account_linking_settings,
                cloudflare_credentials=cloudflare_credentials,
                legacy_apple_recovery_hints=legacy_apple_recovery_hints,
            ),
            "account_linking_settings": account_linking_settings,
            "cloudflare_credentials": cloudflare_credentials,
            "alexa_action_copy": alexa_action_copy,
            "alexa_endpoint": "https://edge-calsync.neonbutterfly.net/alexa",
            "alexa_account_linking_authorization_url": "https://calsync.neonbutterfly.net/alexa/account-linking/authorize",
            "privacy_url": "https://calsync.neonbutterfly.net/privacy",
            "terms_url": "https://calsync.neonbutterfly.net/terms",
            "simulator_url": "/alexa/simulator",
            "flash_message": flash_message,
            "error_message": error_message,
        },
        status_code=status_code,
    )


@router.post("/alexa/setup/account-linking")
def alexa_setup_update_account_linking(
    request: Request,
    link_code: str = Form(""),
):
    operator_settings = OperatorSettingsService()
    try:
        operator_settings.set_alexa_account_linking_settings(link_code=link_code)
        flash_message = "Alexa account linking is ready."
        error_message = None
    except ValueError as exc:
        flash_message = None
        error_message = str(exc)
    edge_settings = CloudflareWorkerConfigService().get_alexa_settings()
    return _render_alexa_setup_page(
        request,
        readiness=ReadinessService().build(),
        operator_settings=operator_settings,
        edge_settings=edge_settings,
        flash_message=flash_message,
        error_message=error_message,
        status_code=200 if error_message is None else 400,
    )


@router.get("/alexa/account-linking/authorize")
def alexa_account_linking_authorize_page(
    request: Request,
    client_id: str = "",
    redirect_uri: str = "",
    response_type: str = "",
    state: str = "",
    scope: str = "",
):
    operator_settings = OperatorSettingsService()
    return _render_alexa_account_linking_authorize_page(
        request,
        operator_settings=operator_settings,
        form_values={
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": response_type,
            "state": state,
            "scope": scope,
            "link_code": "",
        },
        error_message=None,
        status_code=200,
    )


@router.post("/alexa/account-linking/authorize")
def alexa_account_linking_authorize(
    request: Request,
    client_id: str = Form(""),
    redirect_uri: str = Form(""),
    response_type: str = Form(""),
    state: str = Form(""),
    scope: str = Form(""),
    link_code: str = Form(""),
):
    operator_settings = OperatorSettingsService()
    settings = operator_settings.get_alexa_account_linking_settings()
    error_message: str | None = None
    if not operator_settings.describe_alexa_account_linking_settings()["configured"]:
        error_message = "Alexa account linking has not been configured in CalSync yet."
    elif response_type != "token":
        error_message = "Alexa account linking only supports the implicit token response right now."
    elif not state.strip():
        error_message = "Alexa account linking requires a state value."
    elif not _is_allowed_alexa_redirect_uri(redirect_uri):
        error_message = "Alexa redirect URI is not allowed."
    elif client_id.strip() != str(settings["client_id"] or "").strip():
        error_message = "Client ID does not match the saved Alexa account-linking client."
    elif not operator_settings.validate_alexa_account_linking_code(link_code):
        error_message = "Link code did not match the saved Alexa household code."

    if error_message:
        return _render_alexa_account_linking_authorize_page(
            request,
            operator_settings=operator_settings,
            form_values={
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": response_type,
                "state": state,
                "scope": scope,
                "link_code": "",
            },
            error_message=error_message,
            status_code=400,
        )

    fragment = urlencode(
        {
            "state": state,
            "access_token": str(settings["access_token"] or ""),
            "token_type": "Bearer",
        }
    )
    return RedirectResponse(
        url=f"{redirect_uri}#{fragment}",
        status_code=302,
    )


@router.post("/api/alexa/account-linking/validate")
async def alexa_account_linking_validate(request: Request):
    operator_settings = OperatorSettingsService()
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    access_token = (
        str(payload.get("access_token") or "").strip()
        if isinstance(payload, dict)
        else ""
    )
    configured = bool(
        operator_settings.describe_alexa_account_linking_settings()["configured"]
    )
    linked = (
        operator_settings.validate_alexa_account_linking_access_token(access_token)
        if configured
        else False
    )
    return {
        "ok": True,
        "message": "Alexa account-linking status retrieved.",
        "data": {
            "account_linking_configured": configured,
            "linked": linked,
        },
    }


@router.get("/calendar/setup")
def calendar_setup_page(
    request: Request,
    recovered_calendar_url: str | None = None,
):
    operator_settings = OperatorSettingsService()
    apple_settings = operator_settings.describe_apple_calendar_settings()
    legacy_recovery_hints = operator_settings.describe_legacy_apple_recovery_hints()
    runtime_service = AppleRuntimeConfigService(operator_settings=operator_settings)
    runtime_config = runtime_service.resolve()
    status_code = 200
    flash_message = None
    error_message = None
    selected_recovered_calendar_url = str(recovered_calendar_url or "").strip()
    auto_loaded_recovery_hint = False
    if (
        not selected_recovered_calendar_url
        and str(apple_settings.get("source") or "") == "missing"
        and str(legacy_recovery_hints.get("source") or "") != "missing"
    ):
        selected_recovered_calendar_url = str(
            legacy_recovery_hints.get("recommended_calendar_url") or ""
        ).strip()
        auto_loaded_recovery_hint = bool(selected_recovered_calendar_url)
    if selected_recovered_calendar_url:
        try:
            apple_settings = _prefill_apple_settings_from_legacy_hints(
                apple_settings=apple_settings,
                legacy_recovery_hints=legacy_recovery_hints,
                recovered_calendar_url=selected_recovered_calendar_url,
            )
            if not auto_loaded_recovery_hint:
                flash_message = (
                    "Recovered Apple details loaded into the setup form. "
                    "Add a fresh app-specific password to finish reconnecting."
                )
        except ValueError as exc:
            error_message = str(exc)
            status_code = 400
    return _templates.TemplateResponse(
        request,
        "calendar_setup.html",
        _build_calendar_setup_context(
            request,
            apple_settings=apple_settings,
            legacy_recovery_hints=legacy_recovery_hints,
            runtime_service=runtime_service,
            runtime_config=runtime_config,
            flash_message=flash_message,
            error_message=error_message,
        ),
        status_code=status_code,
    )


def _build_calendar_setup_context(
    request: Request,
    *,
    apple_settings: dict[str, object],
    legacy_recovery_hints: dict[str, object],
    runtime_service: AppleRuntimeConfigService,
    runtime_config: dict[str, object],
    flash_message: str | None,
    error_message: str | None,
) -> dict[str, object]:
    loaded_recovered_calendar_url = (
        str(apple_settings.get("primary_calendar_url") or "").strip()
        if str(apple_settings.get("source") or "") == "legacy_recovery_hints"
        else ""
    )
    recommended_recovered_calendar_url = str(
        legacy_recovery_hints.get("recommended_calendar_url") or ""
    ).strip()
    source_card = _describe_calendar_setup_source_card(
        apple_settings=apple_settings,
        runtime_config=runtime_config,
        legacy_recovery_hints=legacy_recovery_hints,
    )
    return {
        "request": request,
        "apple_settings": apple_settings,
        "legacy_recovery_hints": legacy_recovery_hints,
        "runtime_config": runtime_config,
        "source_card": source_card,
        "apple_accounts": runtime_service.list_accounts(),
        "calendar_catalog": runtime_service.list_calendars(),
        "flash_message": flash_message,
        "error_message": error_message,
        "loaded_recovered_calendar_url": loaded_recovered_calendar_url,
        "recommended_recovered_hint_loaded": bool(loaded_recovered_calendar_url)
        and loaded_recovered_calendar_url == recommended_recovered_calendar_url,
    }


def _prefill_apple_settings_from_legacy_hints(
    *,
    apple_settings: dict[str, object],
    legacy_recovery_hints: dict[str, object],
    recovered_calendar_url: str,
) -> dict[str, object]:
    if str(legacy_recovery_hints.get("source") or "") == "missing":
        raise ValueError("Import a legacy Apple backup before trying to load recovered setup hints.")
    if str(apple_settings.get("source") or "") != "missing":
        raise ValueError(
            "Recovered Apple hints can only prefill the form before the first Apple account is saved."
        )
    selected_url = str(recovered_calendar_url or "").strip()
    selected_hint = next(
        (
            item
            for item in legacy_recovery_hints.get("calendars", [])
            if isinstance(item, dict)
            and str(item.get("calendar_url") or "").strip() == selected_url
        ),
        None,
    )
    if selected_hint is None:
        raise ValueError("Recovered Apple calendar hint was not found.")
    return {
        "account_label": str(
            legacy_recovery_hints.get("account_label")
            or legacy_recovery_hints.get("account_username")
            or ""
        ),
        "username": str(legacy_recovery_hints.get("account_username") or ""),
        "primary_calendar_url": selected_url,
        "primary_calendar_name": str(selected_hint.get("calendar_name") or ""),
        "password_saved": False,
        "source": "legacy_recovery_hints",
    }


def _build_pending_apple_setup_state(
    *,
    apple_account_label: str,
    apple_username: str,
    apple_primary_calendar_url: str,
    apple_primary_calendar_name: str,
    legacy_recovery_hints: dict[str, object],
) -> dict[str, object]:
    normalized_username = apple_username.strip()
    normalized_calendar_url = apple_primary_calendar_url.strip()
    source = "form"
    if (
        str(legacy_recovery_hints.get("source") or "") != "missing"
        and normalized_username
        and normalized_username.lower()
        == str(legacy_recovery_hints.get("account_username") or "").strip().lower()
        and any(
            isinstance(item, dict)
            and str(item.get("calendar_url") or "").strip() == normalized_calendar_url
            for item in legacy_recovery_hints.get("calendars", [])
        )
    ):
        source = "legacy_recovery_hints"
    return {
        "account_label": apple_account_label.strip(),
        "username": normalized_username,
        "primary_calendar_url": normalized_calendar_url,
        "primary_calendar_name": apple_primary_calendar_name.strip(),
        "password_saved": False,
        "source": source,
    }


def _build_pending_apple_validation_config(
    *,
    apple_account_label: str,
    apple_username: str,
    apple_app_specific_password: str,
    apple_primary_calendar_url: str,
    apple_primary_calendar_name: str,
) -> AppleCalDAVConfig:
    normalized_account_label = apple_account_label.strip()
    normalized_username = apple_username.strip()
    normalized_password = apple_app_specific_password.strip()
    normalized_calendar_url = apple_primary_calendar_url.strip()
    normalized_calendar_name = apple_primary_calendar_name.strip()
    if not normalized_account_label:
        raise ValueError("Apple account label is required.")
    if not normalized_username:
        raise ValueError("Apple username is required.")
    if not normalized_password:
        raise ValueError("Apple app-specific password is required for validation.")
    if not normalized_calendar_url:
        raise ValueError("Apple calendar URL is required.")
    if not normalized_calendar_name:
        raise ValueError("Apple calendar name is required.")
    return AppleCalDAVConfig(
        account_label=normalized_account_label,
        apple_username=normalized_username,
        app_specific_password=normalized_password,
        primary_calendar_url=normalized_calendar_url,
        primary_calendar_name=normalized_calendar_name,
    )


def _describe_calendar_setup_source_card(
    *,
    apple_settings: dict[str, object],
    runtime_config: dict[str, object],
    legacy_recovery_hints: dict[str, object],
) -> dict[str, str]:
    if bool(runtime_config.get("ready")):
        return {
            "label": str(runtime_config.get("source") or "").replace("_", " ").title(),
            "detail": "Apple calendar setup is ready for the live scheduling brain.",
        }
    if str(apple_settings.get("source") or "") == "legacy_recovery_hints":
        return {
            "label": "Recovered hint loaded",
            "detail": "The recommended recovered Apple calendar is already loaded into setup. Add a fresh app-specific password to reconnect.",
        }
    if str(legacy_recovery_hints.get("source") or "") != "missing":
        return {
            "label": "Recovered hint available",
            "detail": "Legacy Apple backup hints are ready. Load the right calendar into setup and save a fresh app-specific password to reconnect.",
        }
    return {
        "label": str(runtime_config.get("source") or "").replace("_", " ").title(),
        "detail": "Apple calendar setup is still incomplete.",
    }


@router.get("/connections")
def connections_page(request: Request):
    return _templates.TemplateResponse(
        request,
        "connections.html",
        _build_connections_context(
            request,
            flash_message=None,
            error_message=None,
        ),
    )


@router.get("/connections/settings-backup")
def connections_download_settings_backup() -> StreamingResponse:
    backup = OperatorSettingsService().export_operator_settings_backup()
    payload = BytesIO(str(backup["backup_json"]).encode("utf-8"))
    return StreamingResponse(
        payload,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{backup["filename"]}"'
        },
    )


@router.post("/connections/settings-restore")
async def connections_restore_settings_backup(
    request: Request,
    backup_file: UploadFile = File(...),
):
    operator_settings = OperatorSettingsService()
    try:
        raw_bytes = await backup_file.read()
        backup_document = json.loads(raw_bytes.decode("utf-8"))
        restored_count = operator_settings.restore_operator_settings_backup(backup_document)
        flash_message = (
            f"Operator settings restored from encrypted backup. {restored_count} settings loaded."
        )
        error_message = None
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        flash_message = None
        error_message = str(exc)

    return _templates.TemplateResponse(
        request,
        "connections.html",
        _build_connections_context(
            request,
            flash_message=flash_message,
            error_message=error_message,
        ),
        status_code=200 if error_message is None else 400,
    )


@router.post("/connections/legacy-backup/import")
async def connections_import_legacy_backup(
    request: Request,
    backup_file: UploadFile = File(...),
):
    operator_settings = OperatorSettingsService()
    try:
        raw_bytes = await backup_file.read()
        hints = LegacyBackupRecoveryService().extract_apple_hints(
            backup_bytes=raw_bytes,
            filename=backup_file.filename or "legacy-backup",
        )
        operator_settings.set_legacy_apple_recovery_hints(hints)
        flash_message = "Legacy Apple recovery hints imported from backup."
        error_message = None
    except ValueError as exc:
        flash_message = None
        error_message = str(exc)

    return _templates.TemplateResponse(
        request,
        "connections.html",
        _build_connections_context(
            request,
            flash_message=flash_message,
            error_message=error_message,
        ),
        status_code=200 if error_message is None else 400,
    )


@router.post("/connections/test")
def connections_run_write_test(
    request: Request,
    target_calendar_url: str = Form(""),
):
    operator_settings = OperatorSettingsService()
    service = AppointmentService()
    try:
        result = service.run_write_smoke_test(
            target_calendar_url=target_calendar_url,
            actor="console",
        )
        flash_message = _write_test_success_message(result)
        _record_write_test_verification(
            operator_settings,
            service,
            target_calendar_url=target_calendar_url,
            passed=True,
            message=flash_message,
            result=result,
        )
        error_message = None
    except (
        AppleCalDAVError,
        GoogleCalendarError,
        MicrosoftCalendarError,
        ValueError,
    ) as exc:
        flash_message = None
        error_message = str(exc)
        _record_write_test_verification(
            operator_settings,
            service,
            target_calendar_url=target_calendar_url,
            passed=False,
            message=error_message,
            result=None,
        )

    return _templates.TemplateResponse(
        request,
        "connections.html",
        _build_connections_context(
            request,
            flash_message=flash_message,
            error_message=error_message,
        ),
        status_code=200 if error_message is None else 400,
    )


@router.post("/connections/google/refresh")
def connections_google_refresh(request: Request):
    operator_settings = OperatorSettingsService()
    requested_account_email = str((request.query_params.get("account_email") or "")).strip() or None
    try:
        client = _build_google_client_from_settings(
            operator_settings,
            account_email=requested_account_email,
        )
        selected_runtime = GoogleRuntimeConfigService(
            operator_settings=operator_settings
        ).resolve(account_email=requested_account_email)
        account_email = client.current_user_email()
        calendar_catalog = client.list_calendars()
        previous_account_email = str(selected_runtime["account_email"] or "").strip()
        if previous_account_email and previous_account_email.lower() != account_email.lower():
            operator_settings.remove_google_account(previous_account_email)
        operator_settings.upsert_google_account(
            account_label=account_email,
            account_email=account_email,
            refresh_token=str(selected_runtime["refresh_token"] or ""),
            calendars=calendar_catalog,
        )
        flash_message = "Google calendars refreshed from the live account."
        error_message = None
    except (GoogleCalendarError, ValueError) as exc:
        flash_message = None
        error_message = str(exc)

    return _templates.TemplateResponse(
        request,
        "connections.html",
        _build_connections_context(
            request,
            flash_message=flash_message,
            error_message=error_message,
        ),
        status_code=200 if error_message is None else 400,
    )


@router.post("/connections/google/disconnect")
def connections_google_disconnect(request: Request):
    operator_settings = OperatorSettingsService()
    operator_settings.clear_google_oauth_state()
    account_email = str((request.query_params.get("account_email") or "")).strip() or None
    if account_email:
        operator_settings.remove_google_account(account_email)
    else:
        operator_settings.clear_google_account_settings()
        operator_settings.clear_google_calendar_catalog()
    return _templates.TemplateResponse(
        request,
        "connections.html",
        _build_connections_context(
            request,
            flash_message="Google account disconnected. The shared OAuth app is still saved.",
            error_message=None,
        ),
    )


@router.post("/connections/microsoft/refresh")
def connections_microsoft_refresh(request: Request):
    operator_settings = OperatorSettingsService()
    requested_account_email = str((request.query_params.get("account_email") or "")).strip() or None
    try:
        client = _build_microsoft_client_from_settings(
            operator_settings,
            account_email=requested_account_email,
        )
        selected_runtime = MicrosoftRuntimeConfigService(
            operator_settings=operator_settings
        ).resolve(account_email=requested_account_email)
        account_email = client.current_user_email()
        calendar_catalog = client.list_calendars()
        previous_account_email = str(selected_runtime["account_email"] or "").strip()
        if previous_account_email and previous_account_email.lower() != account_email.lower():
            operator_settings.remove_microsoft_account(previous_account_email)
        operator_settings.upsert_microsoft_account(
            account_label=account_email,
            account_email=account_email,
            refresh_token=str(selected_runtime["refresh_token"] or ""),
            calendars=calendar_catalog,
        )
        flash_message = "Microsoft calendars refreshed from the live account."
        error_message = None
    except (MicrosoftCalendarError, ValueError) as exc:
        flash_message = None
        error_message = str(exc)

    return _templates.TemplateResponse(
        request,
        "connections.html",
        _build_connections_context(
            request,
            flash_message=flash_message,
            error_message=error_message,
        ),
        status_code=200 if error_message is None else 400,
    )


@router.post("/connections/microsoft/disconnect")
def connections_microsoft_disconnect(request: Request):
    operator_settings = OperatorSettingsService()
    operator_settings.clear_microsoft_oauth_state()
    account_email = str((request.query_params.get("account_email") or "")).strip() or None
    if account_email:
        operator_settings.remove_microsoft_account(account_email)
    else:
        operator_settings.clear_microsoft_account_settings()
        operator_settings.clear_microsoft_calendar_catalog()
    return _templates.TemplateResponse(
        request,
        "connections.html",
        _build_connections_context(
            request,
            flash_message="Microsoft account disconnected. The shared OAuth app is still saved.",
            error_message=None,
        ),
    )


@router.post("/connections/alexa")
def connections_alexa_update(
    request: Request,
    allowed_skill_ids: str = Form(""),
    enable_alexa: str | None = Form(None),
):
    operator_settings = OperatorSettingsService()
    normalized_skill_ids = [
        value.strip() for value in allowed_skill_ids.split(",") if value.strip()
    ]
    operator_settings.set_desired_alexa_settings(
        enable_alexa=enable_alexa == "true",
        allowed_skill_ids=normalized_skill_ids,
    )
    service = CloudflareWorkerConfigService()
    try:
        service.update_alexa_settings(
            enable_alexa=enable_alexa == "true",
            allowed_skill_ids=normalized_skill_ids,
        )
        flash_message = "Desired Alexa settings saved and edge Worker updated."
        error_message = None
    except ValueError as exc:
        flash_message = "Desired Alexa settings saved securely."
        error_message = str(exc)

    return _templates.TemplateResponse(
        request,
        "connections.html",
        _build_connections_context(
            request,
            flash_message=flash_message,
            error_message=error_message,
        ),
        status_code=200,
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
        _build_calendar_setup_context(
            request,
            apple_settings=apple_settings,
            legacy_recovery_hints=operator_settings.describe_legacy_apple_recovery_hints(),
            runtime_service=runtime_service,
            runtime_config=runtime_config,
            flash_message=flash_message,
            error_message=error_message,
        ),
        status_code=200 if error_message is None else 400,
    )


@router.post("/calendar/setup/validate")
def calendar_setup_validate(
    request: Request,
    apple_account_label: str = Form(""),
    apple_username: str = Form(""),
    apple_app_specific_password: str = Form(""),
    apple_primary_calendar_url: str = Form(""),
    apple_primary_calendar_name: str = Form(""),
):
    operator_settings = OperatorSettingsService()
    runtime_service = AppleRuntimeConfigService(
        operator_settings=operator_settings
    )
    legacy_recovery_hints = operator_settings.describe_legacy_apple_recovery_hints()
    apple_settings = _build_pending_apple_setup_state(
        apple_account_label=apple_account_label,
        apple_username=apple_username,
        apple_primary_calendar_url=apple_primary_calendar_url,
        apple_primary_calendar_name=apple_primary_calendar_name,
        legacy_recovery_hints=legacy_recovery_hints,
    )
    try:
        config = _build_pending_apple_validation_config(
            apple_account_label=apple_account_label,
            apple_username=apple_username,
            apple_app_specific_password=apple_app_specific_password,
            apple_primary_calendar_url=apple_primary_calendar_url,
            apple_primary_calendar_name=apple_primary_calendar_name,
        )
        AppleCalDAVClient(config).validate_calendar_access()
        flash_message = (
            "Apple calendar credentials validated successfully. "
            "Nothing has been saved yet."
        )
        error_message = None
    except (ValueError, AppleCalDAVError) as exc:
        flash_message = None
        error_message = str(exc)

    runtime_config = runtime_service.resolve()
    return _templates.TemplateResponse(
        request,
        "calendar_setup.html",
        _build_calendar_setup_context(
            request,
            apple_settings=apple_settings,
            legacy_recovery_hints=legacy_recovery_hints,
            runtime_service=runtime_service,
            runtime_config=runtime_config,
            flash_message=flash_message,
            error_message=error_message,
        ),
        status_code=200 if error_message is None else 400,
    )


@router.post("/calendar/setup/calendars")
def calendar_setup_add_calendar(
    request: Request,
    account_username: str = Form(""),
    calendar_name: str = Form(""),
    calendar_url: str = Form(""),
    is_default: str | None = Form(None),
):
    operator_settings = OperatorSettingsService()
    runtime_service = AppleRuntimeConfigService(operator_settings=operator_settings)
    try:
        normalized_username = account_username.strip()
        accounts = runtime_service.list_accounts()
        if not normalized_username and len(accounts) == 1:
            normalized_username = str(accounts[0].get("username") or "")
        if normalized_username and not operator_settings.get_apple_accounts():
            runtime_config = runtime_service.resolve(username=normalized_username)
            operator_settings.upsert_apple_account(
                account_label=str(runtime_config["account_label"]),
                username=str(runtime_config["username"]),
                app_specific_password=str(runtime_config["app_specific_password"]),
                calendars=[
                    {
                        "calendar_name": str(item["calendar_name"]),
                        "calendar_url": str(item["calendar_url"]),
                        "is_default": bool(item.get("is_default")),
                    }
                    for item in runtime_service.list_calendars()
                    if str(item.get("username") or "") == normalized_username
                ] or [
                    {
                        "calendar_name": str(runtime_config["primary_calendar_name"]),
                        "calendar_url": str(runtime_config["primary_calendar_url"]),
                        "is_default": True,
                    }
                ],
            )
        operator_settings.add_apple_calendar_target(
            account_username=normalized_username,
            calendar_name=calendar_name,
            calendar_url=calendar_url,
            is_default=is_default == "true",
        )
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
        _build_calendar_setup_context(
            request,
            apple_settings=apple_settings,
            legacy_recovery_hints=operator_settings.describe_legacy_apple_recovery_hints(),
            runtime_service=runtime_service,
            runtime_config=runtime_config,
            flash_message=flash_message,
            error_message=error_message,
        ),
        status_code=200 if error_message is None else 400,
    )


@router.post("/calendar/setup/test")
def calendar_setup_run_write_test(
    request: Request,
    target_calendar_url: str = Form(""),
):
    service = AppointmentService()
    operator_settings = OperatorSettingsService()
    try:
        result = service.run_write_smoke_test(
            target_calendar_url=target_calendar_url,
            actor="console",
        )
        flash_message = _write_test_success_message(result)
        _record_write_test_verification(
            operator_settings,
            service,
            target_calendar_url=target_calendar_url,
            passed=True,
            message=flash_message,
            result=result,
        )
        error_message = None
    except (
        AppleCalDAVError,
        GoogleCalendarError,
        MicrosoftCalendarError,
        ValueError,
    ) as exc:
        flash_message = None
        error_message = str(exc)
        _record_write_test_verification(
            operator_settings,
            service,
            target_calendar_url=target_calendar_url,
            passed=False,
            message=error_message,
            result=None,
        )

    runtime_service = AppleRuntimeConfigService(operator_settings=operator_settings)
    runtime_config = runtime_service.resolve()
    return _templates.TemplateResponse(
        request,
        "calendar_setup.html",
        _build_calendar_setup_context(
            request,
            apple_settings=operator_settings.describe_apple_calendar_settings(),
            legacy_recovery_hints=operator_settings.describe_legacy_apple_recovery_hints(),
            runtime_service=runtime_service,
            runtime_config=runtime_config,
            flash_message=flash_message,
            error_message=error_message,
        ),
        status_code=200 if error_message is None else 400,
    )


@router.get("/google/setup")
def google_setup_page(request: Request):
    operator_settings = OperatorSettingsService()
    runtime_service = GoogleRuntimeConfigService(operator_settings=operator_settings)
    return _templates.TemplateResponse(
        request,
        "google_setup.html",
        _build_google_setup_context(
            request,
            operator_settings=operator_settings,
            runtime_service=runtime_service,
            flash_message=None,
            error_message=None,
        ),
    )


def _build_google_client_from_settings(
    operator_settings: OperatorSettingsService,
    *,
    account_email: str | None = None,
) -> GoogleCalendarClient:
    oauth_settings = operator_settings.get_google_oauth_settings()
    runtime_service = GoogleRuntimeConfigService(operator_settings=operator_settings)
    runtime_config = runtime_service.resolve(account_email=account_email)
    client_id = str(oauth_settings["client_id"] or "").strip()
    client_secret = str(oauth_settings["client_secret"] or "").strip()
    refresh_token = str(runtime_config["refresh_token"] or "").strip()
    if not client_id or not client_secret:
        raise ValueError("Google OAuth settings are incomplete.")
    if not refresh_token:
        raise ValueError("Google account is not connected yet.")
    return GoogleCalendarClient(
        GoogleOAuthConfig(
            account_label=str(runtime_config["account_label"] or "Google"),
            account_email=str(runtime_config["account_email"] or ""),
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            primary_calendar_id=str(runtime_config["primary_calendar_id"] or "primary"),
            primary_calendar_name=str(runtime_config["primary_calendar_name"] or "Primary"),
        )
    )


def _build_microsoft_client_from_settings(
    operator_settings: OperatorSettingsService,
    *,
    account_email: str | None = None,
) -> MicrosoftCalendarClient:
    oauth_settings = operator_settings.get_microsoft_oauth_settings()
    runtime_service = MicrosoftRuntimeConfigService(operator_settings=operator_settings)
    runtime_config = runtime_service.resolve(account_email=account_email)
    client_id = str(oauth_settings["client_id"] or "").strip()
    client_secret = str(oauth_settings["client_secret"] or "").strip()
    refresh_token = str(runtime_config["refresh_token"] or "").strip()
    if not client_id or not client_secret:
        raise ValueError("Microsoft OAuth settings are incomplete.")
    if not refresh_token:
        raise ValueError("Microsoft account is not connected yet.")
    return MicrosoftCalendarClient(
        MicrosoftOAuthConfig(
            account_label=str(runtime_config["account_label"] or "Microsoft"),
            account_email=str(runtime_config["account_email"] or ""),
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            primary_calendar_id=str(runtime_config["primary_calendar_id"] or "primary"),
            primary_calendar_name=str(runtime_config["primary_calendar_name"] or "Primary"),
        )
    )


def _google_connect_ready(google_settings: dict[str, object]) -> bool:
    return bool(str(google_settings.get("client_id") or "").strip()) and bool(
        google_settings.get("client_secret_saved")
    )


def _microsoft_connect_ready(microsoft_settings: dict[str, object]) -> bool:
    return bool(str(microsoft_settings.get("client_id") or "").strip()) and bool(
        microsoft_settings.get("client_secret_saved")
    )


def _build_google_setup_context(
    request: Request,
    *,
    operator_settings: OperatorSettingsService,
    runtime_service: GoogleRuntimeConfigService,
    flash_message: str | None,
    error_message: str | None,
    runtime_config: dict[str, object] | None = None,
) -> dict[str, object]:
    google_settings = operator_settings.describe_google_oauth_settings()
    connect_ready = _google_connect_ready(google_settings)
    return {
        "request": request,
        "google_settings": google_settings,
        "runtime_config": runtime_config or runtime_service.resolve(),
        "google_accounts": runtime_service.list_accounts(),
        "calendar_catalog": runtime_service.list_calendars(),
        "flash_message": flash_message,
        "error_message": error_message,
        "connect_url": "/auth/google/start",
        "connect_ready": connect_ready,
        "connect_label": (
            "Connect another Google account"
            if bool(google_settings.get("refresh_token_saved"))
            else "Connect Google account"
        ),
        "connect_block_message": (
            None
            if connect_ready
            else "Save the shared Google OAuth app before connecting a Google account."
        ),
    }


def _build_microsoft_setup_context(
    request: Request,
    *,
    operator_settings: OperatorSettingsService,
    runtime_service: MicrosoftRuntimeConfigService,
    flash_message: str | None,
    error_message: str | None,
    runtime_config: dict[str, object] | None = None,
) -> dict[str, object]:
    microsoft_settings = operator_settings.describe_microsoft_oauth_settings()
    connect_ready = _microsoft_connect_ready(microsoft_settings)
    return {
        "request": request,
        "microsoft_settings": microsoft_settings,
        "runtime_config": runtime_config or runtime_service.resolve(),
        "microsoft_accounts": runtime_service.list_accounts(),
        "calendar_catalog": runtime_service.list_calendars(),
        "flash_message": flash_message,
        "error_message": error_message,
        "connect_url": "/auth/microsoft/start",
        "connect_ready": connect_ready,
        "connect_label": (
            "Connect another Microsoft account"
            if bool(microsoft_settings.get("refresh_token_saved"))
            else "Connect Microsoft account"
        ),
        "connect_block_message": (
            None
            if connect_ready
            else "Save the shared Microsoft OAuth app before connecting a Microsoft account."
        ),
    }


@router.post("/google/setup")
def google_setup_update(
    request: Request,
    google_client_id: str = Form(""),
    google_client_secret: str = Form(""),
):
    operator_settings = OperatorSettingsService()
    try:
        operator_settings.set_google_oauth_settings(
            client_id=google_client_id,
            client_secret=google_client_secret,
            preserve_existing_secret=True,
        )
        flash_message = "Google OAuth settings saved securely."
        error_message = None
    except ValueError as exc:
        flash_message = None
        error_message = str(exc)

    runtime_service = GoogleRuntimeConfigService(operator_settings=operator_settings)
    return _templates.TemplateResponse(
        request,
        "google_setup.html",
        _build_google_setup_context(
            request,
            operator_settings=operator_settings,
            runtime_service=runtime_service,
            flash_message=flash_message,
            error_message=error_message,
        ),
        status_code=200 if error_message is None else 400,
    )


@router.post("/google/setup/refresh")
def google_setup_refresh(request: Request):
    operator_settings = OperatorSettingsService()
    requested_account_email = str((request.query_params.get("account_email") or "")).strip() or None
    try:
        client = _build_google_client_from_settings(
            operator_settings,
            account_email=requested_account_email,
        )
        selected_runtime = GoogleRuntimeConfigService(
            operator_settings=operator_settings
        ).resolve(account_email=requested_account_email)
        account_email = client.current_user_email()
        calendar_catalog = client.list_calendars()
        previous_account_email = str(selected_runtime["account_email"] or "").strip()
        if previous_account_email and previous_account_email.lower() != account_email.lower():
            operator_settings.remove_google_account(previous_account_email)
        operator_settings.upsert_google_account(
            account_label=account_email,
            account_email=account_email,
            refresh_token=str(selected_runtime["refresh_token"] or ""),
            calendars=calendar_catalog,
        )
        flash_message = "Google calendars refreshed from the live account."
        error_message = None
    except (GoogleCalendarError, ValueError) as exc:
        flash_message = None
        error_message = str(exc)

    runtime_service = GoogleRuntimeConfigService(operator_settings=operator_settings)
    return _templates.TemplateResponse(
        request,
        "google_setup.html",
        _build_google_setup_context(
            request,
            operator_settings=operator_settings,
            runtime_service=runtime_service,
            flash_message=flash_message,
            error_message=error_message,
        ),
        status_code=200 if error_message is None else 400,
    )


@router.post("/google/setup/disconnect")
def google_setup_disconnect(request: Request):
    operator_settings = OperatorSettingsService()
    operator_settings.clear_google_oauth_state()
    account_email = str((request.query_params.get("account_email") or "")).strip() or None
    if account_email:
        operator_settings.remove_google_account(account_email)
    else:
        operator_settings.clear_google_account_settings()
        operator_settings.clear_google_calendar_catalog()
    runtime_service = GoogleRuntimeConfigService(operator_settings=operator_settings)
    google_settings = operator_settings.describe_google_oauth_settings()
    runtime_config = runtime_service.resolve() if runtime_service.list_accounts() else {
        "account_label": "",
        "account_email": "",
        "refresh_token": "",
        "client_id": str(operator_settings.get_google_oauth_settings()["client_id"] or ""),
        "client_secret": str(operator_settings.get_google_oauth_settings()["client_secret"] or ""),
        "primary_calendar_id": "",
        "primary_calendar_name": "",
        "source": "product_vault" if google_settings["client_id"] else "missing",
        "ready": False,
        "calendars": [],
        "accounts": [],
    }
    return _templates.TemplateResponse(
        request,
        "google_setup.html",
        _build_google_setup_context(
            request,
            operator_settings=operator_settings,
            runtime_service=runtime_service,
            flash_message="Google account disconnected. The shared OAuth app is still saved.",
            error_message=None,
            runtime_config=runtime_config,
        ),
    )


@router.post("/google/setup/test")
def google_setup_run_write_test(
    request: Request,
    target_calendar_url: str = Form(""),
):
    service = AppointmentService()
    operator_settings = OperatorSettingsService()
    runtime_service = GoogleRuntimeConfigService(operator_settings=operator_settings)
    try:
        result = service.run_write_smoke_test(
            target_calendar_url=target_calendar_url,
            actor="console",
        )
        flash_message = _write_test_success_message(result)
        _record_write_test_verification(
            operator_settings,
            service,
            target_calendar_url=target_calendar_url,
            passed=True,
            message=flash_message,
            result=result,
        )
        error_message = None
    except (
        AppleCalDAVError,
        GoogleCalendarError,
        MicrosoftCalendarError,
        ValueError,
    ) as exc:
        flash_message = None
        error_message = str(exc)
        _record_write_test_verification(
            operator_settings,
            service,
            target_calendar_url=target_calendar_url,
            passed=False,
            message=error_message,
            result=None,
        )

    return _templates.TemplateResponse(
        request,
        "google_setup.html",
        _build_google_setup_context(
            request,
            operator_settings=operator_settings,
            runtime_service=runtime_service,
            flash_message=flash_message,
            error_message=error_message,
        ),
        status_code=200 if error_message is None else 400,
    )


@router.get("/auth/google/start")
def google_oauth_start(request: Request):
    operator_settings = OperatorSettingsService()
    oauth_settings = operator_settings.get_google_oauth_settings()
    client_id = str(oauth_settings["client_id"] or "").strip()
    client_secret = str(oauth_settings["client_secret"] or "").strip()
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Google OAuth settings are incomplete.")

    state = str(uuid4())
    operator_settings.set_google_oauth_state(state)
    redirect_uri = str(request.url_for("google_oauth_callback"))
    client = GoogleCalendarClient(
        GoogleOAuthConfig(
            account_label="Google",
            account_email="",
            client_id=client_id,
            client_secret=client_secret,
            refresh_token="placeholder",
            primary_calendar_id="primary",
            primary_calendar_name="Primary",
        )
    )
    return RedirectResponse(
        client.authorization_url(redirect_uri=redirect_uri, state=state),
        status_code=302,
    )


@router.get("/auth/google/callback", name="google_oauth_callback")
def google_oauth_callback(
    request: Request,
    state: str,
    code: str,
):
    operator_settings = OperatorSettingsService()
    expected_state = operator_settings.get_google_oauth_state()
    if not expected_state or state != expected_state:
        raise HTTPException(status_code=400, detail="Google OAuth state did not match.")
    operator_settings.clear_google_oauth_state()

    oauth_settings = operator_settings.get_google_oauth_settings()
    client_id = str(oauth_settings["client_id"] or "").strip()
    client_secret = str(oauth_settings["client_secret"] or "").strip()
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Google OAuth settings are incomplete.")

    client = GoogleCalendarClient(
        GoogleOAuthConfig(
            account_label="Google",
            account_email="",
            client_id=client_id,
            client_secret=client_secret,
            refresh_token="placeholder",
            primary_calendar_id="primary",
            primary_calendar_name="Primary",
        )
    )
    redirect_uri = str(request.url_for("google_oauth_callback"))
    token_payload = client.exchange_code(code=code, redirect_uri=redirect_uri)
    refresh_token = str(token_payload["refresh_token"] or "").strip()
    if not refresh_token:
        raise HTTPException(
            status_code=400,
            detail="Google did not return a refresh token. Reconnect with consent again.",
        )
    access_token = str(token_payload["access_token"] or "").strip()
    account_email = client.current_user_email(access_token=access_token)
    calendar_catalog = client.list_calendars(access_token=access_token)
    operator_settings.upsert_google_account(
        account_label=account_email,
        account_email=account_email,
        refresh_token=refresh_token,
        calendars=calendar_catalog,
    )

    runtime_service = GoogleRuntimeConfigService(operator_settings=operator_settings)
    runtime_config = runtime_service.resolve()
    return _templates.TemplateResponse(
        request,
        "google_setup.html",
        _build_google_setup_context(
            request,
            operator_settings=operator_settings,
            runtime_service=runtime_service,
            flash_message="Google account connected and calendars discovered.",
            error_message=None,
            runtime_config=runtime_config,
        ),
    )


@router.get("/microsoft/setup")
def microsoft_setup_page(request: Request):
    operator_settings = OperatorSettingsService()
    runtime_service = MicrosoftRuntimeConfigService(operator_settings=operator_settings)
    return _templates.TemplateResponse(
        request,
        "microsoft_setup.html",
        _build_microsoft_setup_context(
            request,
            operator_settings=operator_settings,
            runtime_service=runtime_service,
            flash_message=None,
            error_message=None,
        ),
    )


@router.post("/microsoft/setup")
def microsoft_setup_update(
    request: Request,
    microsoft_client_id: str = Form(""),
    microsoft_client_secret: str = Form(""),
):
    operator_settings = OperatorSettingsService()
    try:
        operator_settings.set_microsoft_oauth_settings(
            client_id=microsoft_client_id,
            client_secret=microsoft_client_secret,
            preserve_existing_secret=True,
        )
        flash_message = "Microsoft OAuth settings saved securely."
        error_message = None
    except ValueError as exc:
        flash_message = None
        error_message = str(exc)

    runtime_service = MicrosoftRuntimeConfigService(operator_settings=operator_settings)
    return _templates.TemplateResponse(
        request,
        "microsoft_setup.html",
        _build_microsoft_setup_context(
            request,
            operator_settings=operator_settings,
            runtime_service=runtime_service,
            flash_message=flash_message,
            error_message=error_message,
        ),
        status_code=200 if error_message is None else 400,
    )


@router.post("/microsoft/setup/refresh")
def microsoft_setup_refresh(request: Request):
    operator_settings = OperatorSettingsService()
    requested_account_email = str((request.query_params.get("account_email") or "")).strip() or None
    try:
        client = _build_microsoft_client_from_settings(
            operator_settings,
            account_email=requested_account_email,
        )
        selected_runtime = MicrosoftRuntimeConfigService(
            operator_settings=operator_settings
        ).resolve(account_email=requested_account_email)
        account_email = client.current_user_email()
        calendar_catalog = client.list_calendars()
        previous_account_email = str(selected_runtime["account_email"] or "").strip()
        if previous_account_email and previous_account_email.lower() != account_email.lower():
            operator_settings.remove_microsoft_account(previous_account_email)
        operator_settings.upsert_microsoft_account(
            account_label=account_email,
            account_email=account_email,
            refresh_token=str(selected_runtime["refresh_token"] or ""),
            calendars=calendar_catalog,
        )
        flash_message = "Microsoft calendars refreshed from the live account."
        error_message = None
    except (MicrosoftCalendarError, ValueError) as exc:
        flash_message = None
        error_message = str(exc)

    runtime_service = MicrosoftRuntimeConfigService(operator_settings=operator_settings)
    return _templates.TemplateResponse(
        request,
        "microsoft_setup.html",
        _build_microsoft_setup_context(
            request,
            operator_settings=operator_settings,
            runtime_service=runtime_service,
            flash_message=flash_message,
            error_message=error_message,
        ),
        status_code=200 if error_message is None else 400,
    )


@router.post("/microsoft/setup/disconnect")
def microsoft_setup_disconnect(request: Request):
    operator_settings = OperatorSettingsService()
    operator_settings.clear_microsoft_oauth_state()
    account_email = str((request.query_params.get("account_email") or "")).strip() or None
    if account_email:
        operator_settings.remove_microsoft_account(account_email)
    else:
        operator_settings.clear_microsoft_account_settings()
        operator_settings.clear_microsoft_calendar_catalog()
    runtime_service = MicrosoftRuntimeConfigService(operator_settings=operator_settings)
    microsoft_settings = operator_settings.describe_microsoft_oauth_settings()
    runtime_config = runtime_service.resolve() if runtime_service.list_accounts() else {
        "account_label": "",
        "account_email": "",
        "refresh_token": "",
        "client_id": str(operator_settings.get_microsoft_oauth_settings()["client_id"] or ""),
        "client_secret": str(operator_settings.get_microsoft_oauth_settings()["client_secret"] or ""),
        "primary_calendar_id": "",
        "primary_calendar_name": "",
        "source": "product_vault" if microsoft_settings["client_id"] else "missing",
        "ready": False,
        "calendars": [],
        "accounts": [],
    }
    return _templates.TemplateResponse(
        request,
        "microsoft_setup.html",
        _build_microsoft_setup_context(
            request,
            operator_settings=operator_settings,
            runtime_service=runtime_service,
            flash_message="Microsoft account disconnected. The shared OAuth app is still saved.",
            error_message=None,
            runtime_config=runtime_config,
        ),
    )


@router.post("/microsoft/setup/test")
def microsoft_setup_run_write_test(
    request: Request,
    target_calendar_url: str = Form(""),
):
    service = AppointmentService()
    operator_settings = OperatorSettingsService()
    runtime_service = MicrosoftRuntimeConfigService(operator_settings=operator_settings)
    try:
        result = service.run_write_smoke_test(
            target_calendar_url=target_calendar_url,
            actor="console",
        )
        flash_message = _write_test_success_message(result)
        _record_write_test_verification(
            operator_settings,
            service,
            target_calendar_url=target_calendar_url,
            passed=True,
            message=flash_message,
            result=result,
        )
        error_message = None
    except (
        AppleCalDAVError,
        GoogleCalendarError,
        MicrosoftCalendarError,
        ValueError,
    ) as exc:
        flash_message = None
        error_message = str(exc)
        _record_write_test_verification(
            operator_settings,
            service,
            target_calendar_url=target_calendar_url,
            passed=False,
            message=error_message,
            result=None,
        )

    return _templates.TemplateResponse(
        request,
        "microsoft_setup.html",
        _build_microsoft_setup_context(
            request,
            operator_settings=operator_settings,
            runtime_service=runtime_service,
            flash_message=flash_message,
            error_message=error_message,
        ),
        status_code=200 if error_message is None else 400,
    )


@router.get("/auth/microsoft/start")
def microsoft_oauth_start(request: Request):
    operator_settings = OperatorSettingsService()
    oauth_settings = operator_settings.get_microsoft_oauth_settings()
    client_id = str(oauth_settings["client_id"] or "").strip()
    client_secret = str(oauth_settings["client_secret"] or "").strip()
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Microsoft OAuth settings are incomplete.")

    state = str(uuid4())
    operator_settings.set_microsoft_oauth_state(state)
    redirect_uri = str(request.url_for("microsoft_oauth_callback"))
    client = MicrosoftCalendarClient(
        MicrosoftOAuthConfig(
            account_label="Microsoft",
            account_email="",
            client_id=client_id,
            client_secret=client_secret,
            refresh_token="placeholder",
            primary_calendar_id="primary",
            primary_calendar_name="Primary",
        )
    )
    return RedirectResponse(
        client.authorization_url(redirect_uri=redirect_uri, state=state),
        status_code=302,
    )


@router.get("/auth/microsoft/callback", name="microsoft_oauth_callback")
def microsoft_oauth_callback(
    request: Request,
    state: str,
    code: str,
):
    operator_settings = OperatorSettingsService()
    expected_state = operator_settings.get_microsoft_oauth_state()
    if not expected_state or state != expected_state:
        raise HTTPException(status_code=400, detail="Microsoft OAuth state did not match.")
    operator_settings.clear_microsoft_oauth_state()

    oauth_settings = operator_settings.get_microsoft_oauth_settings()
    client_id = str(oauth_settings["client_id"] or "").strip()
    client_secret = str(oauth_settings["client_secret"] or "").strip()
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Microsoft OAuth settings are incomplete.")

    client = MicrosoftCalendarClient(
        MicrosoftOAuthConfig(
            account_label="Microsoft",
            account_email="",
            client_id=client_id,
            client_secret=client_secret,
            refresh_token="placeholder",
            primary_calendar_id="primary",
            primary_calendar_name="Primary",
        )
    )
    redirect_uri = str(request.url_for("microsoft_oauth_callback"))
    token_payload = client.exchange_code(code=code, redirect_uri=redirect_uri)
    refresh_token = str(token_payload["refresh_token"] or "").strip()
    if not refresh_token:
        raise HTTPException(
            status_code=400,
            detail="Microsoft did not return a refresh token. Reconnect with consent again.",
        )
    access_token = str(token_payload["access_token"] or "").strip()
    account_email = client.current_user_email(access_token=access_token)
    calendar_catalog = client.list_calendars(access_token=access_token)
    operator_settings.upsert_microsoft_account(
        account_label=account_email,
        account_email=account_email,
        refresh_token=refresh_token,
        calendars=calendar_catalog,
    )

    runtime_service = MicrosoftRuntimeConfigService(operator_settings=operator_settings)
    runtime_config = runtime_service.resolve()
    return _templates.TemplateResponse(
        request,
        "microsoft_setup.html",
        _build_microsoft_setup_context(
            request,
            operator_settings=operator_settings,
            runtime_service=runtime_service,
            flash_message="Microsoft account connected and calendars discovered.",
            error_message=None,
            runtime_config=runtime_config,
        ),
    )


@router.post("/alexa/setup")
def alexa_setup_update(
    request: Request,
    allowed_skill_ids: str = Form(""),
    enable_alexa: str | None = Form(None),
):
    operator_settings = OperatorSettingsService()
    normalized_skill_ids = [
        value.strip() for value in allowed_skill_ids.split(",") if value.strip()
    ]
    operator_settings.set_desired_alexa_settings(
        enable_alexa=enable_alexa == "true",
        allowed_skill_ids=normalized_skill_ids,
    )
    service = CloudflareWorkerConfigService()
    try:
        edge_settings = service.update_alexa_settings(
            enable_alexa=enable_alexa == "true",
            allowed_skill_ids=normalized_skill_ids,
        )
        if edge_settings is None:
            edge_settings = service.get_alexa_settings()
        flash_message = "Desired Alexa settings saved and edge Worker updated."
        error_message = None
    except ValueError as exc:
        edge_settings = service.get_alexa_settings()
        flash_message = "Desired Alexa settings saved securely."
        error_message = str(exc)
    readiness = ReadinessService().build()

    return _render_alexa_setup_page(
        request,
        readiness=readiness,
        operator_settings=operator_settings,
        edge_settings=edge_settings,
        flash_message=flash_message,
        error_message=error_message,
        status_code=200,
    )


@router.post("/alexa/setup/cloudflare")
def alexa_setup_update_cloudflare_credentials(
    request: Request,
    cloudflare_account_id: str = Form(""),
    cloudflare_api_token: str = Form(""),
):
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

    readiness = ReadinessService().build()
    edge_settings = CloudflareWorkerConfigService().get_alexa_settings()
    return _render_alexa_setup_page(
        request,
        readiness=readiness,
        operator_settings=operator_settings,
        edge_settings=edge_settings,
        flash_message=flash_message,
        error_message=error_message,
        status_code=200 if error_message is None else 400,
    )


@router.get("/alexa/simulator")
def alexa_simulator_page(request: Request):
    service = AppointmentService()
    readiness = ReadinessService().build()
    calendar_name_options = _calendar_name_options(service)
    legacy_apple_recovery_hints = (
        OperatorSettingsService().describe_legacy_apple_recovery_hints()
    )
    return _templates.TemplateResponse(
        request,
        "alexa_simulator.html",
        {
            "request": request,
            "readiness": readiness,
            "simulator_state": _describe_alexa_simulator_state(
                readiness=readiness,
                calendar_name_options=calendar_name_options,
                recovery_mode=_alexa_recovery_mode(
                    readiness=readiness,
                    legacy_apple_recovery_hints=legacy_apple_recovery_hints,
                ),
            ),
            "simulation_result": None,
            "error_message": None,
            "form_values": _default_alexa_simulator_values(),
            "calendar_name_options": calendar_name_options,
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
    calendar_name: str = Form(""),
    duration_minutes: str = Form(""),
    end_date: str = Form(""),
    new_date: str = Form(""),
    new_start_time: str = Form(""),
    new_end_time: str = Form(""),
    new_calendar_name: str = Form(""),
):
    service = AppointmentService()
    form_values = {
        "request_type": request_type,
        "intent_name": intent_name,
        "title": title,
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "location": location,
        "notes": notes,
        "calendar_name": calendar_name,
        "duration_minutes": duration_minutes,
        "end_date": end_date,
        "new_date": new_date,
        "new_start_time": new_start_time,
        "new_end_time": new_end_time,
        "new_calendar_name": new_calendar_name,
    }
    slots = {
        "title": title,
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "location": location,
        "notes": notes,
        "calendar_name": calendar_name,
        "duration_minutes": duration_minutes,
        "end_date": end_date,
        "new_date": new_date,
        "new_start_time": new_start_time,
        "new_end_time": new_end_time,
        "new_calendar_name": new_calendar_name,
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
    readiness = ReadinessService().build()
    calendar_name_options = _calendar_name_options(service)
    legacy_apple_recovery_hints = (
        OperatorSettingsService().describe_legacy_apple_recovery_hints()
    )

    return _templates.TemplateResponse(
        request,
        "alexa_simulator.html",
        {
            "request": request,
            "readiness": readiness,
            "simulator_state": _describe_alexa_simulator_state(
                readiness=readiness,
                calendar_name_options=calendar_name_options,
                recovery_mode=_alexa_recovery_mode(
                    readiness=readiness,
                    legacy_apple_recovery_hints=legacy_apple_recovery_hints,
                ),
            ),
            "simulation_result": simulation_result,
            "error_message": error_message,
            "form_values": form_values,
            "calendar_name_options": calendar_name_options,
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
    availability_date_from: str | None = None,
    availability_date_to: str | None = None,
    availability_duration_minutes: int = 60,
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
    except (
        AppleCalDAVError,
        GoogleCalendarError,
        ModuleNotFoundError,
        SQLAlchemyError,
        ValueError,
    ):
        appointments = []
        selected_detail = None
        schedule_error = "Schedule data is unavailable right now."
    availability_form_values = _default_availability_form_values()
    if availability_date_from:
        availability_form_values["date_from"] = availability_date_from
    if availability_date_to:
        availability_form_values["date_to"] = availability_date_to
    availability_form_values["duration_minutes"] = availability_duration_minutes
    availability_results: list[AvailabilitySlot] = []
    availability_error: str | None = None
    availability_requested = bool(availability_date_from or availability_date_to)
    availability_ready = bool(service.available_calendars)
    availability_searched = availability_requested and availability_ready
    if availability_searched:
        try:
            availability_results = service.find_availability(
                date_from=str(availability_form_values["date_from"]),
                date_to=str(availability_form_values["date_to"]),
                duration_minutes=availability_duration_minutes,
            ).items
        except (AppleCalDAVError, GoogleCalendarError, ValueError) as exc:
            availability_error = str(exc)
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
            availability_form_values=availability_form_values,
            availability_results=availability_results,
            availability_error=availability_error,
            availability_searched=availability_searched,
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
    except (AppleCalDAVError, GoogleCalendarError, ValueError) as exc:
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
                availability_form_values=_default_availability_form_values(),
                availability_results=[],
                availability_error=None,
                availability_searched=False,
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
    except (AppleCalDAVError, GoogleCalendarError) as exc:
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
    except (AppleCalDAVError, GoogleCalendarError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
    availability_form_values: dict[str, object],
    availability_results: list[AvailabilitySlot],
    availability_error: str | None,
    availability_searched: bool,
    selected_window: str,
    show_cancelled: bool,
    readiness: dict[str, object],
) -> dict[str, object]:
    origin = readiness.get("origin", {}) if isinstance(readiness, dict) else {}
    any_calendar_ready = bool(origin.get("any_calendar_ready"))
    legacy_recovery_hints = OperatorSettingsService().describe_legacy_apple_recovery_hints()
    visible_appointments = appointments if any_calendar_ready else []
    visible_selected_detail = selected_detail if any_calendar_ready else None
    hero_subject = visible_appointments[0] if visible_appointments else None
    calendar_options = _calendar_options(
        service,
        selected_calendar_url=str(form_values.get("target_calendar_url") or ""),
    )
    create_ready = bool(calendar_options)
    availability_ready = create_ready
    schedule_ready = create_ready
    root_recovery_mode = (
        not schedule_ready
        and str(legacy_recovery_hints.get("source") or "missing") != "missing"
    )
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
        "create_ready": create_ready,
        "create_block_message": (
            None
            if create_ready
            else (
                "Apple reconnect still blocks write actions. Open Apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password before creating appointments from the schedule workspace."
                if root_recovery_mode
                else "Connect a writable calendar before creating appointments from the schedule workspace."
            )
        ),
        "availability_form_values": availability_form_values,
        "schedule_ready": schedule_ready,
        "schedule_block_message": (
            None
            if schedule_ready
            else (
                "Apple reconnect still blocks live schedule sync. Open Apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password before expecting a real household schedule here."
                if root_recovery_mode
                else "Connect a writable calendar before CalSync can show a real live schedule window."
            )
        ),
        "detail_block_message": (
            None
            if schedule_ready
            else (
                "Apple reconnect still blocks appointment detail. Open Apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password before expecting appointment activity here."
                if root_recovery_mode
                else "Choose a calendar connection before expecting appointment detail or activity here."
            )
        ),
        "availability_ready": availability_ready,
        "availability_block_message": (
            None
            if availability_ready
            else (
                "Apple reconnect still blocks availability search. Open Apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password before searching for open time from the schedule workspace."
                if root_recovery_mode
                else "Connect a writable calendar before searching for open time from the schedule workspace."
            )
        ),
        "availability_results": _serialize_availability_results(availability_results),
        "availability_error": availability_error,
        "availability_searched": availability_searched,
        "calendar_label": service.display_calendar_name,
        "account_label": service.display_account_label,
        "calendar_options": calendar_options,
        "selected_window": selected_window,
        "show_cancelled": show_cancelled,
        "window_options": _window_options(
            selected_window=selected_window,
            show_cancelled=show_cancelled,
            selected_appointment_id=(
                visible_selected_detail.appointment_id
                if visible_selected_detail
                else None
            ),
        ),
        "window_label": _WINDOWS[selected_window][0],
        "window_summary": _window_summary(selected_window),
        "schedule_board": _build_schedule_board(
            visible_appointments,
            selected_window=selected_window,
            show_cancelled=show_cancelled,
            selected_appointment_id=(
                visible_selected_detail.appointment_id
                if visible_selected_detail
                else None
            ),
        ),
        "workspace_capabilities": _workspace_capabilities(
            readiness,
            recovery_mode=root_recovery_mode,
        ),
        "selected_appointment": _serialize_detail(visible_selected_detail),
        "appointment_count": len(visible_appointments),
        "active_count": len(visible_appointments),
        "cancelled_count": sum(
            1 for item in visible_appointments if item.status == "cancelled"
        ),
        "next_up_label": _next_up_label(hero_subject),
        "hero_ready": any_calendar_ready,
        "readiness": readiness,
    }


def _booking_setup_recovery_mode(
    *,
    operator_settings: OperatorSettingsService,
) -> bool:
    legacy_apple_recovery_hints = operator_settings.describe_legacy_apple_recovery_hints()
    return str(legacy_apple_recovery_hints.get("source") or "missing") != "missing"


def _describe_booking_setup_block_message(*, recovery_mode: bool) -> str:
    if recovery_mode:
        return "Apple reconnect still blocks booking setup. Open Apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password before configuring public booking."
    return "Connect a writable calendar before configuring public booking settings or creating shareable booking types."


def _describe_booking_setup_save_error(*, recovery_mode: bool) -> str:
    if recovery_mode:
        return "Apple reconnect still blocks saving booking setup. Open Apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password before saving public booking settings."
    return "Connect a writable calendar before saving public booking settings."


def _describe_booking_setup_type_error(*, recovery_mode: bool) -> str:
    if recovery_mode:
        return "Apple reconnect still blocks new booking types. Open Apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password before creating public booking types."
    return "Connect a writable calendar before creating public booking types."


def _describe_public_booking_availability_block_message(*, recovery_mode: bool) -> str:
    if recovery_mode:
        return "Apple reconnect still blocks public booking availability. Open Apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password before invitees can search for open time."
    return "Connect a writable calendar before public booking can search for open time."


def _describe_public_booking_not_ready_message(*, recovery_mode: bool) -> str:
    if recovery_mode:
        return "Apple reconnect still blocks public booking. Open Apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password before invitees can request time."
    return "CalSync needs one writable calendar target before invitees can request time."


def _describe_public_booking_target_status(*, recovery_mode: bool) -> tuple[str, str]:
    if recovery_mode:
        return (
            "Apple reconnect still needed",
            "Recovered Apple hints are ready. Open Apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password before this public booking flow can go live.",
        )
    return (
        "Not ready yet",
        "CalSync needs at least one writable calendar before public booking can go live.",
    )


def _build_booking_context(
    request: Request,
    *,
    service: AppointmentService,
    booking_settings: dict[str, object],
    availability_date_from: str | None,
    availability_date_to: str | None,
    availability_duration_minutes: int | None,
    booking_form_values: dict[str, object],
    flash_message: str | None,
    error_message: str | None,
    booking_confirmation: dict[str, object] | None,
    booking_types: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    defaults = _default_booking_availability_form_values(booking_settings=booking_settings)
    recovery_mode = _booking_setup_recovery_mode(
        operator_settings=OperatorSettingsService()
    )
    form_values = {
        "date_from": availability_date_from or str(defaults["date_from"]),
        "date_to": availability_date_to or str(defaults["date_to"]),
        "duration_minutes": availability_duration_minutes or int(defaults["duration_minutes"]),
    }
    target = _default_booking_target(
        service,
        configured_target_calendar_url=str(booking_settings.get("target_calendar_url") or ""),
    )
    availability_results: list[AvailabilitySlot] = []
    availability_error: str | None = None
    target_status, target_message = _describe_public_booking_target_status(
        recovery_mode=recovery_mode
    )
    if target is not None:
        try:
            availability_results = service.find_availability(
                date_from=str(form_values["date_from"]),
                date_to=str(form_values["date_to"]),
                duration_minutes=int(form_values["duration_minutes"]),
                allowed_weekdays=[
                    int(value) for value in booking_settings.get("booking_weekdays", [])
                ],
                day_start_time=str(booking_settings.get("day_start_time") or "08:00"),
                day_end_time=str(booking_settings.get("day_end_time") or "18:00"),
            ).items
        except (ValueError, AppleCalDAVError, GoogleCalendarError, MicrosoftCalendarError) as exc:
            availability_error = str(exc)
    return {
        "request": request,
        "flash_message": flash_message,
        "error_message": error_message or availability_error,
        "booking_confirmation": booking_confirmation,
        "booking_form_values": booking_form_values,
        "booking_settings": booking_settings,
        "public_booking_url": str(booking_settings.get("public_url") or "/book"),
        "booking_catalog_mode": False,
        "booking_types": booking_types or [],
        "availability_form_values": form_values,
        "availability_ready": target is not None,
        "recovery_mode": recovery_mode,
        "availability_block_message": (
            None
            if target is not None
            else _describe_public_booking_availability_block_message(
                recovery_mode=recovery_mode
            )
        ),
        "availability_results": _serialize_booking_slots(availability_results),
        "calendar_target": target,
        "calendar_ready": target is not None,
        "calendar_target_status": (
            str(target.get("label") or "Connected calendar target")
            if target is not None
            else target_status
        ),
        "calendar_target_message": (
            "This public booking flow writes into the selected connected calendar target."
            if target is not None
            else target_message
        ),
        "public_booking_not_ready_message": _describe_public_booking_not_ready_message(
            recovery_mode=recovery_mode
        ),
    }


def _load_public_booking_settings(
    operator_settings: OperatorSettingsService,
    *,
    booking_slug: str | None,
) -> dict[str, object]:
    normalized_slug = str(booking_slug or "").strip()
    if normalized_slug:
        available_slugs = {
            str(item["slug"])
            for item in operator_settings.describe_public_booking_types()
        }
        if normalized_slug not in available_slugs:
            raise HTTPException(status_code=404, detail="Booking type not found.")
        return operator_settings.describe_public_booking_settings(slug=normalized_slug)
    return operator_settings.describe_public_booking_settings()


def _build_schedule_board(
    appointments: list[AppointmentListItem],
    *,
    selected_window: str,
    show_cancelled: bool,
    selected_appointment_id: str | None,
) -> dict[str, object]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for item in appointments:
        grouped.setdefault(item.date, []).append(
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
        )

    window_start, window_end, _ = _resolve_window(selected_window)
    if selected_window == "month":
        return _build_month_board(
            grouped,
            window_start=window_start,
            window_end=window_end,
        )
    return _build_column_board(
        grouped,
        selected_window=selected_window,
        window_start=window_start,
        window_end=window_end,
    )


def _build_column_board(
    grouped: dict[str, list[dict[str, object]]],
    *,
    selected_window: str,
    window_start: date,
    window_end: date,
) -> dict[str, object]:
    columns: list[dict[str, object]] = []
    cursor = window_start
    today = _today_in_alaska()
    while cursor <= window_end:
        day_key = cursor.isoformat()
        columns.append(
            {
                "eyebrow": _schedule_eyebrow(day_key),
                "date_label": _friendly_date_label(day_key),
                "entries": grouped.get(day_key, []),
                "is_today": cursor == today,
            }
        )
        cursor += timedelta(days=1)
    return {
        "mode": selected_window,
        "title": "Day board" if selected_window == "day" else "Week board",
        "description": (
            "Focus on the immediate day with one clean planning lane."
            if selected_window == "day"
            else "See the next seven days in parallel so it feels like real calendar planning."
        ),
        "has_appointments": any(column["entries"] for column in columns),
        "columns": columns,
    }


def _build_month_board(
    grouped: dict[str, list[dict[str, object]]],
    *,
    window_start: date,
    window_end: date,
) -> dict[str, object]:
    grid_start = window_start - timedelta(days=window_start.weekday())
    grid_end = window_end + timedelta(days=6 - window_end.weekday())
    weeks: list[dict[str, object]] = []
    today = _today_in_alaska()
    cursor = grid_start
    while cursor <= grid_end:
        days: list[dict[str, object]] = []
        for _ in range(7):
            day_key = cursor.isoformat()
            entries = grouped.get(day_key, [])
            days.append(
                {
                    "eyebrow": cursor.strftime("%a").upper(),
                    "day_number": cursor.day,
                    "date_label": _friendly_date_label(day_key),
                    "entries": entries[:3],
                    "overflow_count": max(0, len(entries) - 3),
                    "is_today": cursor == today,
                    "is_in_window": window_start <= cursor <= window_end,
                }
            )
            cursor += timedelta(days=1)
        weeks.append({"days": days})
    return {
        "mode": "month",
        "title": "Month board",
        "description": "See the next 30 days as a real planning board instead of a long undifferentiated list.",
        "has_appointments": any(day["entries"] for week in weeks for day in week["days"]),
        "weeks": weeks,
    }


def _workspace_capabilities(
    readiness: dict[str, object],
    *,
    recovery_mode: bool = False,
) -> list[str]:
    origin = readiness.get("origin", {})
    edge = readiness.get("edge", {})
    desired_alexa = readiness.get("desired_alexa", {})
    any_calendar_ready = bool(origin.get("any_calendar_ready"))
    items: list[str] = ["Browse day, week, and month windows"]
    if any_calendar_ready:
        items.insert(0, "Create, edit, and cancel appointments")
        items.insert(0, "Read and sync existing connected calendar events")
    else:
        items.insert(
            0,
            (
                "Open Apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password to unlock create, edit, and cancel appointments."
                if recovery_mode
                else "Connect a writable calendar to unlock create, edit, and cancel appointments."
            ),
        )
    if origin.get("apple_ready"):
        items.append("Write to connected Apple calendars")
    if origin.get("google_ready"):
        items.append("Write to connected Google calendars")
    else:
        items.append("Google write path is built and waiting for setup")
    if origin.get("microsoft_ready"):
        items.append("Write to connected Microsoft calendars")
    else:
        items.append("Microsoft write path is built and waiting for setup")
    if edge.get("alexa", {}).get("enabled"):
        items.append("Use the same scheduling brain through Alexa live")
    elif desired_alexa.get("saved"):
        items.append("Alexa turn-on plan is saved and waiting for edge apply")
    else:
        items.append("Preview Alexa through the setup flow and simulator before live turn-on")
    return items


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
    if provider_type == "google_calendar":
        return "Google Calendar"
    if provider_type == "microsoft_calendar":
        return "Microsoft Calendar"
    return provider_type.replace("_", " ").title()


def _write_test_success_message(result: dict[str, str]) -> str:
    return (
        f"Write test passed for {result['calendar_name']} on "
        f"{result['provider_label']}"
        + (f" ({result['account_label']})" if result["account_label"] else "")
        + "."
    )


def _record_write_test_verification(
    operator_settings: OperatorSettingsService,
    service: AppointmentService,
    *,
    target_calendar_url: str,
    passed: bool,
    message: str,
    result: dict[str, str] | None,
) -> None:
    try:
        described_target = service.describe_target_calendar(target_calendar_url)
        target = {
            "provider_type": str(
                (result or {}).get("provider_type")
                or described_target["provider_type"]
            ),
            "provider_label": str(
                (result or {}).get("provider_label")
                or described_target["provider_label"]
            ),
            "account_label": str(
                (result or {}).get("account_label")
                or described_target.get("account_label")
                or ""
            ),
            "calendar_name": str(
                (result or {}).get("calendar_name")
                or described_target["calendar_name"]
            ),
            "target_value": str(
                (result or {}).get("target_value")
                or target_calendar_url
            ),
        }
        operator_settings.record_calendar_write_verification(
            target_value=target["target_value"],
            provider_type=str(target["provider_type"]),
            provider_label=str(target["provider_label"]),
            account_label=str(target.get("account_label") or ""),
            calendar_name=str(target["calendar_name"]),
            passed=passed,
            message=message,
            checked_at=datetime.now(UTC).isoformat(),
        )
    except ValueError:
        return


def _build_connections_context(
    request: Request,
    *,
    flash_message: str | None,
    error_message: str | None,
) -> dict[str, object]:
    operator_settings = OperatorSettingsService()
    cloudflare_worker_service = CloudflareWorkerConfigService()
    apple_runtime_service = AppleRuntimeConfigService(operator_settings=operator_settings)
    google_runtime_service = GoogleRuntimeConfigService(operator_settings=operator_settings)
    microsoft_runtime_service = MicrosoftRuntimeConfigService(operator_settings=operator_settings)
    apple_settings = operator_settings.describe_apple_calendar_settings()
    legacy_apple_recovery_hints = operator_settings.describe_legacy_apple_recovery_hints()
    google_settings = operator_settings.describe_google_oauth_settings()
    microsoft_settings = operator_settings.describe_microsoft_oauth_settings()
    apple_runtime = apple_runtime_service.resolve()
    google_runtime = google_runtime_service.resolve()
    microsoft_runtime = microsoft_runtime_service.resolve()
    readiness = ReadinessService().build()
    edge_settings = cloudflare_worker_service.get_alexa_settings()
    desired_alexa_settings = operator_settings.describe_desired_alexa_settings()
    alexa_drift = _describe_alexa_settings_drift(
        desired_settings=desired_alexa_settings,
        edge_settings=edge_settings,
    )
    cloudflare_credentials = operator_settings.describe_cloudflare_worker_credentials()
    account_linking_settings = operator_settings.describe_alexa_account_linking_settings()
    verification_map = {
        str(item["target_value"]): item
        for item in operator_settings.get_calendar_write_verifications()
    }
    apple_targets = _decorate_connection_targets(
        apple_runtime_service.list_calendars(),
        provider_type="apple",
        verification_map=verification_map,
    )
    google_targets = _decorate_connection_targets(
        google_runtime_service.list_calendars(),
        provider_type="google",
        verification_map=verification_map,
    )
    microsoft_targets = _decorate_connection_targets(
        microsoft_runtime_service.list_calendars(),
        provider_type="microsoft",
        verification_map=verification_map,
    )
    verification_targets = [
        *apple_targets,
        *google_targets,
        *microsoft_targets,
    ]
    passed_verifications = [
        item for item in verification_targets if item["verification_status"] == "passed"
    ]
    failed_verifications = [
        item for item in verification_targets if item["verification_status"] == "failed"
    ]
    setup_checklist = [
        {
            "label": "Apple calendar path",
            "status_label": "Ready" if apple_runtime["ready"] else "Needs setup",
            "detail": (
                "Apple credentials and a writable target are available."
                if apple_runtime["ready"]
                else (
                    "Recovered Apple hints are ready. Apple setup already opens with the recommended calendar loaded, so add a fresh app-specific password and save."
                    if legacy_apple_recovery_hints.get("source") != "missing"
                    else "Save the household Apple connection to unlock the first live calendar path."
                )
            ),
        },
        {
            "label": "Google calendar path",
            "status_label": "Ready" if google_runtime["ready"] else "Needs setup",
            "detail": (
                "Google OAuth, account connect, and at least one writable target are ready."
                if google_runtime["ready"]
                else "Save the shared Google OAuth app and connect a browser-approved account."
            ),
        },
        {
            "label": "Microsoft calendar path",
            "status_label": "Ready" if microsoft_runtime["ready"] else "Needs setup",
            "detail": (
                "Microsoft OAuth, account connect, and at least one writable target are ready."
                if microsoft_runtime["ready"]
                else "Save the shared Microsoft OAuth app and connect an Outlook account."
            ),
        },
        {
            "label": "Alexa edge route",
            "status_label": (
                "Ready"
                if readiness.get("edge", {}).get("reachable")
                and readiness.get("edge", {}).get("alexa", {}).get("enabled")
                and account_linking_settings.get("configured")
                else "Needs setup"
            ),
            "detail": (
                "The edge Worker can accept Alexa traffic and account linking is configured."
                if readiness.get("edge", {}).get("reachable")
                and readiness.get("edge", {}).get("alexa", {}).get("enabled")
                and account_linking_settings.get("configured")
                else (
                    "Save a household link code, then finish edge enablement and skill allowlisting before real device traffic is live."
                    if not account_linking_settings.get("configured")
                    else "Finish edge enablement and skill allowlisting before real device traffic is live."
                )
            ),
        },
    ]
    return {
        "request": request,
        "apple_settings": apple_settings,
        "legacy_apple_recovery_hints": legacy_apple_recovery_hints,
        "apple_runtime": apple_runtime,
        "apple_accounts": apple_runtime_service.list_accounts(),
        "apple_calendar_catalog": apple_runtime_service.list_calendars(),
        "google_settings": google_settings,
        "google_connect_ready": _google_connect_ready(google_settings),
        "google_runtime": google_runtime,
        "google_accounts": google_runtime_service.list_accounts(),
        "google_calendar_catalog": google_runtime_service.list_calendars(),
        "microsoft_settings": microsoft_settings,
        "microsoft_connect_ready": _microsoft_connect_ready(microsoft_settings),
        "microsoft_runtime": microsoft_runtime,
        "microsoft_accounts": microsoft_runtime_service.list_accounts(),
        "microsoft_calendar_catalog": microsoft_runtime_service.list_calendars(),
        "readiness": readiness,
        "edge_settings": edge_settings,
        "desired_alexa_settings": desired_alexa_settings,
        "alexa_drift": alexa_drift,
        "alexa_action_copy": _describe_alexa_action_copy(edge_settings=edge_settings),
        "alexa_next_action": _describe_alexa_next_action(
            readiness=readiness,
            desired_settings=desired_alexa_settings,
            account_linking_settings=account_linking_settings,
            cloudflare_credentials=cloudflare_credentials,
            legacy_apple_recovery_hints=legacy_apple_recovery_hints,
        ),
        "alexa_finish_line_action": _describe_alexa_finish_line_action(
            readiness=readiness,
            account_linking_settings=account_linking_settings,
            cloudflare_credentials=cloudflare_credentials,
            legacy_apple_recovery_hints=legacy_apple_recovery_hints,
        ),
        "cloudflare_credentials": cloudflare_credentials,
        "account_linking_settings": account_linking_settings,
        "flash_message": flash_message,
        "error_message": error_message,
        "setup_checklist": setup_checklist,
        "apple_targets": apple_targets,
        "google_targets": google_targets,
        "microsoft_targets": microsoft_targets,
        "verification_targets": verification_targets,
        "passed_verification_count": len(passed_verifications),
        "failed_verification_count": len(failed_verifications),
        "verified_target_count": len(
            [item for item in verification_targets if item["verification_status"] != "unverified"]
        ),
    }


def _decorate_connection_targets(
    targets: list[dict[str, object]],
    *,
    provider_type: str,
    verification_map: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    decorated: list[dict[str, object]] = []
    for item in targets:
        target_value = str(
            item.get("target_value")
            or item.get("calendar_url")
            or item.get("calendar_id")
            or ""
        )
        verification = verification_map.get(target_value)
        verification_status = (
            str(verification["status"]) if verification is not None else "unverified"
        )
        decorated.append(
            {
                "provider_type": provider_type,
                "provider_label": _provider_label(
                    {
                        "apple": "icloud_caldav",
                        "google": "google_calendar",
                        "microsoft": "microsoft_calendar",
                    }[provider_type]
                ),
                "target_value": target_value,
                "calendar_name": str(item.get("calendar_name") or ""),
                "account_label": str(
                    item.get("account_label")
                    or item.get("username")
                    or item.get("account_email")
                    or ""
                ),
                "is_default": bool(item.get("is_default")),
                "verification_status": verification_status,
                "verification_status_label": {
                    "passed": "Verified",
                    "failed": "Needs attention",
                    "unverified": "Not yet verified",
                }[verification_status],
                "verification_message": (
                    str(verification["message"])
                    if verification is not None
                    else "Run the in-product write test to prove this path can create, update, and cancel safely."
                ),
                "verification_checked_at_label": (
                    _friendly_timestamp(str(verification["checked_at"]))
                    if verification is not None
                    else ""
                ),
            }
        )
    return decorated


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
        return "Created in CalSync and written to the connected calendar."
    if action == "update_appointment":
        changed_fields = []
        for key in ("title", "date", "start_time", "end_time", "location", "notes"):
            if key in payload:
                changed_fields.append(key.replace("_", " "))
        if changed_fields:
            readable = ", ".join(changed_fields)
            return f"Updated {readable} and synced the same connected calendar event."
        return "Updated this appointment and synced the same connected calendar event."
    if action == "cancel_appointment":
        return "Cancelled in CalSync and removed from the connected calendar."
    return "Recorded activity for this appointment."


def _flash_message(
    created: str | None,
    updated: str | None,
    cancelled: str | None,
) -> str | None:
    if created:
        return "Appointment created on the connected calendar."
    if updated:
        return "Appointment updated on the connected calendar."
    if cancelled:
        return "Appointment cancelled on the connected calendar."
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


def _default_availability_form_values() -> dict[str, object]:
    start = _today_in_alaska()
    return {
        "date_from": start.isoformat(),
        "date_to": (start + timedelta(days=6)).isoformat(),
        "duration_minutes": 60,
    }


def _default_booking_availability_form_values(
    *,
    booking_settings: dict[str, object],
) -> dict[str, object]:
    start = _today_in_alaska()
    search_window_days = max(7, int(booking_settings.get("search_window_days") or 7))
    return {
        "date_from": start.isoformat(),
        "date_to": (start + timedelta(days=search_window_days - 1)).isoformat(),
        "duration_minutes": int(booking_settings.get("duration_minutes") or 60),
    }


def _empty_booking_form_values() -> dict[str, object]:
    return {
        "title": "",
        "requester_name": "",
        "requester_contact": "",
        "attendees_text": "",
        "location": "",
        "notes": "",
        "slot_value": "",
    }


def _public_booking_notes(
    *,
    requester_name: str,
    requester_contact: str,
    notes: str,
) -> str:
    header = [
        f"Requested by: {requester_name.strip()}",
        f"Contact: {requester_contact.strip()}",
    ]
    extra_notes = notes.strip()
    if extra_notes:
        header.extend(["", extra_notes])
    return "\n".join(header)


def _serialize_availability_results(
    items: list[AvailabilitySlot],
) -> list[dict[str, str]]:
    return [
        {
            "date_label": _friendly_date_label(item.date, include_weekday=True),
            "time_label": f"{_to_12_hour(item.start_time)} - {_to_12_hour(item.end_time)}",
            "timezone": item.timezone,
        }
        for item in items
    ]


def _serialize_booking_slots(
    items: list[AvailabilitySlot],
) -> list[dict[str, str | bool]]:
    slots = _serialize_availability_results(items)
    serialized: list[dict[str, str | bool]] = []
    for index, item in enumerate(items):
        serialized.append(
            {
                **slots[index],
                "slot_value": f"{item.date}|{item.start_time}|{item.end_time}|{item.timezone}",
                "is_default": index == 0,
            }
        )
    return serialized


def _calendar_options(
    service: AppointmentService,
    *,
    selected_calendar_url: str | None,
) -> list[dict[str, object]]:
    selected_value = selected_calendar_url or ""
    options: list[dict[str, object]] = []
    for item in service.available_calendars:
        calendar_url = str(item["calendar_url"])
        account_label = str(item.get("account_label") or "").strip()
        provider_type = str(item.get("provider_type") or "").strip()
        provider_label = _provider_label(provider_type) if provider_type else ""
        label_parts = [str(item["calendar_name"])]
        if provider_label:
            label_parts.append(provider_label)
        if account_label:
            label_parts.append(account_label)
        options.append(
            {
                "label": " · ".join(label_parts),
                "value": calendar_url,
                "is_selected": calendar_url == selected_value
                or (not selected_value and bool(item.get("is_default"))),
            }
        )
    return options


def _default_booking_target(
    service: AppointmentService,
    *,
    configured_target_calendar_url: str,
) -> dict[str, object] | None:
    calendars = service.available_calendars
    if not calendars:
        return None
    configured_value = str(configured_target_calendar_url or "").strip()
    if configured_value and any(
        str(item["calendar_url"]) == configured_value for item in calendars
    ):
        selected_value = configured_value
    else:
        selected_value = next(
            (str(item["calendar_url"]) for item in calendars if bool(item.get("is_default"))),
            str(calendars[0]["calendar_url"]),
        )
    options = _calendar_options(service, selected_calendar_url=selected_value)
    selected_option = next(option for option in options if bool(option["is_selected"]))
    return {
        "label": str(selected_option["label"]),
        "value": selected_value,
    }


def _parse_booking_slot_value(value: str) -> tuple[str, str, str, str]:
    parts = str(value or "").split("|")
    if len(parts) != 4 or not all(parts):
        raise ValueError("Choose an available time before requesting a booking.")
    return parts[0], parts[1], parts[2], parts[3]


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
        "calendar_name": "",
        "duration_minutes": "60",
        "end_date": next_day.isoformat(),
        "new_date": next_day.isoformat(),
        "new_start_time": "13:00",
        "new_end_time": "14:00",
        "new_calendar_name": "",
    }


def _render_alexa_account_linking_authorize_page(
    request: Request,
    *,
    operator_settings: OperatorSettingsService,
    form_values: dict[str, str],
    error_message: str | None,
    status_code: int,
):
    return _templates.TemplateResponse(
        request,
        "alexa_account_linking_authorize.html",
        {
            "request": request,
            "form_values": form_values,
            "account_linking_settings": operator_settings.describe_alexa_account_linking_settings(),
            "error_message": error_message,
        },
        status_code=status_code,
    )


def _is_allowed_alexa_redirect_uri(redirect_uri: str) -> bool:
    try:
        parsed = urlparse(redirect_uri)
    except ValueError:
        return False
    host = str(parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        return False
    if not (
        host.endswith(".amazon.com")
        or host == "amazon.com"
        or host.endswith(".amazon.co.jp")
    ):
        return False
    return parsed.path == "/spa/skill/account-linking-status.html" or parsed.path.startswith(
        "/api/skill/link/"
    )


def _describe_alexa_settings_drift(
    *,
    desired_settings: dict[str, object],
    edge_settings: dict[str, object],
) -> dict[str, object]:
    desired_enabled = bool(desired_settings.get("enable_alexa"))
    live_enabled = bool(edge_settings.get("enable_alexa"))
    desired_skill_ids = [
        str(value).strip()
        for value in desired_settings.get("allowed_skill_ids", [])
        if str(value).strip()
    ]
    live_skill_ids = [
        str(value).strip()
        for value in edge_settings.get("allowed_skill_ids", [])
        if str(value).strip()
    ]
    pending_enable_change = desired_enabled != live_enabled
    pending_skill_id_change = desired_skill_ids != live_skill_ids
    pending_changes = pending_enable_change or pending_skill_id_change
    if not desired_settings.get("saved"):
        message = "No desired Alexa edge state has been saved in the product yet."
    elif pending_changes:
        message = "Desired Alexa settings differ from the live Worker and still need to be applied."
    else:
        message = "Desired Alexa settings already match the live Worker."
    return {
        "pending_changes": pending_changes,
        "pending_enable_change": pending_enable_change,
        "pending_skill_id_change": pending_skill_id_change,
        "message": message,
        "live_skill_id_count": len(live_skill_ids),
        "desired_skill_id_count": len(desired_skill_ids),
    }


def _describe_alexa_action_copy(
    *,
    edge_settings: dict[str, object],
) -> dict[str, str | bool]:
    manageable = bool(edge_settings.get("manageable"))
    if manageable:
        return {
            "manageable": True,
            "setup_button_label": "Apply edge settings",
            "connections_button_label": "Apply Alexa settings",
            "helper_message": "This will save the desired Alexa plan in CalSync and update the live edge Worker now.",
        }
    return {
        "manageable": False,
        "setup_button_label": "Save desired Alexa settings",
        "connections_button_label": "Save desired Alexa settings",
        "helper_message": "Cloudflare Worker access is still missing, so this will save the desired Alexa plan in CalSync until live edge updates are available.",
    }


def _describe_alexa_next_action(
    *,
    readiness: dict[str, object],
    desired_settings: dict[str, object],
    account_linking_settings: dict[str, object],
    cloudflare_credentials: dict[str, object],
    legacy_apple_recovery_hints: dict[str, object],
) -> str:
    origin = readiness.get("origin", {})
    edge = readiness.get("edge", {})
    channel_tokens = readiness.get("channel_tokens", {})
    edge_alexa = edge.get("alexa", {})
    desired_skill_ids = [
        str(value).strip()
        for value in desired_settings.get("allowed_skill_ids", [])
        if str(value).strip()
    ]
    account_linking_ready = bool(account_linking_settings.get("configured"))
    cloudflare_ready = bool(cloudflare_credentials.get("api_token_saved"))
    recovery_mode = _alexa_recovery_mode(
        readiness=readiness,
        legacy_apple_recovery_hints=legacy_apple_recovery_hints,
    )
    if not origin.get("any_calendar_ready") and not cloudflare_credentials.get(
        "api_token_saved"
    ):
        if recovery_mode and not account_linking_ready:
            return "Open Apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password, then save a household link code and Cloudflare Worker access so CalSync can finish Alexa account linking and live edge turn-on."
        if recovery_mode:
            return "Open Apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password, then save Cloudflare Worker access so you can turn on the live Alexa route from CalSync."
        if not account_linking_ready:
            return "Connect at least one writable calendar, then save a household link code and Cloudflare Worker access so CalSync can finish Alexa account linking and live edge turn-on."
        return "Connect at least one writable calendar, then save Cloudflare Worker access so you can turn on the live Alexa route from CalSync."
    if not origin.get("any_calendar_ready"):
        if recovery_mode and not account_linking_ready:
            return "Open Apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password, then save a household link code so the live skill can link to the right CalSync household."
        if recovery_mode:
            return "Open Apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password so Alexa has a real schedule to read and write once voice traffic goes live."
        if not account_linking_ready:
            return "Connect at least one writable calendar, then save a household link code so the live skill can link to the right CalSync household."
        return "Connect at least one writable calendar so Alexa has a real schedule to read and write once voice traffic goes live."
    if not account_linking_ready and not cloudflare_ready:
        return "Save a household link code and Cloudflare Worker access so CalSync can finish Alexa account linking and live edge turn-on."
    if not cloudflare_ready:
        return "Save Cloudflare Worker access so CalSync can turn on the live Alexa route and skill allowlist from the product."
    if not account_linking_ready:
        return "Save a household link code so Alexa account linking can hand the live skill a bearer token."
    if not desired_settings.get("saved"):
        return "Save the Alexa plan and your real skill ID so CalSync knows what the live Worker should allow."
    if not edge.get("reachable", False):
        return "Check the edge Worker deployment so Alexa route status can be verified and updated live."
    if not edge_alexa.get("enabled", False):
        return "Apply the saved Alexa settings so the live edge Worker enables the voice route."
    if not edge_alexa.get("skill_ids_configured", False) or not desired_skill_ids:
        return "Add the real Alexa skill ID to the live allowlist before turning voice access on."
    if not channel_tokens.get("alexa", False):
        return "Bootstrap the Alexa channel token on the origin so voice-origin calls can be authenticated."
    return "Alexa is ready for real signed Amazon skill verification."


def _describe_alexa_finish_line_action(
    *,
    readiness: dict[str, object],
    account_linking_settings: dict[str, object],
    cloudflare_credentials: dict[str, object],
    legacy_apple_recovery_hints: dict[str, object],
) -> str:
    account_linking_ready = bool(account_linking_settings.get("configured"))
    cloudflare_ready = bool(cloudflare_credentials.get("api_token_saved"))
    recovery_mode = _alexa_recovery_mode(
        readiness=readiness,
        legacy_apple_recovery_hints=legacy_apple_recovery_hints,
    )
    if recovery_mode:
        if not account_linking_ready and not cloudflare_ready:
            return "open Apple setup, confirm the loaded recovered calendar, save a fresh app-specific password, then save a household link code and Cloudflare Worker access from the Alexa setup page."
        if not account_linking_ready:
            return "open Apple setup, confirm the loaded recovered calendar, save a fresh app-specific password, then save a household link code from the Alexa setup page."
        if not cloudflare_ready:
            return "open Apple setup, confirm the loaded recovered calendar, save a fresh app-specific password, then save Cloudflare Worker access from the Alexa setup page."
        return "open Apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password so Alexa has a real schedule behind the shared brain."
    if account_linking_ready:
        return "finish edge enablement and skill-ID allowlisting from the Alexa setup page."
    return "save a household link code, then finish edge enablement and skill-ID allowlisting from the Alexa setup page."


def _alexa_recovery_mode(
    *,
    readiness: dict[str, object],
    legacy_apple_recovery_hints: dict[str, object],
) -> bool:
    origin = readiness.get("origin", {}) if isinstance(readiness, dict) else {}
    return (
        not bool(origin.get("any_calendar_ready"))
        and str(legacy_apple_recovery_hints.get("source") or "missing") != "missing"
    )


def _describe_alexa_simulator_state(
    *,
    readiness: dict[str, object],
    calendar_name_options: list[dict[str, str]],
    recovery_mode: bool = False,
) -> dict[str, object]:
    origin = readiness.get("origin", {})
    edge = readiness.get("edge", {})
    any_calendar_ready = bool(origin.get("any_calendar_ready"))
    edge_reachable = bool(edge.get("reachable", False))
    edge_enabled = bool(edge.get("alexa", {}).get("enabled", False))
    if not any_calendar_ready:
        headline = (
            "Apple reconnect still blocks meaningful scheduling tests"
            if recovery_mode
            else "Calendar setup still blocks meaningful scheduling tests"
        )
        detail = (
            "Recovered Apple hints are already loaded into Apple setup. You can still preview LaunchRequest "
            "and the general voice shape, but scheduling intents become useful after you save a fresh "
            "app-specific password on the recovered Apple calendar."
            if recovery_mode
            else "No writable calendar is connected yet. You can still preview LaunchRequest "
            "and the general voice shape, but scheduling intents become useful after "
            "Apple, Google, or Microsoft setup is connected."
        )
        useful_now = "LaunchRequest and copy checks"
    elif not edge_enabled:
        headline = "Scheduling simulation is ready before full device turn-on"
        detail = (
            "A writable calendar is ready, so the simulator can exercise scheduling "
            "intents even though the real Alexa route is still disabled."
        )
        useful_now = "LaunchRequest plus scheduling intents"
    elif not edge_reachable:
        headline = "Simulator guidance is limited while edge status is unavailable"
        detail = (
            "Calendar-backed scheduling is configured, but CalSync cannot currently "
            "confirm the live edge state."
        )
        useful_now = "Most simulator requests"
    else:
        headline = "Simulator is ready for end-to-end voice rehearsal"
        detail = (
            "The connected calendar path and live edge state are both visible, so "
            "this page can preview the real voice behavior before signed Amazon traffic."
        )
        useful_now = "LaunchRequest plus scheduling intents"
    return {
        "calendar_ready": any_calendar_ready,
        "edge_reachable": edge_reachable,
        "edge_enabled": edge_enabled,
        "recovery_mode": recovery_mode,
        "headline": headline,
        "detail": detail,
        "useful_now": useful_now,
        "target_option_count": len(calendar_name_options),
    }


def _calendar_name_options(
    service: AppointmentService,
) -> list[dict[str, str]]:
    return service.calendar_name_targets
