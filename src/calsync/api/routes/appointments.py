from fastapi import APIRouter, HTTPException, status

from calsync.schemas import (
    AppointmentResponse,
    CreateAppointmentRequest,
    UpdateAppointmentRequest,
)
from calsync.services.appointments import AppointmentService

router = APIRouter(prefix="/api/appointments", tags=["appointments"])


@router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(payload: CreateAppointmentRequest) -> AppointmentResponse:
    try:
        return AppointmentService().create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{appointment_id}", response_model=AppointmentResponse)
def update_appointment(
    appointment_id: str,
    payload: UpdateAppointmentRequest,
) -> AppointmentResponse:
    try:
        return AppointmentService().update(appointment_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{appointment_id}/cancel", response_model=AppointmentResponse)
def cancel_appointment(appointment_id: str) -> AppointmentResponse:
    try:
        return AppointmentService().cancel(appointment_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
