from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
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
from calsync.schemas.appointments import (
    AppointmentAuditItem,
    AppointmentDetailResponse,
    AppointmentListItem,
    AppointmentResponse,
    AvailabilityResponse,
    AvailabilitySlot,
    CreateAppointmentRequest,
    ListAppointmentsResponse,
    UpdateAppointmentRequest,
)
from calsync.services.apple_caldav import (
    AppleCalDAVClient,
    AppleCalDAVConfig,
    AppleCalDAVError,
    AppleListedEvent,
)
from calsync.services.apple_runtime_config import AppleRuntimeConfigService
from calsync.services.google_calendar import (
    GoogleCalendarClient,
    GoogleCalendarError,
    GoogleListedEvent,
    GoogleOAuthConfig,
)
from calsync.services.google_runtime_config import GoogleRuntimeConfigService


class AppointmentService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.session_factory = session_factory
        self.apple_runtime_config = AppleRuntimeConfigService(settings=self.settings)
        self.google_runtime_config = GoogleRuntimeConfigService(settings=self.settings)

    def create(
        self,
        payload: CreateAppointmentRequest,
        actor: str = "api",
    ) -> AppointmentResponse:
        starts_at, ends_at = self._parse_range(
            payload.date,
            payload.start_time,
            payload.end_time,
            payload.timezone,
        )
        with self._get_session_factory()() as session:
            target_calendar_value = self._resolve_target_calendar_value(
                payload.target_calendar_url,
                payload.target_calendar_name,
            )
            connection = self._ensure_connection(
                session,
                target_calendar_value=target_calendar_value,
            )
            provider_record = self._create_provider_event(
                connection,
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
                    provider_type=connection.provider_type,
                    provider_event_id=provider_record.provider_event_id,
                    provider_href=provider_record.href,
                    provider_etag=provider_record.etag,
                )
            )
            session.add(
                AuditEntry(
                    appointment_id=appointment.id,
                    action="create_appointment",
                    actor=actor,
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

    def list_range(
        self,
        *,
        date_from: str,
        date_to: str,
        include_cancelled: bool = False,
    ) -> ListAppointmentsResponse:
        start = datetime.combine(date.fromisoformat(date_from), time.min, tzinfo=UTC)
        end = datetime.combine(date.fromisoformat(date_to), time.max, tzinfo=UTC)
        if end < start:
            raise ValueError("date_to must be on or after date_from.")

        with self._get_session_factory()() as session:
            try:
                for calendar in self.available_calendars:
                    self._sync_calendar_range(
                        session,
                        starts_at=start,
                        ends_at=end,
                        calendar=calendar,
                    )
                session.commit()
            except (AppleCalDAVError, GoogleCalendarError, AttributeError):
                session.rollback()
            query = (
                select(Appointment, AppointmentExternalLink)
                .join(
                    AppointmentExternalLink,
                    AppointmentExternalLink.appointment_id == Appointment.id,
                    isouter=True,
                )
                .where(Appointment.starts_at >= start)
                .where(Appointment.starts_at <= end)
                .order_by(Appointment.starts_at.asc())
            )
            if not include_cancelled:
                query = query.where(Appointment.status != "cancelled")
            rows = session.execute(query).all()

        items = [
            self._to_list_item(appointment, external_link)
            for appointment, external_link in rows
        ]
        return ListAppointmentsResponse(items=items)

    def update(
        self,
        appointment_id: str,
        payload: UpdateAppointmentRequest,
        actor: str = "api",
    ) -> AppointmentResponse:
        with self._get_session_factory()() as session:
            appointment = self._get_appointment(session, appointment_id)
            external_link = self._get_external_link(session, appointment_id)
            connection = session.get(AppleCalendarConnection, appointment.connection_id)
            if connection is None:
                raise ValueError("Appointment calendar connection not found.")
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
            if payload.target_calendar_url or payload.target_calendar_name:
                target_calendar_value = self._resolve_target_calendar_value(
                    payload.target_calendar_url,
                    payload.target_calendar_name,
                )
            else:
                target_calendar_value = self._connection_target_value(connection)

            if target_calendar_value != self._connection_target_value(connection):
                next_connection = self._ensure_connection(
                    session,
                    target_calendar_value=target_calendar_value,
                )
                provider_record = self._create_provider_event(
                    next_connection,
                    title=title,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    all_day=all_day,
                    location=location,
                    notes=notes,
                )
                self._cancel_provider_event(
                    connection,
                    provider_event_id=external_link.provider_event_id,
                    href=external_link.provider_href,
                    etag=external_link.provider_etag,
                )
                appointment.connection_id = next_connection.id
                external_link.provider_event_id = provider_record.provider_event_id
                external_link.provider_type = next_connection.provider_type
            else:
                provider_record = self._update_provider_event(
                    connection,
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
                    actor=actor,
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

    def find_availability(
        self,
        *,
        date_from: str,
        date_to: str,
        duration_minutes: int,
        max_results: int = 5,
    ) -> AvailabilityResponse:
        if duration_minutes <= 0:
            raise ValueError("duration_minutes must be greater than zero.")
        if max_results <= 0:
            raise ValueError("max_results must be greater than zero.")

        start_day = date.fromisoformat(date_from)
        end_day = date.fromisoformat(date_to)
        if end_day < start_day:
            raise ValueError("date_to must be on or after date_from.")

        sync_start = datetime.combine(start_day, time.min, tzinfo=UTC)
        sync_end = datetime.combine(end_day, time.max, tzinfo=UTC)
        timezone = ZoneInfo(self.settings.default_timezone)
        workday_start = time(hour=8, minute=0)
        workday_end = time(hour=18, minute=0)
        duration = timedelta(minutes=duration_minutes)

        with self._get_session_factory()() as session:
            try:
                for calendar in self.available_calendars:
                    self._sync_calendar_range(
                        session,
                        starts_at=sync_start,
                        ends_at=sync_end,
                        calendar=calendar,
                    )
                session.commit()
            except (AppleCalDAVError, GoogleCalendarError, AttributeError):
                session.rollback()

            appointments = session.scalars(
                select(Appointment)
                .where(Appointment.status != "cancelled")
                .where(Appointment.ends_at > sync_start)
                .where(Appointment.starts_at < sync_end)
                .order_by(Appointment.starts_at.asc())
            ).all()

        items: list[AvailabilitySlot] = []
        current_day = start_day
        while current_day <= end_day and len(items) < max_results:
            day_start = datetime.combine(current_day, workday_start, tzinfo=timezone)
            day_end = datetime.combine(current_day, workday_end, tzinfo=timezone)
            busy_ranges = self._merge_busy_ranges(
                appointments,
                day_start=day_start,
                day_end=day_end,
                timezone=timezone,
            )
            cursor = day_start
            for busy_start, busy_end in busy_ranges:
                while cursor + duration <= busy_start and len(items) < max_results:
                    slot_end = cursor + duration
                    items.append(
                        AvailabilitySlot(
                            date=current_day.isoformat(),
                            start_time=cursor.strftime("%H:%M"),
                            end_time=slot_end.strftime("%H:%M"),
                            timezone=timezone.key,
                        )
                    )
                    cursor = slot_end
                if cursor < busy_end:
                    cursor = busy_end
            while cursor + duration <= day_end and len(items) < max_results:
                slot_end = cursor + duration
                items.append(
                    AvailabilitySlot(
                        date=current_day.isoformat(),
                        start_time=cursor.strftime("%H:%M"),
                        end_time=slot_end.strftime("%H:%M"),
                        timezone=timezone.key,
                    )
                )
                cursor = slot_end
            current_day += timedelta(days=1)

        return AvailabilityResponse(items=items)

    def cancel(self, appointment_id: str, actor: str = "api") -> AppointmentResponse:
        with self._get_session_factory()() as session:
            appointment = self._get_appointment(session, appointment_id)
            external_link = self._get_external_link(session, appointment_id)
            connection = session.get(AppleCalendarConnection, appointment.connection_id)
            if connection is None:
                raise ValueError("Appointment calendar connection not found.")
            self._cancel_provider_event(
                connection,
                provider_event_id=external_link.provider_event_id,
                href=external_link.provider_href,
                etag=external_link.provider_etag,
            )
            appointment.status = "cancelled"
            session.add(
                AuditEntry(
                    appointment_id=appointment.id,
                    action="cancel_appointment",
                    actor=actor,
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

    def get(self, appointment_id: str) -> AppointmentListItem:
        with self._get_session_factory()() as session:
            appointment = self._get_appointment(session, appointment_id)
            external_link = self._get_external_link(session, appointment_id)
            return self._to_list_item(appointment, external_link)

    def get_detail(self, appointment_id: str) -> AppointmentDetailResponse:
        with self._get_session_factory()() as session:
            appointment = self._get_appointment(session, appointment_id)
            external_link = self._get_external_link(session, appointment_id)
            connection = session.get(AppleCalendarConnection, appointment.connection_id)
            if connection is None:
                raise ValueError("Appointment calendar connection not found.")
            audits = session.execute(
                select(AuditEntry)
                .where(AuditEntry.appointment_id == appointment_id)
                .order_by(AuditEntry.created_at.desc())
            ).scalars().all()
            timezone = ZoneInfo(appointment.timezone_name)
            starts_at = appointment.starts_at.astimezone(timezone)
            ends_at = appointment.ends_at.astimezone(timezone)
            return AppointmentDetailResponse(
                appointment_id=appointment.id,
                title=appointment.title,
                status=appointment.status,
                date=starts_at.date().isoformat(),
                start_time=starts_at.strftime("%H:%M"),
                end_time=ends_at.strftime("%H:%M"),
                timezone=appointment.timezone_name,
                all_day=appointment.all_day,
                location=appointment.location,
                notes=appointment.notes,
                attendees_text=appointment.attendees_text,
                provider_event_id=external_link.provider_event_id,
                account_label=connection.account_label,
                calendar_name=connection.primary_calendar_name,
                calendar_url=self._connection_target_value(connection),
                provider_type=external_link.provider_type,
                provider_href=external_link.provider_href,
                provider_etag=external_link.provider_etag,
                created_at=appointment.created_at.astimezone(timezone).isoformat(),
                updated_at=appointment.updated_at.astimezone(timezone).isoformat(),
                audit_entries=[
                    AppointmentAuditItem(
                        action=audit.action,
                        actor=audit.actor,
                        created_at=audit.created_at.astimezone(timezone).isoformat(),
                        payload_json=audit.payload_json,
                    )
                    for audit in audits
                ],
            )

    def _build_apple_client(
        self,
        calendar_url: str | None = None,
        calendar_name: str | None = None,
    ) -> AppleCalDAVClient:
        config = self.apple_runtime_config.resolve(
            calendar_url=calendar_url,
            calendar_name=calendar_name,
        )
        if not config["ready"]:
            raise ValueError("Apple/iCloud calendar settings are incomplete.")
        return AppleCalDAVClient(
            AppleCalDAVConfig(
                account_label=str(config["account_label"]),
                apple_username=str(config["username"]),
                app_specific_password=str(config["app_specific_password"]),
                primary_calendar_url=str(config["primary_calendar_url"]),
                primary_calendar_name=str(config["primary_calendar_name"]),
            )
        )

    def _build_google_client(
        self,
        calendar_id: str | None = None,
        calendar_name: str | None = None,
    ) -> GoogleCalendarClient:
        config = self.google_runtime_config.resolve(
            calendar_id=calendar_id,
            calendar_name=calendar_name,
        )
        if not config["ready"]:
            raise ValueError("Google calendar settings are incomplete.")
        return GoogleCalendarClient(
            GoogleOAuthConfig(
                account_label=str(config["account_label"]),
                account_email=str(config["account_email"]),
                client_id=str(config["client_id"]),
                client_secret=str(config["client_secret"]),
                refresh_token=str(config["refresh_token"]),
                primary_calendar_id=str(config["primary_calendar_id"]),
                primary_calendar_name=str(config["primary_calendar_name"]),
            )
        )

    def _ensure_connection(
        self,
        session: Session,
        *,
        target_calendar_value: str | None = None,
    ) -> AppleCalendarConnection:
        provider_type, external_id = self._parse_target_calendar_value(
            target_calendar_value
        )
        if provider_type == "google_calendar":
            config = self.google_runtime_config.resolve(calendar_id=external_id)
            if not config["ready"]:
                raise ValueError("Google calendar settings are incomplete.")
            existing = session.scalar(
                select(AppleCalendarConnection).where(
                    AppleCalendarConnection.provider_type == "google_calendar",
                    AppleCalendarConnection.primary_calendar_url
                    == str(config["primary_calendar_id"]),
                )
            )
            if existing is not None:
                existing.account_label = str(config["account_label"])
                existing.apple_username = str(config["account_email"])
                existing.primary_calendar_name = str(config["primary_calendar_name"])
                existing.is_primary = bool(
                    self.google_runtime_config.resolve()["primary_calendar_id"]
                    == existing.primary_calendar_url
                )
                return existing
            connection = AppleCalendarConnection(
                provider_type="google_calendar",
                account_label=str(config["account_label"]),
                apple_username=str(config["account_email"]),
                primary_calendar_url=str(config["primary_calendar_id"]),
                primary_calendar_name=str(config["primary_calendar_name"]),
                is_primary=bool(
                    self.google_runtime_config.resolve()["primary_calendar_id"]
                    == str(config["primary_calendar_id"])
                ),
            )
            session.add(connection)
            session.flush()
            return connection

        config = self.apple_runtime_config.resolve(calendar_url=external_id)
        if not config["ready"]:
            raise ValueError("Primary Apple/iCloud calendar is not configured.")
        existing = session.scalar(
            select(AppleCalendarConnection).where(
                AppleCalendarConnection.provider_type == "icloud_caldav",
                AppleCalendarConnection.primary_calendar_url
                == str(config["primary_calendar_url"])
            )
        )
        if existing is not None:
            existing.provider_type = "icloud_caldav"
            existing.account_label = str(config["account_label"])
            existing.apple_username = str(config["username"])
            existing.primary_calendar_name = str(config["primary_calendar_name"])
            existing.is_primary = bool(
                self.apple_runtime_config.resolve()["primary_calendar_url"]
                == existing.primary_calendar_url
            )
            return existing
        connection = AppleCalendarConnection(
            provider_type="icloud_caldav",
            account_label=str(config["account_label"]),
            apple_username=str(config["username"]),
            primary_calendar_url=str(config["primary_calendar_url"]),
            primary_calendar_name=str(config["primary_calendar_name"]),
            is_primary=bool(
                self.apple_runtime_config.resolve()["primary_calendar_url"]
                == str(config["primary_calendar_url"])
            ),
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

    def _sync_calendar_range(
        self,
        session: Session,
        *,
        starts_at: datetime,
        ends_at: datetime,
        calendar: dict[str, object],
    ) -> None:
        target_value = str(calendar["calendar_url"])
        provider_type, external_id = self._parse_target_calendar_value(target_value)
        connection = self._ensure_connection(
            session,
            target_calendar_value=target_value,
        )
        provider_events = self._list_provider_events(
            provider_type=provider_type,
            external_id=external_id,
            starts_at=starts_at,
            ends_at=ends_at + timedelta(days=1),
        )
        seen_provider_event_ids: set[str] = set()
        for provider_event in provider_events:
            provider_event_id = str(getattr(provider_event, "provider_event_id"))
            if provider_event_id in seen_provider_event_ids:
                continue
            seen_provider_event_ids.add(provider_event_id)
            self._upsert_synced_provider_event(
                session,
                connection=connection,
                provider_event=provider_event,
            )

    def _upsert_synced_provider_event(
        self,
        session: Session,
        *,
        connection: AppleCalendarConnection,
        provider_event: AppleListedEvent | GoogleListedEvent | object,
    ) -> None:
        provider_event_id = str(getattr(provider_event, "provider_event_id"))
        external_links = session.scalars(
            select(AppointmentExternalLink)
            .join(
                Appointment,
                Appointment.id == AppointmentExternalLink.appointment_id,
            )
            .where(
                AppointmentExternalLink.provider_type == connection.provider_type,
                AppointmentExternalLink.provider_event_id == provider_event_id,
                Appointment.connection_id == connection.id,
            )
        ).all()
        starts_at = self._coerce_provider_datetime(getattr(provider_event, "starts_at"))
        ends_at = self._coerce_provider_datetime(getattr(provider_event, "ends_at"))
        title = str(getattr(provider_event, "title"))
        status = "cancelled" if str(getattr(provider_event, "status", "confirmed")).lower() == "cancelled" else "active"
        all_day = bool(getattr(provider_event, "all_day", False))
        location = getattr(provider_event, "location", None)
        notes = getattr(provider_event, "notes", None)
        attendees_text = getattr(provider_event, "attendees_text", None)
        href = str(getattr(provider_event, "href"))
        etag = getattr(provider_event, "etag", None)

        external_link = None
        if external_links:
            external_link = external_links[0]
            for duplicate_link in external_links[1:]:
                duplicate_appointment = self._get_appointment(
                    session,
                    duplicate_link.appointment_id,
                )
                session.delete(duplicate_appointment)
                session.delete(duplicate_link)

        if external_link is None:
            appointment = Appointment(
                connection_id=connection.id,
                title=title,
                starts_at=starts_at,
                ends_at=ends_at,
                timezone_name=self._provider_timezone_name(starts_at),
                all_day=all_day,
                location=location,
                notes=notes,
                attendees_text=attendees_text,
                status=status,
                source="provider_sync",
            )
            session.add(appointment)
            session.flush()
            session.add(
                AppointmentExternalLink(
                    appointment_id=appointment.id,
                    provider_type=connection.provider_type,
                    provider_event_id=provider_event_id,
                    provider_href=href,
                    provider_etag=etag,
                )
            )
            session.flush()
            return

        appointment = self._get_appointment(session, external_link.appointment_id)
        appointment.connection_id = connection.id
        appointment.title = title
        appointment.starts_at = starts_at
        appointment.ends_at = ends_at
        appointment.timezone_name = self._provider_timezone_name(starts_at)
        appointment.all_day = all_day
        appointment.location = location
        appointment.notes = notes
        appointment.attendees_text = attendees_text
        appointment.status = status
        external_link.provider_href = href
        external_link.provider_etag = etag

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

    def _coerce_provider_datetime(self, value: datetime | str) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)

    def _merge_busy_ranges(
        self,
        appointments: list[Appointment],
        *,
        day_start: datetime,
        day_end: datetime,
        timezone: ZoneInfo,
    ) -> list[tuple[datetime, datetime]]:
        busy_ranges: list[tuple[datetime, datetime]] = []
        for appointment in appointments:
            if appointment.all_day:
                busy_ranges.append((day_start, day_end))
                continue
            starts_at = appointment.starts_at.astimezone(timezone)
            ends_at = appointment.ends_at.astimezone(timezone)
            clipped_start = max(starts_at, day_start)
            clipped_end = min(ends_at, day_end)
            if clipped_end <= day_start or clipped_start >= day_end:
                continue
            if clipped_end <= clipped_start:
                continue
            busy_ranges.append((clipped_start, clipped_end))

        busy_ranges.sort(key=lambda item: item[0])
        merged: list[tuple[datetime, datetime]] = []
        for start_value, end_value in busy_ranges:
            if not merged or start_value > merged[-1][1]:
                merged.append((start_value, end_value))
                continue
            merged[-1] = (merged[-1][0], max(merged[-1][1], end_value))
        return merged

    def _provider_timezone_name(self, value: datetime) -> str:
        tzinfo = value.tzinfo
        if tzinfo is None:
            return self.settings.default_timezone
        return getattr(tzinfo, "key", None) or self.settings.default_timezone

    def _resolve_target_calendar_value(
        self,
        target_calendar_url: str | None,
        target_calendar_name: str | None,
    ) -> str:
        if target_calendar_url and target_calendar_url.startswith("google:"):
            return target_calendar_url
        if target_calendar_name:
            try:
                calendar_id = str(
                    self.google_runtime_config.resolve(
                        calendar_name=target_calendar_name,
                    )["primary_calendar_id"]
                )
                if calendar_id:
                    return f"google:{calendar_id}"
            except ValueError:
                pass
        return str(
            self.apple_runtime_config.resolve(
                calendar_url=target_calendar_url,
                calendar_name=target_calendar_name,
            )["primary_calendar_url"]
        )

    def _parse_target_calendar_value(self, value: str | None) -> tuple[str, str]:
        raw = str(value or "").strip()
        if raw.startswith("google:"):
            return ("google_calendar", raw.split(":", 1)[1])
        return ("icloud_caldav", raw)

    def _connection_target_value(self, connection: AppleCalendarConnection) -> str:
        if connection.provider_type == "google_calendar":
            return f"google:{connection.primary_calendar_url}"
        return connection.primary_calendar_url

    def _create_provider_event(
        self,
        connection: AppleCalendarConnection,
        *,
        title: str,
        starts_at: datetime,
        ends_at: datetime,
        all_day: bool,
        location: str | None,
        notes: str | None,
    ):
        if connection.provider_type == "google_calendar":
            return self._google_client_for_calendar(
                connection.primary_calendar_url
            ).create_event(
                calendar_id=connection.primary_calendar_url,
                title=title,
                starts_at=starts_at,
                ends_at=ends_at,
                all_day=all_day,
                location=location,
                notes=notes,
            )
        return self._apple_client_for_calendar(connection.primary_calendar_url).create_event(
            title=title,
            starts_at=starts_at,
            ends_at=ends_at,
            all_day=all_day,
            location=location,
            notes=notes,
        )

    def _update_provider_event(
        self,
        connection: AppleCalendarConnection,
        *,
        provider_event_id: str,
        title: str,
        starts_at: datetime,
        ends_at: datetime,
        all_day: bool,
        location: str | None,
        notes: str | None,
        href: str | None,
        etag: str | None,
    ):
        if connection.provider_type == "google_calendar":
            return self._google_client_for_calendar(
                connection.primary_calendar_url
            ).update_event(
                calendar_id=connection.primary_calendar_url,
                provider_event_id=provider_event_id,
                title=title,
                starts_at=starts_at,
                ends_at=ends_at,
                all_day=all_day,
                location=location,
                notes=notes,
                href=href,
                etag=etag,
            )
        return self._apple_client_for_calendar(connection.primary_calendar_url).update_event(
            provider_event_id=provider_event_id,
            title=title,
            starts_at=starts_at,
            ends_at=ends_at,
            all_day=all_day,
            location=location,
            notes=notes,
            href=href,
            etag=etag,
        )

    def _cancel_provider_event(
        self,
        connection: AppleCalendarConnection,
        *,
        provider_event_id: str,
        href: str | None,
        etag: str | None,
    ) -> None:
        if connection.provider_type == "google_calendar":
            self._google_client_for_calendar(connection.primary_calendar_url).cancel_event(
                calendar_id=connection.primary_calendar_url,
                provider_event_id=provider_event_id,
                href=href,
                etag=etag,
            )
            return
        self._apple_client_for_calendar(connection.primary_calendar_url).cancel_event(
            provider_event_id=provider_event_id,
            href=href,
            etag=etag,
        )

    def _list_provider_events(
        self,
        *,
        provider_type: str,
        external_id: str,
        starts_at: datetime,
        ends_at: datetime,
    ) -> list[AppleListedEvent | GoogleListedEvent]:
        if provider_type == "google_calendar":
            client = self._google_client_for_calendar(external_id)
            if not hasattr(client, "list_events"):
                return []
            return client.list_events(
                calendar_id=external_id,
                starts_at=starts_at,
                ends_at=ends_at,
            )
        client = self._apple_client_for_calendar(external_id)
        if not hasattr(client, "list_events"):
            return []
        return client.list_events(
            starts_at=starts_at,
            ends_at=ends_at,
        )

    def _apple_client_for_calendar(self, calendar_url: str) -> AppleCalDAVClient:
        try:
            return self._build_apple_client(calendar_url=calendar_url)
        except TypeError:
            return self._build_apple_client()

    def _google_client_for_calendar(self, calendar_id: str) -> GoogleCalendarClient:
        try:
            return self._build_google_client(calendar_id=calendar_id)
        except TypeError:
            return self._build_google_client()

    @property
    def display_account_label(self) -> str:
        apple = self.apple_runtime_config.resolve()
        if apple["ready"]:
            return str(apple["account_label"])
        google = self.google_runtime_config.resolve()
        if google["ready"]:
            return str(google["account_label"])
        return "Not connected"

    @property
    def display_calendar_name(self) -> str:
        apple = self.apple_runtime_config.resolve()
        if apple["ready"]:
            return str(apple["primary_calendar_name"])
        google = self.google_runtime_config.resolve()
        if google["ready"]:
            return str(google["primary_calendar_name"])
        return "No calendar selected"

    @property
    def available_calendars(self) -> list[dict[str, object]]:
        calendars: list[dict[str, object]] = [
            {
                "provider_type": "icloud_caldav",
                "calendar_name": str(item["calendar_name"]),
                "calendar_url": str(item["calendar_url"]),
                "is_default": bool(item.get("is_default")),
                "account_label": str(self.apple_runtime_config.resolve()["account_label"]),
            }
            for item in self.apple_runtime_config.list_calendars()
        ]
        google = self.google_runtime_config.resolve()
        calendars.extend(
            [
                {
                    "provider_type": "google_calendar",
                    "calendar_name": str(item["calendar_name"]),
                    "calendar_url": f"google:{item['calendar_id']}",
                    "is_default": bool(item.get("is_default")),
                    "account_label": str(google["account_label"]),
                }
                for item in self.google_runtime_config.list_calendars()
            ]
        )
        return calendars

    def _get_session_factory(self) -> sessionmaker[Session]:
        if self.session_factory is None:
            self.session_factory = create_session_factory(self.settings)
        return self.session_factory

    def _to_list_item(
        self,
        appointment: Appointment,
        external_link: AppointmentExternalLink | None,
    ) -> AppointmentListItem:
        timezone = ZoneInfo(appointment.timezone_name)
        starts_at = appointment.starts_at.astimezone(timezone)
        ends_at = appointment.ends_at.astimezone(timezone)
        return AppointmentListItem(
            appointment_id=appointment.id,
            title=appointment.title,
            status=appointment.status,
            date=starts_at.date().isoformat(),
            start_time=starts_at.strftime("%H:%M"),
            end_time=ends_at.strftime("%H:%M"),
            timezone=appointment.timezone_name,
            all_day=appointment.all_day,
            location=appointment.location,
            notes=appointment.notes,
            attendees_text=appointment.attendees_text,
            provider_event_id=(
                external_link.provider_event_id if external_link is not None else None
            ),
        )
