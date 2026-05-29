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

router = APIRouter(prefix="/api/appointments", tags=["appointments"])
availability_router = APIRouter(prefix="/api", tags=["availability"])


@router.get("", response_model=ListAppointmentsResponse)
def list_appointments(
    date_from: str,
    date_to: str,
    include_cancelled: bool = False,
) -> ListAppointmentsResponse:
    try:
        return AppointmentService().list_range(
            date_from=date_from,
            date_to=date_to,
            include_cancelled=include_cancelled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@availability_router.get("/availability", response_model=AvailabilityResponse)
def list_availability(
    date_from: str,
    date_to: str,
    duration_minutes: int,
    max_results: int = 5,
) -> AvailabilityResponse:
    try:
        return AppointmentService().find_availability(
            date_from=date_from,
            date_to=date_to,
            duration_minutes=duration_minutes,
            max_results=max_results,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{appointment_id}", response_model=AppointmentDetailResponse)
def get_appointment(appointment_id: str) -> AppointmentDetailResponse:
    try:
        return AppointmentService().get_detail(appointment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(
    payload: CreateAppointmentRequest,
    x_calsync_channel: str | None = Header(default=None),
) -> AppointmentResponse:
    try:
        actor = f"worker:{x_calsync_channel}" if x_calsync_channel else "api"
        return AppointmentService().create(payload, actor=actor)
    except AppleCalDAVError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{appointment_id}", response_model=AppointmentResponse)
def update_appointment(
    appointment_id: str,
    payload: UpdateAppointmentRequest,
    x_calsync_channel: str | None = Header(default=None),
) -> AppointmentResponse:
    try:
        actor = f"worker:{x_calsync_channel}" if x_calsync_channel else "api"
        return AppointmentService().update(appointment_id, payload, actor=actor)
    except AppleCalDAVError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{appointment_id}/cancel", response_model=AppointmentResponse)
def cancel_appointment(
    appointment_id: str,
    x_calsync_channel: str | None = Header(default=None),
) -> AppointmentResponse:
    try:
        actor = f"worker:{x_calsync_channel}" if x_calsync_channel else "api"
        return AppointmentService().cancel(appointment_id, actor=actor)
    except AppleCalDAVError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
