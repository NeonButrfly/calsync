from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from datetime import date as date_value
from xml.etree import ElementTree as ET
from urllib.parse import urljoin
from uuid import uuid4

import httpx
from icalendar import Calendar, Event as ICalEvent


class AppleCalDAVError(RuntimeError):
    pass


@dataclass(slots=True)
class AppleCalDAVConfig:
    account_label: str
    apple_username: str
    app_specific_password: str
    primary_calendar_url: str
    primary_calendar_name: str


@dataclass(slots=True)
class AppleEventRecord:
    provider_event_id: str
    href: str
    etag: str | None


@dataclass(slots=True)
class AppleListedEvent:
    provider_event_id: str
    href: str
    etag: str | None
    title: str
    starts_at: datetime
    ends_at: datetime
    all_day: bool
    location: str | None
    notes: str | None
    status: str


def build_event_payload(
    *,
    uid: str,
    title: str,
    starts_at: datetime,
    ends_at: datetime,
    all_day: bool,
    location: str | None,
    notes: str | None,
) -> bytes:
    calendar = Calendar()
    calendar.add("prodid", "-//CalSync//EN")
    calendar.add("version", "2.0")
    event = ICalEvent()
    event.add("uid", uid)
    event.add("summary", title)
    if location:
        event.add("location", location)
    if notes:
        event.add("description", notes)
    if all_day:
        event.add("dtstart", starts_at.astimezone(UTC).date())
        event.add("dtend", ends_at.astimezone(UTC).date())
    else:
        event.add("dtstart", starts_at.astimezone(UTC))
        event.add("dtend", ends_at.astimezone(UTC))
    event.add("status", "CONFIRMED")
    event.add("dtstamp", datetime.now(UTC))
    calendar.add_component(event)
    return calendar.to_ical()


