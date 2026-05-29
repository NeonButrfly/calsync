from pydantic import BaseModel, Field


class CreateAppointmentRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    date: str
    start_time: str
    end_time: str
    timezone: str
    all_day: bool = False
    location: str | None = None
    notes: str | None = None
    attendees_text: str | None = None
    target_calendar_url: str | None = None
    target_calendar_name: str | None = None


class UpdateAppointmentRequest(BaseModel):
    title: str | None = None
    date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    timezone: str | None = None
    all_day: bool | None = None
    location: str | None = None
    notes: str | None = None
    attendees_text: str | None = None
    target_calendar_url: str | None = None
    target_calendar_name: str | None = None


class AppointmentResponse(BaseModel):
    appointment_id: str
    status: str
    provider_event_id: str
    message: str


class AppointmentListItem(BaseModel):
    appointment_id: str
    title: str
    status: str
    date: str
    start_time: str
    end_time: str
    timezone: str
    all_day: bool
    location: str | None = None
    notes: str | None = None
    attendees_text: str | None = None
    provider_event_id: str | None = None


class AppointmentAuditItem(BaseModel):
    action: str
    actor: str
    created_at: str
    payload_json: dict[str, object] | None = None


class AppointmentDetailResponse(AppointmentListItem):
    account_label: str
    calendar_name: str
    calendar_url: str | None = None
    provider_type: str
    provider_href: str | None = None
    provider_etag: str | None = None
    created_at: str
    updated_at: str
    audit_entries: list[AppointmentAuditItem]


class ListAppointmentsResponse(BaseModel):
    items: list[AppointmentListItem]
