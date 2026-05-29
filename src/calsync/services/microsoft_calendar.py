from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote

import httpx
from dateutil import tz


class MicrosoftCalendarError(RuntimeError):
    pass


@dataclass(slots=True)
class MicrosoftOAuthConfig:
    account_label: str
    account_email: str
    client_id: str
    client_secret: str
    refresh_token: str
    primary_calendar_id: str
    primary_calendar_name: str


@dataclass(slots=True)
class MicrosoftEventRecord:
    provider_event_id: str
    href: str
    etag: str | None


@dataclass(slots=True)
class MicrosoftListedEvent:
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
    attendees_text: str | None


class MicrosoftCalendarClient:
    def __init__(self, config: MicrosoftOAuthConfig) -> None:
        self.config = config

    def authorization_url(self, *, redirect_uri: str, state: str) -> str:
        query = httpx.QueryParams(
            {
                "client_id": self.config.client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "response_mode": "query",
                "scope": "offline_access openid User.Read Calendars.ReadWrite",
                "state": state,
            }
        )
        return (
            "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
            f"?{query}"
        )

    def exchange_code(self, *, code: str, redirect_uri: str) -> dict[str, str]:
        response = httpx.post(
            "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            data={
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=30,
        )
        self._raise_for_error(response, "Microsoft token exchange failed.")
        payload = response.json()
        return {
            "refresh_token": str(payload.get("refresh_token") or ""),
            "access_token": str(payload.get("access_token") or ""),
        }

    def current_user_email(self, *, access_token: str | None = None) -> str:
        response = httpx.get(
            "https://graph.microsoft.com/v1.0/me",
            headers=self._headers(access_token=access_token),
            timeout=30,
        )
        self._raise_for_error(response, "Microsoft account lookup failed.")
        payload = response.json()
        email = str(
            payload.get("mail")
            or payload.get("userPrincipalName")
            or ""
        ).strip()
        if not email:
            raise MicrosoftCalendarError("Microsoft account email was not returned.")
        return email

    def list_calendars(self, *, access_token: str | None = None) -> list[dict[str, object]]:
        response = httpx.get(
            "https://graph.microsoft.com/v1.0/me/calendars",
            headers=self._headers(access_token=access_token),
            timeout=30,
        )
        self._raise_for_error(response, "Microsoft calendar list request failed.")
        payload = response.json()
        items = payload.get("value", []) if isinstance(payload, dict) else []
        calendars: list[dict[str, object]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            calendar_id = str(item.get("id") or "").strip()
            if not calendar_id:
                continue
            calendars.append(
                {
                    "calendar_name": str(item.get("name") or calendar_id),
                    "calendar_id": calendar_id,
                    "is_default": bool(item.get("isDefaultCalendar")),
                }
            )
        if calendars and not any(item["is_default"] for item in calendars):
            calendars[0]["is_default"] = True
        return calendars

    def create_event(
        self,
        *,
        calendar_id: str,
        title: str,
        starts_at: datetime,
        ends_at: datetime,
        all_day: bool,
        location: str | None,
        notes: str | None,
    ) -> MicrosoftEventRecord:
        response = httpx.post(
            self._events_url(calendar_id),
            headers=self._headers(),
            json=self._event_payload(
                title=title,
                starts_at=starts_at,
                ends_at=ends_at,
                all_day=all_day,
                location=location,
                notes=notes,
            ),
            timeout=30,
        )
        self._raise_for_error(response, "Microsoft calendar write request failed.")
        body = response.json()
        return MicrosoftEventRecord(
            provider_event_id=str(body.get("id") or ""),
            href=f"microsoft:{calendar_id}:{body.get('id') or ''}",
            etag=str(body.get("@odata.etag") or "") or None,
        )

    def update_event(
        self,
        *,
        calendar_id: str,
        provider_event_id: str,
        title: str,
        starts_at: datetime,
        ends_at: datetime,
        all_day: bool,
        location: str | None,
        notes: str | None,
        href: str | None = None,
        etag: str | None = None,
    ) -> MicrosoftEventRecord:
        headers = self._headers()
        if etag:
            headers["If-Match"] = etag
        response = httpx.patch(
            f"{self._events_url(calendar_id)}/{quote(provider_event_id, safe='')}",
            headers=headers,
            json=self._event_payload(
                title=title,
                starts_at=starts_at,
                ends_at=ends_at,
                all_day=all_day,
                location=location,
                notes=notes,
            ),
            timeout=30,
        )
        self._raise_for_error(response, "Microsoft calendar write request failed.")
        body = response.json()
        return MicrosoftEventRecord(
            provider_event_id=str(body.get("id") or provider_event_id),
            href=href or f"microsoft:{calendar_id}:{provider_event_id}",
            etag=str(body.get("@odata.etag") or "") or None,
        )

    def cancel_event(
        self,
        *,
        calendar_id: str,
        provider_event_id: str,
        href: str | None = None,
        etag: str | None = None,
    ) -> None:
        headers = self._headers()
        if etag:
            headers["If-Match"] = etag
        response = httpx.delete(
            f"{self._events_url(calendar_id)}/{quote(provider_event_id, safe='')}",
            headers=headers,
            timeout=30,
        )
        self._raise_for_error(response, "Microsoft calendar write request failed.")

    def list_events(
        self,
        *,
        calendar_id: str,
        starts_at: datetime,
        ends_at: datetime,
    ) -> list[MicrosoftListedEvent]:
        response = httpx.get(
            self._events_url(calendar_id),
            headers={
                **self._headers(),
                "Prefer": 'outlook.timezone="UTC"',
            },
            params={
                "$top": "200",
                "$orderby": "start/dateTime",
                "startDateTime": starts_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "endDateTime": ends_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            },
            timeout=30,
        )
        self._raise_for_error(response, "Microsoft calendar read request failed.")
        payload = response.json()
        items = payload.get("value", []) if isinstance(payload, dict) else []
        events: list[MicrosoftListedEvent] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            provider_event_id = str(item.get("id") or "").strip()
            if not provider_event_id:
                continue
            start_value, all_day_value = self._parse_event_datetime(
                item.get("start") or {},
                all_day=bool(item.get("isAllDay", False)),
            )
            end_value, _ = self._parse_event_datetime(
                item.get("end") or {},
                all_day=bool(item.get("isAllDay", False)),
            )
            events.append(
                MicrosoftListedEvent(
                    provider_event_id=provider_event_id,
                    href=f"microsoft:{calendar_id}:{provider_event_id}",
                    etag=str(item.get("@odata.etag") or "") or None,
                    title=str(item.get("subject") or "Untitled event"),
                    starts_at=start_value,
                    ends_at=end_value,
                    all_day=all_day_value,
                    location=self._nested_text(item.get("location"), "displayName"),
                    notes=self._optional_text(item.get("bodyPreview")),
                    status="cancelled" if bool(item.get("isCancelled")) else "confirmed",
                    attendees_text=self._attendees_text(item.get("attendees")),
                )
            )
        return events

    def _refresh_access_token(self) -> str:
        response = httpx.post(
            "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            data={
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "refresh_token": self.config.refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        self._raise_for_error(response, "Microsoft access refresh failed.")
        payload = response.json()
        access_token = str(payload.get("access_token") or "").strip()
        if not access_token:
            raise MicrosoftCalendarError("Microsoft access refresh did not return a token.")
        return access_token

    def _headers(self, *, access_token: str | None = None) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token or self._refresh_access_token()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _events_url(calendar_id: str) -> str:
        return f"https://graph.microsoft.com/v1.0/me/calendars/{quote(calendar_id, safe='')}/events"

    @staticmethod
    def _event_payload(
        *,
        title: str,
        starts_at: datetime,
        ends_at: datetime,
        all_day: bool,
        location: str | None,
        notes: str | None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "subject": title,
        }
        if location:
            payload["location"] = {"displayName": location}
        if notes:
            payload["body"] = {
                "contentType": "text",
                "content": notes,
            }
        if all_day:
            start_date = starts_at.astimezone(UTC).date().isoformat()
            end_date = ends_at.astimezone(UTC).date().isoformat()
            payload["isAllDay"] = True
            payload["start"] = {"dateTime": f"{start_date}T00:00:00", "timeZone": "UTC"}
            payload["end"] = {"dateTime": f"{end_date}T00:00:00", "timeZone": "UTC"}
        else:
            payload["start"] = {"dateTime": starts_at.isoformat(), "timeZone": "UTC"}
            payload["end"] = {"dateTime": ends_at.isoformat(), "timeZone": "UTC"}
        return payload

    @staticmethod
    def _raise_for_error(response: httpx.Response, message: str) -> None:
        if response.status_code == 401:
            raise MicrosoftCalendarError("Microsoft authentication failed.")
        if response.status_code >= 400:
            raise MicrosoftCalendarError(message)

    @staticmethod
    def _parse_event_datetime(
        payload: dict[str, object],
        *,
        all_day: bool,
    ) -> tuple[datetime, bool]:
        value = str(payload.get("dateTime") or "").strip()
        if not value:
            raise MicrosoftCalendarError("Microsoft event time payload was incomplete.")
        timezone_name = str(payload.get("timeZone") or "UTC").strip() or "UTC"
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            timezone_info = UTC if timezone_name.upper() == "UTC" else tz.gettz(timezone_name)
            if timezone_info is None:
                raise MicrosoftCalendarError(
                    "Microsoft event datetime must include a recognized timezone."
                )
            parsed = parsed.replace(tzinfo=timezone_info)
        return parsed, all_day

    @staticmethod
    def _optional_text(value: object) -> str | None:
        text = str(value or "").strip()
        return text or None

    @staticmethod
    def _nested_text(value: object, key: str) -> str | None:
        if isinstance(value, dict):
            return MicrosoftCalendarClient._optional_text(value.get(key))
        return None

    @staticmethod
    def _attendees_text(value: object) -> str | None:
        if not isinstance(value, list):
            return None
        attendees = []
        for item in value:
            if not isinstance(item, dict):
                continue
            email = MicrosoftCalendarClient._nested_text(item.get("emailAddress"), "address")
            name = MicrosoftCalendarClient._nested_text(item.get("emailAddress"), "name")
            attendees.append(email or name or "")
        attendees = [item for item in attendees if item]
        return ", ".join(attendees) if attendees else None