class AppleCalDAVClient:
    def __init__(self, config: AppleCalDAVConfig) -> None:
        self.config = config

    def validate_calendar_access(self) -> None:
        starts_at = datetime.now(UTC)
        self.list_events(
            starts_at=starts_at,
            ends_at=starts_at + timedelta(days=1),
        )

    def resource_href(self, provider_event_id: str) -> str:
        base_url = self.config.primary_calendar_url
        if not base_url.endswith("/"):
            base_url = f"{base_url}/"
        return urljoin(base_url, f"{provider_event_id}.ics")

    def create_event(
        self,
        *,
        title: str,
        starts_at: datetime,
        ends_at: datetime,
        all_day: bool,
        location: str | None,
        notes: str | None,
    ) -> AppleEventRecord:
        provider_event_id = str(uuid4())
        href = self.resource_href(provider_event_id)
        etag = self._request_mutation(
            "PUT",
            href,
            build_event_payload(
                uid=provider_event_id,
                title=title,
                starts_at=starts_at,
                ends_at=ends_at,
                all_day=all_day,
                location=location,
                notes=notes,
            ),
        )
        return AppleEventRecord(
            provider_event_id=provider_event_id,
            href=href,
            etag=etag,
        )

    def update_event(
        self,
        *,
        provider_event_id: str,
        title: str,
        starts_at: datetime,
        ends_at: datetime,
        all_day: bool,
        location: str | None,
        notes: str | None,
        href: str | None = None,
        etag: str | None = None,
    ) -> AppleEventRecord:
        target_href = href or self.resource_href(provider_event_id)
        next_etag = self._request_mutation(
            "PUT",
            target_href,
            build_event_payload(
                uid=provider_event_id,
                title=title,
                starts_at=starts_at,
                ends_at=ends_at,
                all_day=all_day,
                location=location,
                notes=notes,
            ),
            etag=etag,
        )
        return AppleEventRecord(
            provider_event_id=provider_event_id,
            href=target_href,
            etag=next_etag,
        )

    def cancel_event(
        self,
        *,
        provider_event_id: str,
        href: str | None = None,
        etag: str | None = None,
    ) -> None:
        self._request_mutation(
            "DELETE",
            href or self.resource_href(provider_event_id),
            None,
            etag=etag,
        )

    def list_events(
        self,
        *,
        starts_at: datetime,
        ends_at: datetime,
    ) -> list[AppleListedEvent]:
        body = self._build_calendar_query(starts_at=starts_at, ends_at=ends_at)
        try:
            response = httpx.request(
                "REPORT",
                self.config.primary_calendar_url,
                auth=(
                    self.config.apple_username,
                    self.config.app_specific_password,
                ),
                content=body,
                headers={
                    "Depth": "1",
                    "Content-Type": "application/xml; charset=utf-8",
                },
                timeout=30,
            )
        except httpx.HTTPError as exc:
            raise AppleCalDAVError("Apple/iCloud calendar read request failed.") from exc
        if response.status_code == 401:
            raise AppleCalDAVError("Apple/iCloud authentication failed.")
        if response.status_code >= 400:
            raise AppleCalDAVError("Apple/iCloud calendar read request failed.")
        return self._parse_calendar_report(response.text)

    def _build_calendar_query(self, *, starts_at: datetime, ends_at: datetime) -> bytes:
        start_text = starts_at.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
        end_text = ends_at.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
        return f"""<?xml version="1.0" encoding="utf-8"?>
<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
  <d:prop>
    <d:getetag />
    <c:calendar-data />
  </d:prop>
  <c:filter>
    <c:comp-filter name="VCALENDAR">
      <c:comp-filter name="VEVENT">
        <c:time-range start="{start_text}" end="{end_text}" />
      </c:comp-filter>
    </c:comp-filter>
  </c:filter>
</c:calendar-query>
""".encode("utf-8")

    def _parse_calendar_report(self, xml_text: str) -> list[AppleListedEvent]:
        namespace = {
            "d": "DAV:",
            "c": "urn:ietf:params:xml:ns:caldav",
        }
        root = ET.fromstring(xml_text)
        events: list[AppleListedEvent] = []
        for response_node in root.findall("d:response", namespace):
            href = response_node.findtext("d:href", default="", namespaces=namespace)
            resolved_href = urljoin(self.config.primary_calendar_url, href)
            etag = response_node.findtext(
                "d:propstat/d:prop/d:getetag",
                default=None,
                namespaces=namespace,
            )
            calendar_data = response_node.findtext(
                "d:propstat/d:prop/c:calendar-data",
                default=None,
                namespaces=namespace,
            )
            if not calendar_data:
                continue
            calendar = Calendar.from_ical(calendar_data)
            for component in calendar.walk("VEVENT"):
                provider_event_id = str(component.get("uid") or "").strip()
                if not provider_event_id:
                    continue
                starts_at = self._coerce_event_datetime(component.decoded("dtstart"))
                ends_at = self._coerce_event_datetime(component.decoded("dtend"))
                all_day = isinstance(component.decoded("dtstart"), date_value) and not isinstance(
                    component.decoded("dtstart"), datetime
                )
                events.append(
                    AppleListedEvent(
                        provider_event_id=provider_event_id,
                        href=resolved_href,
                        etag=etag,
                        title=str(component.get("summary") or "Untitled event"),
                        starts_at=starts_at,
                        ends_at=ends_at,
                        all_day=all_day,
                        location=self._optional_component_text(component, "location"),
                        notes=self._optional_component_text(component, "description"),
                        status=str(component.get("status") or "CONFIRMED").lower(),
                    )
                )
        return events

    def _coerce_event_datetime(self, value: datetime | date_value) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return datetime(value.year, value.month, value.day, tzinfo=UTC)

    def _optional_component_text(
        self,
        component: ICalEvent,
        field_name: str,
    ) -> str | None:
        value = component.get(field_name)
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _request_mutation(
        self,
        method: str,
        href: str,
        content: bytes | None,
        *,
        etag: str | None = None,
    ) -> str | None:
        headers: dict[str, str] = {}
        if content is not None:
            headers["Content-Type"] = "text/calendar; charset=utf-8"
        if etag:
            headers["If-Match"] = etag
        try:
            response = httpx.request(
                method,
                href,
                auth=(
                    self.config.apple_username,
                    self.config.app_specific_password,
                ),
                content=content,
                headers=headers,
                timeout=30,
            )
        except httpx.HTTPError as exc:
            raise AppleCalDAVError("Apple/iCloud calendar write request failed.") from exc
        if response.status_code == 401:
            raise AppleCalDAVError("Apple/iCloud authentication failed.")
        if response.status_code >= 400:
            raise AppleCalDAVError("Apple/iCloud calendar write request failed.")
        return response.headers.get("ETag")
