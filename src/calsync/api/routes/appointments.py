from fastapi import APIRouter, HTTPException, Header, status

from calsync.schemas import (
    ListAppointmentsResponse,
    AppointmentResponse,
    CreateAppointmentRequest,
    UpdateAppointmentRequest,
)
from calsync.services.appointments import AppointmentService
from calsync.services.apple_caldav import AppleCalDAVError

router = APIRouter(prefix="/api/appointments", tags=["appointments"])


@router.get("", response_model=ListAppointmentsResponse)
def list_appointments(
    date_from: str,
    date_to: str,
) -> ListAppointmentsResponse:
    try:
        return AppointmentService().list_range(date_from=date_from, date_to=date_to)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(
    payload: CreateAppointmentRequest,
    x_calsync_channel: str | None = Header(default=None),
) -> AppointmentResponse:
    try:
        actor = f"worker:{x_calsync_channel}" if x_calsync_channel else "api"
        return AppointmentService().create_with_actor(payload, actor=actor)
    except AppleCalDAVError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{appointment_id}", response_model=AppointmentResponse)
def update_appointment(
    appointment_id: str,
    payload: UpdateAppointmentRequest,
) -> AppointmentResponse:
    try:
        return AppointmentService().update(appointment_id, payload)
    except AppleCalDAVError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{appointment_id}/cancel", response_model=AppointmentResponse)
def cancel_appointment(appointment_id: str) -> AppointmentResponse:
    try:
        return AppointmentService().cancel(appointment_id)
    except AppleCalDAVError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
