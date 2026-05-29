from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from datetime import date as date_value
from urllib.parse import quote

import httpx


class GoogleCalendarError(RuntimeError):
    pass


@dataclass(slots=True)
class GoogleOAuthConfig:
    account_label: str
    account_email: str
    client_id: str
    client_secret: str
    refresh_token: str
    primary_calendar_id: str
    primary_calendar_name: str


@dataclass(slots=True)
class GoogleEventRecord:
    provider_event_id: str
    href: str
    etag: str | None


@dataclass(slots=True)
class GoogleListedEvent:
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


class GoogleCalendarClient:
    def __init__(self, config: GoogleOAuthConfig) -> None:
        self.config = config

    def list_calendars(self, *, access_token: str | None = None) -> list[dict[str, object]]:
        response = httpx.get(
            "https://www.googleapis.com/calendar/v3/users/me/calendarList",
            headers=self._headers(access_token=access_token),
            timeout=30,
        )
        self._raise_for_error(response, "Google calendar list request failed.")
        payload = response.json()
        items = payload.get("items", []) if isinstance(payload, dict) else []
        calendars: list[dict[str, object]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            calendar_id = str(item.get("id") or "").strip()
            if not calendar_id:
                continue
            calendars.append(
                {
                    "calendar_name": str(item.get("summaryOverride") or item.get("summary") or calendar_id),
                    "calendar_id": calendar_id,
                    "is_default": bool(item.get("primary")),
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
    ) -> GoogleEventRecord:
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
        self._raise_for_error(response, "Google calendar write request failed.")
        body = response.json()
        return GoogleEventRecord(
            provider_event_id=str(body.get("id") or ""),
            href=f"google:{calendar_id}:{body.get('id') or ''}",
            etag=str(body.get("etag") or "") or None,
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
    ) -> GoogleEventRecord:
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
        self._raise_for_error(response, "Google calendar write request failed.")
        body = response.json()
        return GoogleEventRecord(
            provider_event_id=str(body.get("id") or provider_event_id),
            href=href or f"google:{calendar_id}:{provider_event_id}",
            etag=str(body.get("etag") or "") or None,
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
        self._raise_for_error(response, "Google calendar write request failed.")

    def list_events(
        self,
        *,
        calendar_id: str,
        starts_at: datetime,
        ends_at: datetime,
    ) -> list[GoogleListedEvent]:
        response = httpx.get(
            self._events_url(calendar_id),
            headers=self._headers(),
            params={
                "singleEvents": "true",
                "showDeleted": "false",
                "timeMin": starts_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "timeMax": ends_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "orderBy": "startTime",
            },
            timeout=30,
        )
        self._raise_for_error(response, "Google calendar read request failed.")
        payload = response.json()
        items = payload.get("items", []) if isinstance(payload, dict) else []
        events: list[GoogleListedEvent] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            provider_event_id = str(item.get("id") or "").strip()
            if not provider_event_id:
                continue
            start_value, all_day = self._parse_event_datetime(item.get("start") or {})
            end_value, _ = self._parse_event_datetime(item.get("end") or {})
            events.append(
                GoogleListedEvent(
                    provider_event_id=provider_event_id,
                    href=f"google:{calendar_id}:{provider_event_id}",
                    etag=str(item.get("etag") or "") or None,
                    title=str(item.get("summary") or "Untitled event"),
                    starts_at=start_value,
                    ends_at=end_value,
                    all_day=all_day,
                    location=self._optional_text(item.get("location")),
                    notes=self._optional_text(item.get("description")),
                    status=str(item.get("status") or "confirmed").lower(),
                    attendees_text=self._attendees_text(item.get("attendees")),
                )
            )
        return events

    def exchange_code(self, *, code: str, redirect_uri: str) -> dict[str, str]:
        response = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=30,
        )
        self._raise_for_error(response, "Google token exchange failed.")
        payload = response.json()
        return {
            "refresh_token": str(payload.get("refresh_token") or ""),
            "access_token": str(payload.get("access_token") or ""),
        }

    def current_user_email(self, *, access_token: str | None = None) -> str:
        response = httpx.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers=self._headers(access_token=access_token),
            timeout=30,
        )
        self._raise_for_error(response, "Google account lookup failed.")
        payload = response.json()
        email = str(payload.get("email") or "").strip()
        if not email:
            raise GoogleCalendarError("Google account email was not returned.")
        return email

    def authorization_url(self, *, redirect_uri: str, state: str) -> str:
        query = httpx.QueryParams(
            {
                "client_id": self.config.client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "openid email profile https://www.googleapis.com/auth/calendar",
                "access_type": "offline",
                "prompt": "consent",
                "state": state,
            }
        )
        return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"

    def _refresh_access_token(self) -> str:
        response = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "refresh_token": self.config.refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        self._raise_for_error(response, "Google access refresh failed.")
        payload = response.json()
        access_token = str(payload.get("access_token") or "").strip()
        if not access_token:
            raise GoogleCalendarError("Google access refresh did not return a token.")
        return access_token

    def _headers(self, *, access_token: str | None = None) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token or self._refresh_access_token()}",
            "Accept": "application/json",
        }

    def _events_url(self, calendar_id: str) -> str:
        return f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar_id, safe='')}/events"

    def _event_payload(
        self,
        *,
        title: str,
        starts_at: datetime,
        ends_at: datetime,
        all_day: bool,
        location: str | None,
        notes: str | None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "summary": title,
        }
        if location:
            payload["location"] = location
        if notes:
            payload["description"] = notes
        if all_day:
            payload["start"] = {"date": starts_at.astimezone(UTC).date().isoformat()}
            payload["end"] = {"date": ends_at.astimezone(UTC).date().isoformat()}
        else:
            payload["start"] = {"dateTime": starts_at.isoformat()}
            payload["end"] = {"dateTime": ends_at.isoformat()}
        return payload

    def _raise_for_error(self, response: httpx.Response, message: str) -> None:
        if response.status_code == 401:
            raise GoogleCalendarError("Google authentication failed.")
        if response.status_code >= 400:
            raise GoogleCalendarError(message)

    def _parse_event_datetime(
        self,
        payload: dict[str, object],
    ) -> tuple[datetime, bool]:
        date_time_value = str(payload.get("dateTime") or "").strip()
        if date_time_value:
            parsed = datetime.fromisoformat(date_time_value.replace("Z", "+00:00"))
            return (
                parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC),
                False,
            )

        date_text = str(payload.get("date") or "").strip()
        if not date_text:
            raise GoogleCalendarError("Google event time payload was incomplete.")
        parsed_date = date_value.fromisoformat(date_text)
        return (datetime(parsed_date.year, parsed_date.month, parsed_date.day, tzinfo=UTC), True)

    @staticmethod
    def _optional_text(value: object) -> str | None:
        text = str(value or "").strip()
        return text or None

    @staticmethod
    def _attendees_text(value: object) -> str | None:
        if not isinstance(value, list):
            return None
        attendees = [
            str(item.get("email") or item.get("displayName") or "").strip()
            for item in value
            if isinstance(item, dict)
        ]
        attendees = [item for item in attendees if item]
        return ", ".join(attendees) if attendees else None
