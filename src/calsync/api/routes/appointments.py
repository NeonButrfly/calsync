from fastapi import APIRouter, HTTPException, Header, status

from calsync.schemas.appointments import (
    AppointmentDetailResponse,
    ListAppointmentsResponse,
    AppointmentResponse,
    AvailabilityResponse,
    CreateAppointmentRequest,
    UpdateAppointmentRequest,
)
from calsync.services.appointments import AppointmentService
from calsync.services.apple_caldav import AppleCalDAVError
from calsync.services.google_calendar import GoogleCalendarError
from calsync.services.operator_settings import OperatorSettingsService
from calsync.services.readiness import ReadinessService

router = APIRouter(prefix="/api/appointments", tags=["appointments"])
availability_router = APIRouter(prefix="/api", tags=["availability"])


def _recovery_mode() -> bool:
    readiness = ReadinessService().build()
    origin = readiness.get("origin", {}) if isinstance(readiness, dict) else {}
    any_calendar_ready = bool(origin.get("any_calendar_ready"))
    legacy_hints = OperatorSettingsService().describe_legacy_apple_recovery_hints()
    return (
        not any_calendar_ready
        and str(legacy_hints.get("source") or "missing") != "missing"
    )


def _recovery_guidance_detail() -> str:
    return (
        "Apple reconnect still needs one more step. Open Apple setup in CalSync, "
        "confirm the recovered calendar, and save a fresh app-specific password "
        "before I can help with the household calendar."
    )


def _normalize_recovery_error_detail(detail: str) -> str:
    normalized = detail.strip()
    if normalized not in {
        "Primary Apple/iCloud calendar is not configured.",
        "Apple/iCloud calendar settings are incomplete.",
        "Appointment calendar connection not found.",
    }:
        return normalized

    if _recovery_mode():
        return _recovery_guidance_detail()
    return normalized


@router.get("", response_model=ListAppointmentsResponse)
def list_appointments(
    date_from: str,
    date_to: str,
    include_cancelled: bool = False,
) -> ListAppointmentsResponse:
    if _recovery_mode():
        raise HTTPException(status_code=400, detail=_recovery_guidance_detail())
    try:
        return AppointmentService().list_range(
            date_from=date_from,
            date_to=date_to,
            include_cancelled=include_cancelled,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=_normalize_recovery_error_detail(str(exc)),
        ) from exc


@availability_router.get("/availability", response_model=AvailabilityResponse)
def list_availability(
    date_from: str,
    date_to: str,
    duration_minutes: int,
    max_results: int = 5,
) -> AvailabilityResponse:
    if _recovery_mode():
        raise HTTPException(status_code=400, detail=_recovery_guidance_detail())
    try:
        return AppointmentService().find_availability(
            date_from=date_from,
            date_to=date_to,
            duration_minutes=duration_minutes,
            max_results=max_results,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=_normalize_recovery_error_detail(str(exc)),
        ) from exc


@router.get("/{appointment_id}", response_model=AppointmentDetailResponse)
def get_appointment(appointment_id: str) -> AppointmentDetailResponse:
    if _recovery_mode():
        raise HTTPException(status_code=400, detail=_recovery_guidance_detail())
    try:
        return AppointmentService().get_detail(appointment_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=_normalize_recovery_error_detail(str(exc)),
        ) from exc


@router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(
    payload: CreateAppointmentRequest,
    x_calsync_channel: str | None = Header(default=None),
) -> AppointmentResponse:
    try:
        actor = f"worker:{x_calsync_channel}" if x_calsync_channel else "api"
        return AppointmentService().create(payload, actor=actor)
    except (AppleCalDAVError, GoogleCalendarError) as exc:
        raise HTTPException(
            status_code=502,
            detail=_normalize_recovery_error_detail(str(exc)),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=_normalize_recovery_error_detail(str(exc)),
        ) from exc


@router.patch("/{appointment_id}", response_model=AppointmentResponse)
def update_appointment(
    appointment_id: str,
    payload: UpdateAppointmentRequest,
    x_calsync_channel: str | None = Header(default=None),
) -> AppointmentResponse:
    try:
        actor = f"worker:{x_calsync_channel}" if x_calsync_channel else "api"
        return AppointmentService().update(appointment_id, payload, actor=actor)
    except (AppleCalDAVError, GoogleCalendarError) as exc:
        raise HTTPException(
            status_code=502,
            detail=_normalize_recovery_error_detail(str(exc)),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=_normalize_recovery_error_detail(str(exc)),
        ) from exc


@router.post("/{appointment_id}/cancel", response_model=AppointmentResponse)
def cancel_appointment(
    appointment_id: str,
    x_calsync_channel: str | None = Header(default=None),
) -> AppointmentResponse:
    try:
        actor = f"worker:{x_calsync_channel}" if x_calsync_channel else "api"
        return AppointmentService().cancel(appointment_id, actor=actor)
    except (AppleCalDAVError, GoogleCalendarError) as exc:
        raise HTTPException(
            status_code=502,
            detail=_normalize_recovery_error_detail(str(exc)),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=_normalize_recovery_error_detail(str(exc)),
        ) from exc
