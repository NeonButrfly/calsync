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
            connection = self._ensure_connection(
                session,
                calendar_url=payload.target_calendar_url,
            )
            provider_record = self._client_for_calendar(
                connection.primary_calendar_url
            ).create_event(
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
                        calendar_url=str(calendar["calendar_url"]),
                    )
                session.commit()
            except (AppleCalDAVError, AttributeError):
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
            target_calendar_url = payload.target_calendar_url or connection.primary_calendar_url

            if target_calendar_url != connection.primary_calendar_url:
                next_connection = self._ensure_connection(
                    session,
                    calendar_url=target_calendar_url,
                )
                provider_record = self._client_for_calendar(
                    next_connection.primary_calendar_url
                ).create_event(
                    title=title,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    all_day=all_day,
                    location=location,
                    notes=notes,
                )
                self._client_for_calendar(connection.primary_calendar_url).cancel_event(
                    provider_event_id=external_link.provider_event_id,
                    href=external_link.provider_href,
                    etag=external_link.provider_etag,
                )
                appointment.connection_id = next_connection.id
                external_link.provider_event_id = provider_record.provider_event_id
            else:
                provider_record = self._client_for_calendar(
                    connection.primary_calendar_url
                ).update_event(
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

    def cancel(self, appointment_id: str, actor: str = "api") -> AppointmentResponse:
        with self._get_session_factory()() as session:
            appointment = self._get_appointment(session, appointment_id)
            external_link = self._get_external_link(session, appointment_id)
            connection = session.get(AppleCalendarConnection, appointment.connection_id)
            if connection is None:
                raise ValueError("Appointment calendar connection not found.")
            self._client_for_calendar(connection.primary_calendar_url).cancel_event(
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
                calendar_url=connection.primary_calendar_url,
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

    def _build_apple_client(self, calendar_url: str | None = None) -> AppleCalDAVClient:
        config = self.apple_runtime_config.resolve(calendar_url=calendar_url)
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

    def _ensure_connection(
        self,
        session: Session,
        *,
        calendar_url: str | None = None,
    ) -> AppleCalendarConnection:
        config = self.apple_runtime_config.resolve(calendar_url=calendar_url)
        if not config["ready"]:
            raise ValueError("Primary Apple/iCloud calendar is not configured.")
        existing = session.scalar(
            select(AppleCalendarConnection).where(
                AppleCalendarConnection.primary_calendar_url
                == str(config["primary_calendar_url"])
            )
        )
        if existing is not None:
            existing.account_label = str(config["account_label"])
            existing.apple_username = str(config["username"])
            existing.primary_calendar_name = str(config["primary_calendar_name"])
            existing.is_primary = bool(
                self.apple_runtime_config.resolve()["primary_calendar_url"]
                == existing.primary_calendar_url
            )
            return existing
        connection = AppleCalendarConnection(
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
        calendar_url: str,
    ) -> None:
        connection = self._ensure_connection(session, calendar_url=calendar_url)
        client = self._client_for_calendar(calendar_url)
        if not hasattr(client, "list_events"):
            return
        provider_events = client.list_events(
            starts_at=starts_at,
            ends_at=ends_at + timedelta(days=1),
        )
        seen_provider_event_ids: set[str] = set()
        for provider_event in provider_events:
            provider_event_id = str(getattr(provider_event, "provider_event_id"))
            if provider_event_id in seen_provider_event_ids:
                continue
            seen_provider_event_ids.add(provider_event_id)
            self._upsert_synced_apple_event(
                session,
                connection=connection,
                provider_event=provider_event,
            )

    def _upsert_synced_apple_event(
        self,
        session: Session,
        *,
        connection: AppleCalendarConnection,
        provider_event: AppleListedEvent | object,
    ) -> None:
        provider_event_id = str(getattr(provider_event, "provider_event_id"))
        external_links = session.scalars(
            select(AppointmentExternalLink)
            .join(
                Appointment,
                Appointment.id == AppointmentExternalLink.appointment_id,
            )
            .where(
                AppointmentExternalLink.provider_type == "icloud_caldav",
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
                attendees_text=None,
                status=status,
                source="provider_sync",
            )
            session.add(appointment)
            session.flush()
            session.add(
                AppointmentExternalLink(
                    appointment_id=appointment.id,
                    provider_type="icloud_caldav",
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

    def _provider_timezone_name(self, value: datetime) -> str:
        tzinfo = value.tzinfo
        if tzinfo is None:
            return self.settings.default_timezone
        return getattr(tzinfo, "key", None) or self.settings.default_timezone

    def _client_for_calendar(self, calendar_url: str | None) -> AppleCalDAVClient:
        try:
            return self._build_apple_client(calendar_url=calendar_url)
        except TypeError:
            return self._build_apple_client()

    @property
    def display_account_label(self) -> str:
        return str(self.apple_runtime_config.resolve()["account_label"])

    @property
    def display_calendar_name(self) -> str:
        return str(self.apple_runtime_config.resolve()["primary_calendar_name"])

    @property
    def available_calendars(self) -> list[dict[str, object]]:
        return self.apple_runtime_config.list_calendars()

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
