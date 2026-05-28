from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
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
        if response.status_code == 401:
            raise AppleCalDAVError("Apple/iCloud authentication failed.")
        if response.status_code >= 400:
            raise AppleCalDAVError("Apple/iCloud calendar write request failed.")
        return response.headers.get("ETag")
