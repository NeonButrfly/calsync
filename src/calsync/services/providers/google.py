from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from sqlalchemy.orm import Session

from calsync.config import (
    Settings,
    build_google_callback_url_from_base,
    get_settings,
    validate_google_callback_url,
)
from calsync.crypto import decrypt_text, encrypt_text
from calsync.models import ProviderAccount, ProviderCalendar, utcnow
from calsync.repos.providers import (
    get_provider_account_by_identity,
    upsert_provider_account,
)
from calsync.services.provider_config import (
    GoogleOAuthConfiguration,
    resolve_google_oauth_configuration,
)
from calsync.schemas.providers import DiscoveredCalendar, NormalizedEvent


GOOGLE_OAUTH_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_CALENDAR_LIST_URL = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
GOOGLE_EVENTS_URL_TEMPLATE = (
    "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
)
GOOGLE_PROVIDER_TYPE = "google"
ACCOUNT_DISCOVERY_SYNC_TOKEN_KEY = "google_calendar_list_sync_token"
CALENDAR_EVENTS_SYNC_TOKEN_KEY = "google_events_sync_token"
ACCOUNT_EMAIL_KEY = "google_email"
ACCOUNT_SUBJECT_KEY = "google_subject"
ACCOUNT_SCOPES_KEY = "google_scopes"
ACCOUNT_TOKEN_EXPIRY_KEY = "google_access_token_expires_at"
ACCOUNT_AUTH_STATUS_KEY = "google_auth_status"
ACCOUNT_RECONNECT_REQUIRED_KEY = "google_reconnect_required"
ACCOUNT_LAST_AUTH_ERROR_KEY = "google_last_auth_error"


class GoogleOAuthError(RuntimeError):
    pass


class GoogleOAuthCompatibilityError(GoogleOAuthError):
    pass


