from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

import httpx
from icalendar import Calendar

from calsync.config import Settings, get_settings
from calsync.crypto import decrypt_text
from calsync.models import ProviderAccount, ProviderCalendar
from calsync.schemas.providers import DiscoveredCalendar, NormalizedEvent


ICLOUD_PROVIDER_TYPE = "icloud_caldav"
ICLOUD_BASE_URL = "https://caldav.icloud.com/"
DAV_NAMESPACE = "DAV:"
CALDAV_NAMESPACE = "urn:ietf:params:xml:ns:caldav"
CALSERVER_NAMESPACE = "http://calendarserver.org/ns/"
NAMESPACES = {
    "D": DAV_NAMESPACE,
    "C": CALDAV_NAMESPACE,
    "CS": CALSERVER_NAMESPACE,
}


class ICloudCalDAVError(RuntimeError):
    pass


class ICloudCalDAVProviderAdapter:
    provider_type = ICLOUD_PROVIDER_TYPE

    def __init__(self, *, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def discover_calendars(
        self,
        account: ProviderAccount,
    ) -> list[DiscoveredCalendar]:
        principal_url = self._discover_principal_url(account)
        calendar_home_url = self._discover_calendar_home_url(account, principal_url)
        xml_payload = self._request_xml(
            account,
            "PROPFIND",
            calendar_home_url,
            depth="1",
            body=(
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                "<D:propfind xmlns:D=\"DAV:\" xmlns:C=\"urn:ietf:params:xml:ns:caldav\" "
                "xmlns:CS=\"http://calendarserver.org/ns/\">"
                "<D:prop><D:displayname /><D:resourcetype />"
                "<C:calendar-timezone /><CS:getctag /></D:prop>"
                "</D:propfind>"
            ),
        )
        root = ET.fromstring(xml_payload)
        calendars: list[DiscoveredCalendar] = []
        for response in root.findall("D:response", NAMESPACES):
            if not _response_has_calendar_type(response):
                continue
            href = _text_or_none(response.find("D:href", NAMESPACES))
            if not href:
                continue
            absolute_href = urljoin(calendar_home_url, href)
            display_name = _text_or_none(
                response.find(".//D:displayname", NAMESPACES)
            ) or absolute_href.rstrip("/").rsplit("/", 1)[-1]
            timezone = _text_or_none(
                response.find(".//C:calendar-timezone", NAMESPACES)
            )
            calendars.append(
                DiscoveredCalendar(
                    external_id=absolute_href,
                    name=display_name,
                    timezone=timezone,
                    default_enabled=False,
                    metadata={
                        "href": absolute_href,
                        "ctag": _text_or_none(
                            response.find(".//CS:getctag", NAMESPACES)
                        ),
                    },
                )
            )

        metadata = dict(account.provider_metadata or {})
        metadata["auth_status"] = "connected"
        metadata["principal_url"] = principal_url
        metadata["calendar_home_url"] = calendar_home_url
        metadata["last_auth_error"] = None
        account.provider_metadata = metadata
        return calendars

    def fetch_events(
        self,
        account: ProviderAccount,
        calendar: ProviderCalendar,
    ) -> list[NormalizedEvent]:
        calendar_url = calendar.provider_calendar_id
        xml_payload = self._request_xml(
            account,
            "REPORT",
            calendar_url,
            depth="1",
            body=(
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                "<C:calendar-query xmlns:D=\"DAV:\" xmlns:C=\"urn:ietf:params:xml:ns:caldav\">"
                "<D:prop><D:getetag /><C:calendar-data /></D:prop>"
                "<C:filter><C:comp-filter name=\"VCALENDAR\">"
                "<C:comp-filter name=\"VEVENT\" />"
                "</C:comp-filter></C:filter>"
                "</C:calendar-query>"
            ),
        )
        root = ET.fromstring(xml_payload)
        events: list[NormalizedEvent] = []
        for response in root.findall("D:response", NAMESPACES):
            href = _text_or_none(response.find("D:href", NAMESPACES))
            calendar_data = _text_or_none(
                response.find(".//C:calendar-data", NAMESPACES)
            )
            if not href or not calendar_data:
                continue
            etag = _text_or_none(response.find(".//D:getetag", NAMESPACES))
            parsed_calendar = Calendar.from_ical(calendar_data)
            for component in parsed_calendar.walk("VEVENT"):
                events.append(
                    _normalize_ical_event(
                        account,
                        calendar,
                        component,
                        href=urljoin(calendar_url, href),
                        etag=etag,
                    )
                )
        return events

    def _discover_principal_url(self, account: ProviderAccount) -> str:
        xml_payload = self._request_xml(
            account,
            "PROPFIND",
            ICLOUD_BASE_URL,
            depth="0",
            body=(
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                "<D:propfind xmlns:D=\"DAV:\">"
                "<D:prop><D:current-user-principal /></D:prop>"
                "</D:propfind>"
            ),
        )
        root = ET.fromstring(xml_payload)
        principal_href = _text_or_none(
            root.find(".//D:current-user-principal/D:href", NAMESPACES)
        )
        if not principal_href:
            raise ICloudCalDAVError("Apple/iCloud principal discovery failed.")
        return urljoin(ICLOUD_BASE_URL, principal_href)

    def _discover_calendar_home_url(
        self,
        account: ProviderAccount,
        principal_url: str,
    ) -> str:
        xml_payload = self._request_xml(
            account,
            "PROPFIND",
            principal_url,
            depth="0",
            body=(
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                "<D:propfind xmlns:D=\"DAV:\" xmlns:C=\"urn:ietf:params:xml:ns:caldav\">"
                "<D:prop><C:calendar-home-set /></D:prop>"
                "</D:propfind>"
            ),
        )
        root = ET.fromstring(xml_payload)
        home_href = _text_or_none(root.find(".//C:calendar-home-set/D:href", NAMESPACES))
        if not home_href:
            raise ICloudCalDAVError("Apple/iCloud calendar discovery failed.")
        return urljoin(principal_url, home_href)

    def _request_xml(
        self,
        account: ProviderAccount,
        method: str,
        url: str,
        *,
        depth: str,
        body: str,
    ) -> str:
        username, password = _get_icloud_credentials(account, settings=self.settings)
        with _build_http_client() as client:
            response = client.request(
                method,
                url,
                content=body.encode("utf-8"),
                auth=(username, password),
                headers={
                    "Content-Type": "application/xml; charset=utf-8",
                    "Depth": depth,
                },
            )
        if response.status_code == 401:
            metadata = dict(account.provider_metadata or {})
            metadata["auth_status"] = "error"
            metadata["last_auth_error"] = (
                "Apple/iCloud authentication failed. Verify the Apple ID and app-specific password."
            )
            account.provider_metadata = metadata
            raise ICloudCalDAVError(metadata["last_auth_error"])
        if response.status_code >= 400:
            raise ICloudCalDAVError("Apple/iCloud CalDAV request failed.")
        return response.text


def _build_http_client() -> httpx.Client:
    return httpx.Client(timeout=30)


def _get_icloud_credentials(
    account: ProviderAccount,
    *,
    settings: Settings,
) -> tuple[str, str]:
    if not settings.encryption_key:
        raise RuntimeError("CalSync encryption_key must be configured explicitly.")
    if not account.credential_secret_encrypted:
        raise ICloudCalDAVError("Apple/iCloud account is missing an app-specific password.")
    return (
        account.provider_account_id,
        decrypt_text(settings.encryption_key, account.credential_secret_encrypted),
    )


def _response_has_calendar_type(response: ET.Element) -> bool:
    resource_type = response.find(".//D:resourcetype", NAMESPACES)
    if resource_type is None:
        return False
    return resource_type.find("C:calendar", NAMESPACES) is not None


def _normalize_ical_event(
    account: ProviderAccount,
    calendar: ProviderCalendar,
    component: Any,
    *,
    href: str,
    etag: str | None,
) -> NormalizedEvent:
    starts_at, all_day = _normalize_ical_datetime(component.decoded("DTSTART"))
    ends_at, _ = _normalize_ical_datetime(component.decoded("DTEND"))
    uid = str(component.get("UID") or PurePosixPath(href).stem)
    return NormalizedEvent(
        provider_type=ICLOUD_PROVIDER_TYPE,
        provider_account_id=account.provider_account_id,
        provider_calendar_id=calendar.provider_calendar_id,
        provider_event_id=uid,
        title=str(component.get("SUMMARY") or "Untitled event"),
        description=_string_or_none(component.get("DESCRIPTION")),
        location=_string_or_none(component.get("LOCATION")),
        starts_at=starts_at,
        ends_at=ends_at,
        all_day=all_day,
        status=_string_or_none(component.get("STATUS")) or "confirmed",
        source_payload={
            "href": href,
            "etag": etag,
        },
    )


def _normalize_ical_datetime(value: Any) -> tuple[datetime, bool]:
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime.combine(value, datetime.min.time(), tzinfo=UTC), True
    if not isinstance(value, datetime):
        raise ICloudCalDAVError("Apple/iCloud event payload is missing a valid datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=UTC)
    return value, False


def _text_or_none(element: ET.Element | None) -> str | None:
    if element is None or element.text is None:
        return None
    text = element.text.strip()
    return text or None


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
