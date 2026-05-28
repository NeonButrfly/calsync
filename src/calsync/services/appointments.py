from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from calsync.config import Settings, get_settings
from calsync.db import create_session_factory
from calsync.models import (
    AppleCalendarConnection,
    Appointment,
    AppointmentExternalLink,
    AuditEntry,
)
from calsync.schemas import (
    AppointmentResponse,
    CreateAppointmentRequest,
    UpdateAppointmentRequest,
)
from calsync.services.apple_caldav import AppleCalDAVClient, AppleCalDAVConfig


class AppointmentService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.session_factory = session_factory or create_session_factory(self.settings)

    def create(self, payload: CreateAppointmentRequest) -> AppointmentResponse:
        starts_at, ends_at = self._parse_range(
            payload.date,
            payload.start_time,
            payload.end_time,
            payload.timezone,
        )
        with self.session_factory() as session:
            connection = self._ensure_primary_connection(session)
            provider_record = self._build_apple_client().create_event(
                title=payload.title,
                starts_at=starts_at,
                ends_at=ends_at,
                all_day=payload.all_day,
                location=payload.location,
                notes=payload.notes,
            )
            appointment = Appointment(
                connection_id=connection.id,
                title=payload.title,
                starts_at=starts_at,
                ends_at=ends_at,
                timezone_name=payload.timezone,
                all_day=payload.all_day,
                location=payload.location,
                notes=payload.notes,
                attendees_text=payload.attendees_text,
                status="active",
                source="api",
            )
            session.add(appointment)
            session.flush()
            session.add(
                AppointmentExternalLink(
                    appointment_id=appointment.id,
                    provider_type="icloud_caldav",
                    provider_event_id=provider_record.provider_event_id,
                    provider_href=provider_record.href,
                    provider_etag=provider_record.etag,
                )
            )
            session.add(
                AuditEntry(
                    appointment_id=appointment.id,
                    action="create_appointment",
                    actor="api",
                    payload_json=payload.model_dump(),
                )
            )
            session.commit()
            return AppointmentResponse(
                appointment_id=appointment.id,
                status=appointment.status,
                provider_event_id=provider_record.provider_event_id,
                message="Appointment created.",
            )

    def update(
        self,
        appointment_id: str,
        payload: UpdateAppointmentRequest,
    ) -> AppointmentResponse:
        with self.session_factory() as session:
            appointment = self._get_appointment(session, appointment_id)
            external_link = self._get_external_link(session, appointment_id)
            next_date = payload.date or appointment.starts_at.date().isoformat()
            next_timezone = payload.timezone or appointment.timezone_name
            next_start = payload.start_time or appointment.starts_at.astimezone(
                ZoneInfo(next_timezone)
            ).strftime("%H:%M")
            next_end = payload.end_time or appointment.ends_at.astimezone(
                ZoneInfo(next_timezone)
            ).strftime("%H:%M")
            starts_at, ends_at = self._parse_range(
                next_date,
                next_start,
                next_end,
                next_timezone,
            )
            title = payload.title or appointment.title
            location = payload.location if payload.location is not None else appointment.location
            notes = payload.notes if payload.notes is not None else appointment.notes
            attendees_text = (
                payload.attendees_text
                if payload.attendees_text is not None
                else appointment.attendees_text
            )
            all_day = payload.all_day if payload.all_day is not None else appointment.all_day

            provider_record = self._build_apple_client().update_event(
                provider_event_id=external_link.provider_event_id,
                title=title,
                starts_at=starts_at,
                ends_at=ends_at,
                all_day=all_day,
                location=location,
                notes=notes,
                href=external_link.provider_href,
                etag=external_link.provider_etag,
            )
            appointment.title = title
            appointment.starts_at = starts_at
            appointment.ends_at = ends_at
            appointment.timezone_name = next_timezone
            appointment.all_day = all_day
            appointment.location = location
            appointment.notes = notes
            appointment.attendees_text = attendees_text
            external_link.provider_href = provider_record.href
            external_link.provider_etag = provider_record.etag
            session.add(
                AuditEntry(
                    appointment_id=appointment.id,
                    action="update_appointment",
                    actor="api",
                    payload_json=payload.model_dump(exclude_none=True),
                )
            )
            session.commit()
            return AppointmentResponse(
                appointment_id=appointment.id,
                status=appointment.status,
                provider_event_id=external_link.provider_event_id,
                message="Appointment updated.",
            )

    def cancel(self, appointment_id: str) -> AppointmentResponse:
        with self.session_factory() as session:
            appointment = self._get_appointment(session, appointment_id)
            external_link = self._get_external_link(session, appointment_id)
            self._build_apple_client().cancel_event(
                provider_event_id=external_link.provider_event_id,
                href=external_link.provider_href,
                etag=external_link.provider_etag,
            )
            appointment.status = "cancelled"
            session.add(
                AuditEntry(
                    appointment_id=appointment.id,
                    action="cancel_appointment",
                    actor="api",
                    payload_json={"appointment_id": appointment.id},
                )
            )
            session.commit()
            return AppointmentResponse(
                appointment_id=appointment.id,
                status=appointment.status,
                provider_event_id=external_link.provider_event_id,
                message="Appointment cancelled.",
            )

    def _build_apple_client(self) -> AppleCalDAVClient:
        if not (
            self.settings.apple_username
            and self.settings.apple_app_specific_password
            and self.settings.apple_primary_calendar_url
        ):
            raise ValueError("Apple/iCloud calendar settings are incomplete.")
        return AppleCalDAVClient(
            AppleCalDAVConfig(
                account_label=self.settings.apple_account_label,
                apple_username=self.settings.apple_username,
                app_specific_password=self.settings.apple_app_specific_password,
                primary_calendar_url=self.settings.apple_primary_calendar_url,
                primary_calendar_name=self.settings.apple_primary_calendar_name,
            )
        )

    def _ensure_primary_connection(self, session: Session) -> AppleCalendarConnection:
        existing = session.scalar(
            select(AppleCalendarConnection).where(
                AppleCalendarConnection.is_primary.is_(True)
            )
        )
        if existing is not None:
            return existing
        if not self.settings.apple_primary_calendar_url or not self.settings.apple_username:
            raise ValueError("Primary Apple/iCloud calendar is not configured.")
        connection = AppleCalendarConnection(
            account_label=self.settings.apple_account_label,
            apple_username=self.settings.apple_username,
            primary_calendar_url=self.settings.apple_primary_calendar_url,
            primary_calendar_name=self.settings.apple_primary_calendar_name,
            is_primary=True,
        )
        session.add(connection)
        session.flush()
        return connection

    def _get_appointment(self, session: Session, appointment_id: str) -> Appointment:
        appointment = session.get(Appointment, appointment_id)
        if appointment is None:
            raise ValueError("Appointment not found.")
        return appointment

    def _get_external_link(
        self,
        session: Session,
        appointment_id: str,
    ) -> AppointmentExternalLink:
        external_link = session.scalar(
            select(AppointmentExternalLink).where(
                AppointmentExternalLink.appointment_id == appointment_id
            )
        )
        if external_link is None:
            raise ValueError("Appointment external link not found.")
        return external_link

    def _parse_range(
        self,
        date_value: str,
        start_time: str,
        end_time: str,
        timezone_name: str,
    ) -> tuple[datetime, datetime]:
        timezone = ZoneInfo(timezone_name)
        starts_at = datetime.fromisoformat(f"{date_value}T{start_time}").replace(
            tzinfo=timezone
        )
        ends_at = datetime.fromisoformat(f"{date_value}T{end_time}").replace(
            tzinfo=timezone
        )
        if ends_at <= starts_at:
            raise ValueError("Appointment end time must be after the start time.")
        return starts_at, ends_at