class GoogleProviderAdapter:
    provider_type = GOOGLE_PROVIDER_TYPE

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        session: Session | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.session = session
        self.last_calendar_discovery_was_incremental = False

    def discover_calendars(
        self,
        account: ProviderAccount,
    ) -> list[DiscoveredCalendar]:
        metadata = _account_metadata(account)
        self.last_calendar_discovery_was_incremental = bool(
            isinstance(metadata.get(ACCOUNT_DISCOVERY_SYNC_TOKEN_KEY), str)
            and metadata.get(ACCOUNT_DISCOVERY_SYNC_TOKEN_KEY)
        )
        response_payload = self._get_calendar_list(account)
        metadata = _account_metadata(account)
        next_sync_token = response_payload.get("nextSyncToken")
        if isinstance(next_sync_token, str) and next_sync_token:
            metadata[ACCOUNT_DISCOVERY_SYNC_TOKEN_KEY] = next_sync_token
        account.provider_metadata = metadata

        calendars: list[DiscoveredCalendar] = []
        for item in response_payload.get("items", []):
            if not isinstance(item, dict) or not item.get("id"):
                continue
            deleted = bool(item.get("deleted", False))
            calendars.append(
                DiscoveredCalendar(
                    external_id=str(item["id"]),
                    name=str(item.get("summary") or item["id"]),
                    timezone=_optional_str(item.get("timeZone")),
                    default_enabled=False,
                    deleted=deleted,
                    metadata={
                        "color": item.get("backgroundColor"),
                        "access_role": item.get("accessRole"),
                        "hidden": bool(item.get("hidden", False)),
                        "selected": bool(item.get("selected", True)),
                        "primary": bool(item.get("primary", False)),
                        "deleted": deleted,
                    },
                )
            )
        return calendars

    def fetch_events(
        self,
        account: ProviderAccount,
        calendar: ProviderCalendar,
    ) -> list[NormalizedEvent]:
        response_payload = self._get_events(account, calendar)
        metadata = _calendar_metadata(calendar)
        next_sync_token = response_payload.get("nextSyncToken")
        if isinstance(next_sync_token, str) and next_sync_token:
            metadata[CALENDAR_EVENTS_SYNC_TOKEN_KEY] = next_sync_token
        calendar.provider_metadata = metadata

        events: list[NormalizedEvent] = []
        for item in response_payload.get("items", []):
            if not isinstance(item, dict):
                continue
            if not item.get("id") or not item.get("start") or not item.get("end"):
                continue
            events.append(_normalize_google_event(account, calendar, item))
        return events

    def _get_calendar_list(self, account: ProviderAccount) -> dict[str, object]:
        metadata = _account_metadata(account)
        params: dict[str, Any] = {"maxResults": 250}
        sync_token = metadata.get(ACCOUNT_DISCOVERY_SYNC_TOKEN_KEY)
        if isinstance(sync_token, str) and sync_token:
            params["syncToken"] = sync_token

        try:
            return self._get_paginated_json(
                account,
                GOOGLE_CALENDAR_LIST_URL,
                params=params,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 410 or "syncToken" not in params:
                raise
            metadata.pop(ACCOUNT_DISCOVERY_SYNC_TOKEN_KEY, None)
            account.provider_metadata = metadata
            return self._get_paginated_json(
                account,
                GOOGLE_CALENDAR_LIST_URL,
                params={"maxResults": 250},
            )

    def _get_events(
        self,
        account: ProviderAccount,
        calendar: ProviderCalendar,
    ) -> dict[str, object]:
        metadata = _calendar_metadata(calendar)
        params: dict[str, Any] = {
            "maxResults": 2500,
            "showDeleted": "true",
        }
        sync_token = metadata.get(CALENDAR_EVENTS_SYNC_TOKEN_KEY)
        if isinstance(sync_token, str) and sync_token:
            params["syncToken"] = sync_token

        url = GOOGLE_EVENTS_URL_TEMPLATE.format(
            calendar_id=quote(calendar.provider_calendar_id, safe="")
        )
        try:
            return self._get_paginated_json(account, url, params=params)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 410 or "syncToken" not in params:
                raise
            metadata.pop(CALENDAR_EVENTS_SYNC_TOKEN_KEY, None)
            calendar.provider_metadata = metadata
            return self._get_paginated_json(
                account,
                url,
                params={
                    "maxResults": 2500,
                    "showDeleted": "true",
                },
            )

    def _get_paginated_json(
        self,
        account: ProviderAccount,
        url: str,
        *,
        params: dict[str, Any],
    ) -> dict[str, object]:
        aggregated_items: list[object] = []
        next_sync_token: str | None = None
        page_token: str | None = None
        final_payload: dict[str, object] = {}

        while True:
            page_params = dict(params)
            if page_token:
                page_params["pageToken"] = page_token
            payload = self._authorized_get_json(account, url, params=page_params)
            final_payload = dict(payload)
            items = payload.get("items")
            if isinstance(items, list):
                aggregated_items.extend(items)
            maybe_sync_token = payload.get("nextSyncToken")
            if isinstance(maybe_sync_token, str) and maybe_sync_token:
                next_sync_token = maybe_sync_token
            page_token = payload.get("nextPageToken")
            if not isinstance(page_token, str) or not page_token:
                break

        final_payload["items"] = aggregated_items
        if next_sync_token:
            final_payload["nextSyncToken"] = next_sync_token
        return final_payload

    def _authorized_get_json(
        self,
        account: ProviderAccount,
        url: str,
        *,
        params: dict[str, Any],
    ) -> dict[str, object]:
        access_token = ensure_google_access_token(
            account,
            settings=self.settings,
            session=self.session,
        )
        with _build_http_client() as client:
            response = client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if response.status_code == 401:
                access_token = ensure_google_access_token(
                    account,
                    settings=self.settings,
                    session=self.session,
                    force_refresh=True,
                )
                response = client.get(
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise GoogleOAuthError("Google provider returned an invalid response.")
            return payload


def build_google_authorization_url(
    callback_url: str,
    state: str,
    *,
    settings: Settings | None = None,
    session: Session | None = None,
    force_consent: bool = False,
) -> str:
    resolved_settings = settings or get_settings()
    oauth_configuration = _require_google_config(
        session=session,
        settings=resolved_settings,
        encryption_key=resolved_settings.encryption_key,
    )
    compatibility_error = validate_google_callback_url(callback_url)
    if compatibility_error is not None:
        raise GoogleOAuthCompatibilityError(compatibility_error)

    query = {
        "client_id": oauth_configuration.client_id,
        "redirect_uri": callback_url,
        "response_type": "code",
        "scope": " ".join(oauth_configuration.scopes),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "state": state,
    }
    if force_consent:
        query["prompt"] = "consent"
    return f"{GOOGLE_OAUTH_AUTHORIZE_URL}?{urlencode(query)}"


def connect_google_account_from_callback(
    session,
    *,
    code: str,
    callback_base_url: str,
    settings: Settings | None = None,
    encryption_key: str,
) -> ProviderAccount:
    resolved_settings = settings or get_settings()
    callback_url = build_google_callback_url_from_base(
        callback_base_url,
        settings=resolved_settings,
    )
    token_payload = exchange_google_code_for_tokens(
        code,
        callback_url,
        settings=resolved_settings,
        session=session,
    )
    access_token = _required_str(token_payload.get("access_token"))
    user_info = fetch_google_user_info(access_token)
    provider_account_id = _required_str(user_info.get("sub"))
    existing_account = get_provider_account_by_identity(
        session,
        provider_type=GOOGLE_PROVIDER_TYPE,
        provider_account_id=provider_account_id,
    )
    return persist_google_oauth_account(
        session,
        account=existing_account,
        token_payload=token_payload,
        user_info=user_info,
        encryption_key=encryption_key,
    )


def exchange_google_code_for_tokens(
    code: str,
    callback_url: str,
    *,
    settings: Settings | None = None,
    session: Session | None = None,
) -> dict[str, object]:
    resolved_settings = settings or get_settings()
    oauth_configuration = _require_google_config(
        session=session,
        settings=resolved_settings,
        encryption_key=resolved_settings.encryption_key,
    )
    with _build_http_client() as client:
        response = client.post(
            GOOGLE_OAUTH_TOKEN_URL,
            data={
                "code": code,
                "client_id": oauth_configuration.client_id,
                "client_secret": oauth_configuration.client_secret,
                "redirect_uri": callback_url,
                "grant_type": "authorization_code",
            },
        )
        if response.status_code >= 400:
            raise GoogleOAuthError(_safe_google_oauth_error(response))
        payload = response.json()
        if not isinstance(payload, dict):
            raise GoogleOAuthError("Google token exchange returned an invalid response.")
        return payload


def fetch_google_user_info(access_token: str) -> dict[str, object]:
    with _build_http_client() as client:
        response = client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code >= 400:
            raise GoogleOAuthError("Google account identity lookup failed.")
        payload = response.json()
        if not isinstance(payload, dict):
            raise GoogleOAuthError(
                "Google account identity lookup returned an invalid response."
            )
        return payload


def persist_google_oauth_account(
    session,
    *,
    account: ProviderAccount | None,
    token_payload: dict[str, object],
    user_info: dict[str, object],
    encryption_key: str,
) -> ProviderAccount:
    provider_account_id = _required_str(user_info.get("sub"))
    resolved_account = account or upsert_provider_account(
        session,
        provider_type=GOOGLE_PROVIDER_TYPE,
        provider_account_id=provider_account_id,
    )
    is_new_account = account is None
    refresh_token = _optional_str(token_payload.get("refresh_token"))
    if is_new_account and not refresh_token:
        raise GoogleOAuthError(
            "Google did not return a refresh token. Retry the connection and grant consent again."
        )

    access_token = _required_str(token_payload.get("access_token"))
    resolved_account.access_token_encrypted = encrypt_text(encryption_key, access_token)
    if refresh_token:
        resolved_account.refresh_token_encrypted = encrypt_text(
            encryption_key,
            refresh_token,
        )
    elif not resolved_account.refresh_token_encrypted:
        raise GoogleOAuthError(
            "Google did not return a refresh token. Retry the connection and grant consent again."
        )

    metadata = _account_metadata(resolved_account)
    metadata[ACCOUNT_EMAIL_KEY] = _optional_str(user_info.get("email"))
    metadata[ACCOUNT_SUBJECT_KEY] = provider_account_id
    scope_text = _optional_str(token_payload.get("scope"))
    if scope_text:
        metadata[ACCOUNT_SCOPES_KEY] = scope_text.split()
    expires_in = token_payload.get("expires_in")
    if isinstance(expires_in, (int, float)):
        metadata[ACCOUNT_TOKEN_EXPIRY_KEY] = (
            utcnow() + timedelta(seconds=int(expires_in))
        ).isoformat()
    metadata[ACCOUNT_AUTH_STATUS_KEY] = "connected"
    metadata[ACCOUNT_RECONNECT_REQUIRED_KEY] = False
    metadata.pop(ACCOUNT_LAST_AUTH_ERROR_KEY, None)
    resolved_account.provider_metadata = metadata
    resolved_account.display_name = (
        _optional_str(user_info.get("email"))
        or _optional_str(user_info.get("name"))
        or resolved_account.provider_account_id
    )
    session.add(resolved_account)
    session.flush()
    return resolved_account


def ensure_google_access_token(
    account: ProviderAccount,
    *,
    settings: Settings | None = None,
    session: Session | None = None,
    force_refresh: bool = False,
) -> str:
    resolved_settings = settings or get_settings()
    encryption_key = resolved_settings.encryption_key
    if not encryption_key:
        raise RuntimeError("CalSync encryption_key must be configured explicitly.")

    if not force_refresh and account.access_token_encrypted and _token_is_still_fresh(account):
        return decrypt_text(encryption_key, account.access_token_encrypted)

    refresh_token = None
    if account.refresh_token_encrypted:
        refresh_token = decrypt_text(encryption_key, account.refresh_token_encrypted)
    if not refresh_token:
        _mark_google_reconnect_required(
            account,
            "Google account requires reconnection because no refresh token is available.",
        )
        raise GoogleOAuthError("Google account requires reconnection.")

    try:
        token_payload = refresh_google_access_token(
            refresh_token,
            settings=resolved_settings,
            session=session,
        )
    except GoogleOAuthError as exc:
        _mark_google_reconnect_required(account, str(exc))
        raise
    new_access_token = _required_str(token_payload.get("access_token"))
    account.access_token_encrypted = encrypt_text(encryption_key, new_access_token)
    metadata = _account_metadata(account)
    expires_in = token_payload.get("expires_in")
    if isinstance(expires_in, (int, float)):
        metadata[ACCOUNT_TOKEN_EXPIRY_KEY] = (
            utcnow() + timedelta(seconds=int(expires_in))
        ).isoformat()
    scope_text = _optional_str(token_payload.get("scope"))
    if scope_text:
        metadata[ACCOUNT_SCOPES_KEY] = scope_text.split()
    metadata[ACCOUNT_AUTH_STATUS_KEY] = "connected"
    metadata[ACCOUNT_RECONNECT_REQUIRED_KEY] = False
    metadata.pop(ACCOUNT_LAST_AUTH_ERROR_KEY, None)
    account.provider_metadata = metadata
    return new_access_token


def refresh_google_access_token(
    refresh_token: str,
    *,
    settings: Settings | None = None,
    session: Session | None = None,
) -> dict[str, object]:
    resolved_settings = settings or get_settings()
    oauth_configuration = _require_google_config(
        session=session,
        settings=resolved_settings,
        encryption_key=resolved_settings.encryption_key,
    )
    with _build_http_client() as client:
        response = client.post(
            GOOGLE_OAUTH_TOKEN_URL,
            data={
                "client_id": oauth_configuration.client_id,
                "client_secret": oauth_configuration.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        if response.status_code >= 400:
            raise GoogleOAuthError(_safe_google_refresh_error(response))
        payload = response.json()
        if not isinstance(payload, dict):
            raise GoogleOAuthError("Google token refresh returned an invalid response.")
        return payload


def _build_http_client() -> httpx.Client:
    return httpx.Client(timeout=30)


def _require_google_config(
    *,
    session: Session | None,
    settings: Settings,
    encryption_key: str | None,
) -> GoogleOAuthConfiguration:
    oauth_configuration = resolve_google_oauth_configuration(
        session,
        settings=settings,
        encryption_key=encryption_key,
    )
    if oauth_configuration is not None:
        return oauth_configuration
    raise GoogleOAuthError(
        "Google OAuth is not configured. Add the Google client ID and secret on the Provider Settings page."
    )


def _account_metadata(account: ProviderAccount) -> dict[str, object]:
    return dict(account.provider_metadata or {})


def _calendar_metadata(calendar: ProviderCalendar) -> dict[str, object]:
    return dict(calendar.provider_metadata or {})


def _token_is_still_fresh(account: ProviderAccount) -> bool:
    metadata = _account_metadata(account)
    expires_at = metadata.get(ACCOUNT_TOKEN_EXPIRY_KEY)
    if not isinstance(expires_at, str):
        return False
    try:
        expiry = datetime.fromisoformat(expires_at)
    except ValueError:
        return False
    if expiry.tzinfo is None or expiry.utcoffset() is None:
        expiry = expiry.replace(tzinfo=UTC)
    return expiry > (utcnow() + timedelta(minutes=2))


def _mark_google_reconnect_required(account: ProviderAccount, message: str) -> None:
    metadata = _account_metadata(account)
    metadata[ACCOUNT_AUTH_STATUS_KEY] = "reconnect_required"
    metadata[ACCOUNT_RECONNECT_REQUIRED_KEY] = True
    metadata[ACCOUNT_LAST_AUTH_ERROR_KEY] = message
    account.provider_metadata = metadata


def _normalize_google_event(
    account: ProviderAccount,
    calendar: ProviderCalendar,
    payload: dict[str, object],
) -> NormalizedEvent:
    start_info = payload["start"]
    end_info = payload["end"]
    assert isinstance(start_info, dict)
    assert isinstance(end_info, dict)

    starts_at, all_day = _parse_google_event_datetime(start_info)
    ends_at, _ = _parse_google_event_datetime(end_info)
    return NormalizedEvent(
        provider_type=GOOGLE_PROVIDER_TYPE,
        provider_account_id=account.provider_account_id,
        provider_calendar_id=calendar.provider_calendar_id,
        provider_event_id=str(payload["id"]),
        title=_optional_str(payload.get("summary")) or "Untitled event",
        description=_optional_str(payload.get("description")),
        location=_optional_str(payload.get("location")),
        starts_at=starts_at,
        ends_at=ends_at,
        all_day=all_day,
        status=_optional_str(payload.get("status")) or "confirmed",
        source_payload=dict(payload),
    )


def _parse_google_event_datetime(payload: dict[str, object]) -> tuple[datetime, bool]:
    if "dateTime" in payload:
        value = _required_str(payload.get("dateTime"))
        return _parse_rfc3339_datetime(value), False
    if "date" in payload:
        value = _required_str(payload.get("date"))
        parsed_date = date.fromisoformat(value)
        return datetime.combine(parsed_date, datetime.min.time(), tzinfo=UTC), True
    raise GoogleOAuthError("Google event payload is missing start or end time.")


def _parse_rfc3339_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise GoogleOAuthError("Google event datetime must be timezone-aware.")
    return parsed


def _safe_google_oauth_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return "Google OAuth token exchange failed."
    if isinstance(payload, dict) and payload.get("error") == "invalid_grant":
        return "Google authorization code was rejected or expired."
    return "Google OAuth token exchange failed."


def _safe_google_refresh_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return "Google access refresh failed. Reconnect the account."
    if isinstance(payload, dict) and payload.get("error") == "invalid_grant":
        return "Google access refresh failed because the grant was revoked. Reconnect the account."
    return "Google access refresh failed. Reconnect the account."


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _required_str(value: object) -> str:
    if value is None:
        raise GoogleOAuthError("Google provider response is missing a required value.")
    return str(value)
