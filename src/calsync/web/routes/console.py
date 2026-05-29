from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from importlib.resources import files
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo
from zipfile import ZipFile

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import SQLAlchemyError

from calsync.schemas.appointments import (
    AppointmentDetailResponse,
    AppointmentListItem,
    AvailabilitySlot,
    CreateAppointmentRequest,
    UpdateAppointmentRequest,
)
from calsync.services.apple_caldav import AppleCalDAVError
from calsync.services.alexa_simulator import AlexaSimulatorService
from calsync.services.appointments import AppointmentService
from calsync.services.apple_runtime_config import AppleRuntimeConfigService
from calsync.services.cloudflare_worker_config import CloudflareWorkerConfigService
from calsync.services.google_calendar import (
    GoogleCalendarClient,
    GoogleCalendarError,
    GoogleOAuthConfig,
)
from calsync.services.google_runtime_config import GoogleRuntimeConfigService
from calsync.services.microsoft_calendar import (
    MicrosoftCalendarClient,
    MicrosoftCalendarError,
    MicrosoftOAuthConfig,
)
from calsync.services.microsoft_runtime_config import MicrosoftRuntimeConfigService
from calsync.services.operator_settings import OperatorSettingsService
from calsync.services.readiness import ReadinessService


router = APIRouter(tags=["console"])

_templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)

_WINDOWS: dict[str, tuple[str, int]] = {
    "day": ("Today", 0),
    "week": ("Next 7 days", 6),
    "month": ("Next 30 days", 29),
}


@router.get("/privacy")
def privacy_page(request: Request):
    return _templates.TemplateResponse(
        request,
        "privacy.html",
        {
            "request": request,
        },
    )


@router.get("/terms")
def terms_page(request: Request):
    return _templates.TemplateResponse(
        request,
        "terms.html",
        {
            "request": request,
        },
    )


@router.get("/alexa/setup")
def alexa_setup_page(request: Request):
    readiness = ReadinessService().build()
    edge_settings = CloudflareWorkerConfigService().get_alexa_settings()
    cloudflare_credentials = OperatorSettingsService().describe_cloudflare_worker_credentials()
    return _templates.TemplateResponse(
        request,
        "alexa_setup.html",
        {
            "request": request,
            "readiness": readiness,
            "edge_settings": edge_settings,
            "cloudflare_credentials": cloudflare_credentials,
            "alexa_endpoint": "https://edge-calsync.neonbutterfly.net/alexa",
            "privacy_url": "https://calsync.neonbutterfly.net/privacy",
            "terms_url": "https://calsync.neonbutterfly.net/terms",
            "simulator_url": "/alexa/simulator",
            "flash_message": None,
            "error_message": None,
        },
    )


@router.get("/calendar/setup")
def calendar_setup_page(request: Request):
    operator_settings = OperatorSettingsService()
    apple_settings = operator_settings.describe_apple_calendar_settings()
    runtime_service = AppleRuntimeConfigService(operator_settings=operator_settings)
    runtime_config = runtime_service.resolve()
    return _templates.TemplateResponse(
        request,
        "calendar_setup.html",
        {
            "request": request,
            "apple_settings": apple_settings,
            "runtime_config": runtime_config,
            "apple_accounts": runtime_service.list_accounts(),
            "calendar_catalog": runtime_service.list_calendars(),
            "flash_message": None,
            "error_message": None,
        },
    )


@router.get("/connections")
def connections_page(request: Request):
    return _templates.TemplateResponse(
        request,
        "connections.html",
        _build_connections_context(
            request,
            flash_message=None,
            error_message=None,
        ),
    )


@router.post("/connections/test")
def connections_run_write_test(
    request: Request,
    target_calendar_url: str = Form(""),
):
    operator_settings = OperatorSettingsService()
    service = AppointmentService()
    try:
        result = service.run_write_smoke_test(
            target_calendar_url=target_calendar_url,
            actor="console",
        )
        flash_message = _write_test_success_message(result)
        _record_write_test_verification(
            operator_settings,
            service,
            target_calendar_url=target_calendar_url,
            passed=True,
            message=flash_message,
            result=result,
        )
        error_message = None
    except (
        AppleCalDAVError,
        GoogleCalendarError,
        MicrosoftCalendarError,
        ValueError,
    ) as exc:
        flash_message = None
        error_message = str(exc)
        _record_write_test_verification(
            operator_settings,
            service,
            target_calendar_url=target_calendar_url,
            passed=False,
            message=error_message,
            result=None,
        )

    return _templates.TemplateResponse(
        request,
        "connections.html",
        _build_connections_context(
            request,
            flash_message=flash_message,
            error_message=error_message,
        ),
        status_code=200 if error_message is None else 400,
    )


@router.post("/calendar/setup")
def calendar_setup_update(
    request: Request,
    apple_account_label: str = Form(""),
    apple_username: str = Form(""),
    apple_app_specific_password: str = Form(""),
    apple_primary_calendar_url: str = Form(""),
    apple_primary_calendar_name: str = Form(""),
):
    operator_settings = OperatorSettingsService()
    try:
        operator_settings.set_apple_calendar_settings(
            account_label=apple_account_label,
            username=apple_username,
            app_specific_password=apple_app_specific_password,
            primary_calendar_url=apple_primary_calendar_url,
            primary_calendar_name=apple_primary_calendar_name,
            preserve_existing_password=True,
        )
        flash_message = "Apple calendar settings saved securely."
        error_message = None
    except ValueError as exc:
        flash_message = None
        error_message = str(exc)

    apple_settings = operator_settings.describe_apple_calendar_settings()
    runtime_service = AppleRuntimeConfigService(
        operator_settings=operator_settings
    )
    runtime_config = runtime_service.resolve()
    return _templates.TemplateResponse(
        request,
        "calendar_setup.html",
        {
            "request": request,
            "apple_settings": apple_settings,
            "runtime_config": runtime_config,
            "apple_accounts": runtime_service.list_accounts(),
            "calendar_catalog": runtime_service.list_calendars(),
            "flash_message": flash_message,
            "error_message": error_message,
        },
        status_code=200 if error_message is None else 400,
    )


@router.post("/calendar/setup/calendars")
def calendar_setup_add_calendar(
    request: Request,
    account_username: str = Form(""),
    calendar_name: str = Form(""),
    calendar_url: str = Form(""),
    is_default: str | None = Form(None),
):
    operator_settings = OperatorSettingsService()
    runtime_service = AppleRuntimeConfigService(operator_settings=operator_settings)
    try:
        normalized_username = account_username.strip()
        accounts = runtime_service.list_accounts()
        if not normalized_username and len(accounts) == 1:
            normalized_username = str(accounts[0].get("username") or "")
        if normalized_username and not operator_settings.get_apple_accounts():
            runtime_config = runtime_service.resolve(username=normalized_username)
            operator_settings.upsert_apple_account(
                account_label=str(runtime_config["account_label"]),
                username=str(runtime_config["username"]),
                app_specific_password=str(runtime_config["app_specific_password"]),
                calendars=[
                    {
                        "calendar_name": str(item["calendar_name"]),
                        "calendar_url": str(item["calendar_url"]),
                        "is_default": bool(item.get("is_default")),
                    }
                    for item in runtime_service.list_calendars()
                    if str(item.get("username") or "") == normalized_username
                ] or [
                    {
                        "calendar_name": str(runtime_config["primary_calendar_name"]),
                        "calendar_url": str(runtime_config["primary_calendar_url"]),
                        "is_default": True,
                    }
                ],
            )
        operator_settings.add_apple_calendar_target(
            account_username=normalized_username,
            calendar_name=calendar_name,
            calendar_url=calendar_url,
            is_default=is_default == "true",
        )
        flash_message = "Apple calendar target added."
        error_message = None
    except ValueError as exc:
        flash_message = None
        error_message = str(exc)

    apple_settings = operator_settings.describe_apple_calendar_settings()
    runtime_config = runtime_service.resolve()
    return _templates.TemplateResponse(
        request,
        "calendar_setup.html",
        {
            "request": request,
            "apple_settings": apple_settings,
            "runtime_config": runtime_config,
            "apple_accounts": runtime_service.list_accounts(),
            "calendar_catalog": runtime_service.list_calendars(),
            "flash_message": flash_message,
            "error_message": error_message,
        },
        status_code=200 if error_message is None else 400,
    )


@router.post("/calendar/setup/test")
def calendar_setup_run_write_test(
    request: Request,
    target_calendar_url: str = Form(""),
):
    service = AppointmentService()
    operator_settings = OperatorSettingsService()
    try:
        result = service.run_write_smoke_test(
            target_calendar_url=target_calendar_url,
            actor="console",
        )
        flash_message = _write_test_success_message(result)
        _record_write_test_verification(
            operator_settings,
            service,
            target_calendar_url=target_calendar_url,
            passed=True,
            message=flash_message,
            result=result,
        )
        error_message = None
    except (
        AppleCalDAVError,
        GoogleCalendarError,
        MicrosoftCalendarError,
        ValueError,
    ) as exc:
        flash_message = None
        error_message = str(exc)
        _record_write_test_verification(
            operator_settings,
            service,
            target_calendar_url=target_calendar_url,
            passed=False,
            message=error_message,
            result=None,
        )

    runtime_service = AppleRuntimeConfigService(operator_settings=operator_settings)
    runtime_config = runtime_service.resolve()
    return _templates.TemplateResponse(
        request,
        "calendar_setup.html",
        {
            "request": request,
            "apple_settings": operator_settings.describe_apple_calendar_settings(),
            "runtime_config": runtime_config,
            "apple_accounts": runtime_service.list_accounts(),
            "calendar_catalog": runtime_service.list_calendars(),
            "flash_message": flash_message,
            "error_message": error_message,
        },
        status_code=200 if error_message is None else 400,
    )


@router.get("/google/setup")
def google_setup_page(request: Request):
    operator_settings = OperatorSettingsService()
    google_settings = operator_settings.describe_google_oauth_settings()
    runtime_service = GoogleRuntimeConfigService(operator_settings=operator_settings)
    runtime_config = runtime_service.resolve()
    return _templates.TemplateResponse(
        request,
        "google_setup.html",
        {
            "request": request,
            "google_settings": google_settings,
            "runtime_config": runtime_config,
            "google_accounts": runtime_service.list_accounts(),
            "calendar_catalog": runtime_service.list_calendars(),
            "flash_message": None,
            "error_message": None,
            "connect_url": "/auth/google/start",
        },
    )


def _build_google_client_from_settings(
    operator_settings: OperatorSettingsService,
    *,
    account_email: str | None = None,
) -> GoogleCalendarClient:
    oauth_settings = operator_settings.get_google_oauth_settings()
    runtime_service = GoogleRuntimeConfigService(operator_settings=operator_settings)
    runtime_config = runtime_service.resolve(account_email=account_email)
    client_id = str(oauth_settings["client_id"] or "").strip()
    client_secret = str(oauth_settings["client_secret"] or "").strip()
    refresh_token = str(runtime_config["refresh_token"] or "").strip()
    if not client_id or not client_secret:
        raise ValueError("Google OAuth settings are incomplete.")
    if not refresh_token:
        raise ValueError("Google account is not connected yet.")
    return GoogleCalendarClient(
        GoogleOAuthConfig(
            account_label=str(runtime_config["account_label"] or "Google"),
            account_email=str(runtime_config["account_email"] or ""),
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            primary_calendar_id=str(runtime_config["primary_calendar_id"] or "primary"),
            primary_calendar_name=str(runtime_config["primary_calendar_name"] or "Primary"),
        )
    )


def _build_microsoft_client_from_settings(
    operator_settings: OperatorSettingsService,
    *,
    account_email: str | None = None,
) -> MicrosoftCalendarClient:
    oauth_settings = operator_settings.get_microsoft_oauth_settings()
    runtime_service = MicrosoftRuntimeConfigService(operator_settings=operator_settings)
    runtime_config = runtime_service.resolve(account_email=account_email)
    client_id = str(oauth_settings["client_id"] or "").strip()
    client_secret = str(oauth_settings["client_secret"] or "").strip()
    refresh_token = str(runtime_config["refresh_token"] or "").strip()
    if not client_id or not client_secret:
        raise ValueError("Microsoft OAuth settings are incomplete.")
    if not refresh_token:
        raise ValueError("Microsoft account is not connected yet.")
    return MicrosoftCalendarClient(
        MicrosoftOAuthConfig(
            account_label=str(runtime_config["account_label"] or "Microsoft"),
            account_email=str(runtime_config["account_email"] or ""),
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            primary_calendar_id=str(runtime_config["primary_calendar_id"] or "primary"),
            primary_calendar_name=str(runtime_config["primary_calendar_name"] or "Primary"),
        )
    )


@router.post("/google/setup")
def google_setup_update(
    request: Request,
    google_client_id: str = Form(""),
    google_client_secret: str = Form(""),
):
    operator_settings = OperatorSettingsService()
    try:
        operator_settings.set_google_oauth_settings(
            client_id=google_client_id,
            client_secret=google_client_secret,
            preserve_existing_secret=True,
        )
        flash_message = "Google OAuth settings saved securely."
        error_message = None
    except ValueError as exc:
        flash_message = None
        error_message = str(exc)

    google_settings = operator_settings.describe_google_oauth_settings()
    runtime_service = GoogleRuntimeConfigService(operator_settings=operator_settings)
    runtime_config = runtime_service.resolve()
    return _templates.TemplateResponse(
        request,
        "google_setup.html",
        {
            "request": request,
            "google_settings": google_settings,
            "runtime_config": runtime_config,
            "google_accounts": runtime_service.list_accounts(),
            "calendar_catalog": runtime_service.list_calendars(),
            "flash_message": flash_message,
            "error_message": error_message,
            "connect_url": "/auth/google/start",
        },
        status_code=200 if error_message is None else 400,
    )


@router.post("/google/setup/refresh")
def google_setup_refresh(request: Request):
    operator_settings = OperatorSettingsService()
    requested_account_email = str((request.query_params.get("account_email") or "")).strip() or None
    try:
        client = _build_google_client_from_settings(
            operator_settings,
            account_email=requested_account_email,
        )
        selected_runtime = GoogleRuntimeConfigService(
            operator_settings=operator_settings
        ).resolve(account_email=requested_account_email)
        account_email = client.current_user_email()
        calendar_catalog = client.list_calendars()
        previous_account_email = str(selected_runtime["account_email"] or "").strip()
        if previous_account_email and previous_account_email.lower() != account_email.lower():
            operator_settings.remove_google_account(previous_account_email)
        operator_settings.upsert_google_account(
            account_label=account_email,
            account_email=account_email,
            refresh_token=str(selected_runtime["refresh_token"] or ""),
            calendars=calendar_catalog,
        )
        flash_message = "Google calendars refreshed from the live account."
        error_message = None
    except (GoogleCalendarError, ValueError) as exc:
        flash_message = None
        error_message = str(exc)

    google_settings = operator_settings.describe_google_oauth_settings()
    runtime_service = GoogleRuntimeConfigService(operator_settings=operator_settings)
    runtime_config = runtime_service.resolve()
    return _templates.TemplateResponse(
        request,
        "google_setup.html",
        {
            "request": request,
            "google_settings": google_settings,
            "runtime_config": runtime_config,
            "google_accounts": runtime_service.list_accounts(),
            "calendar_catalog": runtime_service.list_calendars(),
            "flash_message": flash_message,
            "error_message": error_message,
            "connect_url": "/auth/google/start",
        },
        status_code=200 if error_message is None else 400,
    )


@router.post("/google/setup/disconnect")
def google_setup_disconnect(request: Request):
    operator_settings = OperatorSettingsService()
    operator_settings.clear_google_oauth_state()
    account_email = str((request.query_params.get("account_email") or "")).strip() or None
    if account_email:
        operator_settings.remove_google_account(account_email)
    else:
        operator_settings.clear_google_account_settings()
        operator_settings.clear_google_calendar_catalog()
    google_settings = operator_settings.describe_google_oauth_settings()
    runtime_service = GoogleRuntimeConfigService(operator_settings=operator_settings)
    runtime_config = runtime_service.resolve() if runtime_service.list_accounts() else {
        "account_label": "",
        "account_email": "",
        "refresh_token": "",
        "client_id": str(operator_settings.get_google_oauth_settings()["client_id"] or ""),
        "client_secret": str(operator_settings.get_google_oauth_settings()["client_secret"] or ""),
        "primary_calendar_id": "",
        "primary_calendar_name": "",
        "source": "product_vault" if google_settings["client_id"] else "missing",
        "ready": False,
        "calendars": [],
        "accounts": [],
    }
    return _templates.TemplateResponse(
        request,
        "google_setup.html",
        {
            "request": request,
            "google_settings": google_settings,
            "runtime_config": runtime_config,
            "google_accounts": runtime_service.list_accounts(),
            "calendar_catalog": runtime_service.list_calendars(),
            "flash_message": "Google account disconnected. The shared OAuth app is still saved.",
            "error_message": None,
            "connect_url": "/auth/google/start",
        },
    )


@router.post("/google/setup/test")
def google_setup_run_write_test(
    request: Request,
    target_calendar_url: str = Form(""),
):
    service = AppointmentService()
    operator_settings = OperatorSettingsService()
    runtime_service = GoogleRuntimeConfigService(operator_settings=operator_settings)
    try:
        result = service.run_write_smoke_test(
            target_calendar_url=target_calendar_url,
            actor="console",
        )
        flash_message = _write_test_success_message(result)
        _record_write_test_verification(
            operator_settings,
            service,
            target_calendar_url=target_calendar_url,
            passed=True,
            message=flash_message,
            result=result,
        )
        error_message = None
    except (
        AppleCalDAVError,
        GoogleCalendarError,
        MicrosoftCalendarError,
        ValueError,
    ) as exc:
        flash_message = None
        error_message = str(exc)
        _record_write_test_verification(
            operator_settings,
            service,
            target_calendar_url=target_calendar_url,
            passed=False,
            message=error_message,
            result=None,
        )

    return _templates.TemplateResponse(
        request,
        "google_setup.html",
        {
            "request": request,
            "google_settings": operator_settings.describe_google_oauth_settings(),
            "runtime_config": runtime_service.resolve(),
            "google_accounts": runtime_service.list_accounts(),
            "calendar_catalog": runtime_service.list_calendars(),
            "flash_message": flash_message,
            "error_message": error_message,
            "connect_url": "/auth/google/start",
        },
        status_code=200 if error_message is None else 400,
    )


@router.get("/auth/google/start")
def google_oauth_start(request: Request):
    operator_settings = OperatorSettingsService()
    oauth_settings = operator_settings.get_google_oauth_settings()
    client_id = str(oauth_settings["client_id"] or "").strip()
    client_secret = str(oauth_settings["client_secret"] or "").strip()
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Google OAuth settings are incomplete.")

    state = str(uuid4())
    operator_settings.set_google_oauth_state(state)
    redirect_uri = str(request.url_for("google_oauth_callback"))
    client = GoogleCalendarClient(
        GoogleOAuthConfig(
            account_label="Google",
            account_email="",
            client_id=client_id,
            client_secret=client_secret,
            refresh_token="placeholder",
            primary_calendar_id="primary",
            primary_calendar_name="Primary",
        )
    )
    return RedirectResponse(
        client.authorization_url(redirect_uri=redirect_uri, state=state),
        status_code=302,
    )


@router.get("/auth/google/callback", name="google_oauth_callback")
def google_oauth_callback(
    request: Request,
    state: str,
    code: str,
):
    operator_settings = OperatorSettingsService()
    expected_state = operator_settings.get_google_oauth_state()
    if not expected_state or state != expected_state:
        raise HTTPException(status_code=400, detail="Google OAuth state did not match.")
    operator_settings.clear_google_oauth_state()

    oauth_settings = operator_settings.get_google_oauth_settings()
    client_id = str(oauth_settings["client_id"] or "").strip()
    client_secret = str(oauth_settings["client_secret"] or "").strip()
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Google OAuth settings are incomplete.")

    client = GoogleCalendarClient(
        GoogleOAuthConfig(
            account_label="Google",
            account_email="",
            client_id=client_id,
            client_secret=client_secret,
            refresh_token="placeholder",
            primary_calendar_id="primary",
            primary_calendar_name="Primary",
        )
    )
    redirect_uri = str(request.url_for("google_oauth_callback"))
    token_payload = client.exchange_code(code=code, redirect_uri=redirect_uri)
    refresh_token = str(token_payload["refresh_token"] or "").strip()
    if not refresh_token:
        raise HTTPException(
            status_code=400,
            detail="Google did not return a refresh token. Reconnect with consent again.",
        )
    access_token = str(token_payload["access_token"] or "").strip()
    account_email = client.current_user_email(access_token=access_token)
    calendar_catalog = client.list_calendars(access_token=access_token)
    operator_settings.upsert_google_account(
        account_label=account_email,
        account_email=account_email,
        refresh_token=refresh_token,
        calendars=calendar_catalog,
    )

    runtime_service = GoogleRuntimeConfigService(operator_settings=operator_settings)
    google_settings = operator_settings.describe_google_oauth_settings()
    runtime_config = runtime_service.resolve()
    return _templates.TemplateResponse(
        request,
        "google_setup.html",
        {
            "request": request,
            "google_settings": google_settings,
            "runtime_config": runtime_config,
            "google_accounts": runtime_service.list_accounts(),
            "calendar_catalog": runtime_service.list_calendars(),
            "flash_message": "Google account connected and calendars discovered.",
            "error_message": None,
            "connect_url": "/auth/google/start",
        },
    )


@router.get("/microsoft/setup")
def microsoft_setup_page(request: Request):
    operator_settings = OperatorSettingsService()
    microsoft_settings = operator_settings.describe_microsoft_oauth_settings()
    runtime_service = MicrosoftRuntimeConfigService(operator_settings=operator_settings)
    runtime_config = runtime_service.resolve()
    return _templates.TemplateResponse(
        request,
        "microsoft_setup.html",
        {
            "request": request,
            "microsoft_settings": microsoft_settings,
            "runtime_config": runtime_config,
            "microsoft_accounts": runtime_service.list_accounts(),
            "calendar_catalog": runtime_service.list_calendars(),
            "flash_message": None,
            "error_message": None,
            "connect_url": "/auth/microsoft/start",
        },
    )


@router.post("/microsoft/setup")
def microsoft_setup_update(
    request: Request,
    microsoft_client_id: str = Form(""),
    microsoft_client_secret: str = Form(""),
):
    operator_settings = OperatorSettingsService()
    try:
        operator_settings.set_microsoft_oauth_settings(
            client_id=microsoft_client_id,
            client_secret=microsoft_client_secret,
            preserve_existing_secret=True,
        )
        flash_message = "Microsoft OAuth settings saved securely."
        error_message = None
    except ValueError as exc:
        flash_message = None
        error_message = str(exc)

    microsoft_settings = operator_settings.describe_microsoft_oauth_settings()
    runtime_service = MicrosoftRuntimeConfigService(operator_settings=operator_settings)
    runtime_config = runtime_service.resolve()
    return _templates.TemplateResponse(
        request,
        "microsoft_setup.html",
        {
            "request": request,
            "microsoft_settings": microsoft_settings,
            "runtime_config": runtime_config,
            "microsoft_accounts": runtime_service.list_accounts(),
            "calendar_catalog": runtime_service.list_calendars(),
            "flash_message": flash_message,
            "error_message": error_message,
            "connect_url": "/auth/microsoft/start",
        },
        status_code=200 if error_message is None else 400,
    )


@router.post("/microsoft/setup/refresh")
def microsoft_setup_refresh(request: Request):
    operator_settings = OperatorSettingsService()
    requested_account_email = str((request.query_params.get("account_email") or "")).strip() or None
    try:
        client = _build_microsoft_client_from_settings(
            operator_settings,
            account_email=requested_account_email,
        )
        selected_runtime = MicrosoftRuntimeConfigService(
            operator_settings=operator_settings
        ).resolve(account_email=requested_account_email)
        account_email = client.current_user_email()
        calendar_catalog = client.list_calendars()
        previous_account_email = str(selected_runtime["account_email"] or "").strip()
        if previous_account_email and previous_account_email.lower() != account_email.lower():
            operator_settings.remove_microsoft_account(previous_account_email)
        operator_settings.upsert_microsoft_account(
            account_label=account_email,
            account_email=account_email,
            refresh_token=str(selected_runtime["refresh_token"] or ""),
            calendars=calendar_catalog,
        )
        flash_message = "Microsoft calendars refreshed from the live account."
        error_message = None
    except (MicrosoftCalendarError, ValueError) as exc:
        flash_message = None
        error_message = str(exc)

    microsoft_settings = operator_settings.describe_microsoft_oauth_settings()
    runtime_service = MicrosoftRuntimeConfigService(operator_settings=operator_settings)
    runtime_config = runtime_service.resolve()
    return _templates.TemplateResponse(
        request,
        "microsoft_setup.html",
        {
            "request": request,
            "microsoft_settings": microsoft_settings,
            "runtime_config": runtime_config,
            "microsoft_accounts": runtime_service.list_accounts(),
            "calendar_catalog": runtime_service.list_calendars(),
            "flash_message": flash_message,
            "error_message": error_message,
            "connect_url": "/auth/microsoft/start",
        },
        status_code=200 if error_message is None else 400,
    )


@router.post("/microsoft/setup/disconnect")
def microsoft_setup_disconnect(request: Request):
    operator_settings = OperatorSettingsService()
    operator_settings.clear_microsoft_oauth_state()
    account_email = str((request.query_params.get("account_email") or "")).strip() or None
    if account_email:
        operator_settings.remove_microsoft_account(account_email)
    else:
        operator_settings.clear_microsoft_account_settings()
        operator_settings.clear_microsoft_calendar_catalog()
    microsoft_settings = operator_settings.describe_microsoft_oauth_settings()
    runtime_service = MicrosoftRuntimeConfigService(operator_settings=operator_settings)
    runtime_config = runtime_service.resolve() if runtime_service.list_accounts() else {
        "account_label": "",
        "account_email": "",
        "refresh_token": "",
        "client_id": str(operator_settings.get_microsoft_oauth_settings()["client_id"] or ""),
        "client_secret": str(operator_settings.get_microsoft_oauth_settings()["client_secret"] or ""),
        "primary_calendar_id": "",
        "primary_calendar_name": "",
        "source": "product_vault" if microsoft_settings["client_id"] else "missing",
        "ready": False,
        "calendars": [],
        "accounts": [],
    }
    return _templates.TemplateResponse(
        request,
        "microsoft_setup.html",
        {
            "request": request,
            "microsoft_settings": microsoft_settings,
            "runtime_config": runtime_config,
            "microsoft_accounts": runtime_service.list_accounts(),
            "calendar_catalog": runtime_service.list_calendars(),
            "flash_message": "Microsoft account disconnected. The shared OAuth app is still saved.",
            "error_message": None,
            "connect_url": "/auth/microsoft/start",
        },
    )


@router.post("/microsoft/setup/test")
def microsoft_setup_run_write_test(
    request: Request,
    target_calendar_url: str = Form(""),
):
    service = AppointmentService()
    operator_settings = OperatorSettingsService()
    runtime_service = MicrosoftRuntimeConfigService(operator_settings=operator_settings)
    try:
        result = service.run_write_smoke_test(
            target_calendar_url=target_calendar_url,
            actor="console",
        )
        flash_message = _write_test_success_message(result)
        _record_write_test_verification(
            operator_settings,
            service,
            target_calendar_url=target_calendar_url,
            passed=True,
            message=flash_message,
            result=result,
        )
        error_message = None
    except (
        AppleCalDAVError,
        GoogleCalendarError,
        MicrosoftCalendarError,
        ValueError,
    ) as exc:
        flash_message = None
        error_message = str(exc)
        _record_write_test_verification(
            operator_settings,
            service,
            target_calendar_url=target_calendar_url,
            passed=False,
            message=error_message,
            result=None,
        )

    return _templates.TemplateResponse(
        request,
        "microsoft_setup.html",
        {
            "request": request,
            "microsoft_settings": operator_settings.describe_microsoft_oauth_settings(),
            "runtime_config": runtime_service.resolve(),
            "microsoft_accounts": runtime_service.list_accounts(),
            "calendar_catalog": runtime_service.list_calendars(),
            "flash_message": flash_message,
            "error_message": error_message,
            "connect_url": "/auth/microsoft/start",
        },
        status_code=200 if error_message is None else 400,
    )


@router.get("/auth/microsoft/start")
def microsoft_oauth_start(request: Request):
    operator_settings = OperatorSettingsService()
    oauth_settings = operator_settings.get_microsoft_oauth_settings()
    client_id = str(oauth_settings["client_id"] or "").strip()
    client_secret = str(oauth_settings["client_secret"] or "").strip()
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Microsoft OAuth settings are incomplete.")

    state = str(uuid4())
    operator_settings.set_microsoft_oauth_state(state)
    redirect_uri = str(request.url_for("microsoft_oauth_callback"))
    client = MicrosoftCalendarClient(
        MicrosoftOAuthConfig(
            account_label="Microsoft",
            account_email="",
            client_id=client_id,
            client_secret=client_secret,
            refresh_token="placeholder",
            primary_calendar_id="primary",
            primary_calendar_name="Primary",
        )
    )
    return RedirectResponse(
        client.authorization_url(redirect_uri=redirect_uri, state=state),
        status_code=302,
    )


@router.get("/auth/microsoft/callback", name="microsoft_oauth_callback")
def microsoft_oauth_callback(
    request: Request,
    state: str,
    code: str,
):
    operator_settings = OperatorSettingsService()
    expected_state = operator_settings.get_microsoft_oauth_state()
    if not expected_state or state != expected_state:
        raise HTTPException(status_code=400, detail="Microsoft OAuth state did not match.")
    operator_settings.clear_microsoft_oauth_state()

    oauth_settings = operator_settings.get_microsoft_oauth_settings()
    client_id = str(oauth_settings["client_id"] or "").strip()
    client_secret = str(oauth_settings["client_secret"] or "").strip()
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Microsoft OAuth settings are incomplete.")

    client = MicrosoftCalendarClient(
        MicrosoftOAuthConfig(
            account_label="Microsoft",
            account_email="",
            client_id=client_id,
            client_secret=client_secret,
            refresh_token="placeholder",
            primary_calendar_id="primary",
            primary_calendar_name="Primary",
        )
    )
    redirect_uri = str(request.url_for("microsoft_oauth_callback"))
    token_payload = client.exchange_code(code=code, redirect_uri=redirect_uri)
    refresh_token = str(token_payload["refresh_token"] or "").strip()
    if not refresh_token:
        raise HTTPException(
            status_code=400,
            detail="Microsoft did not return a refresh token. Reconnect with consent again.",
        )
    access_token = str(token_payload["access_token"] or "").strip()
    account_email = client.current_user_email(access_token=access_token)
    calendar_catalog = client.list_calendars(access_token=access_token)
    operator_settings.upsert_microsoft_account(
        account_label=account_email,
        account_email=account_email,
        refresh_token=refresh_token,
        calendars=calendar_catalog,
    )

    runtime_service = MicrosoftRuntimeConfigService(operator_settings=operator_settings)
    microsoft_settings = operator_settings.describe_microsoft_oauth_settings()
    runtime_config = runtime_service.resolve()
    return _templates.TemplateResponse(
        request,
        "microsoft_setup.html",
        {
            "request": request,
            "microsoft_settings": microsoft_settings,
            "runtime_config": runtime_config,
            "microsoft_accounts": runtime_service.list_accounts(),
            "calendar_catalog": runtime_service.list_calendars(),
            "flash_message": "Microsoft account connected and calendars discovered.",
            "error_message": None,
            "connect_url": "/auth/microsoft/start",
        },
    )


@router.post("/alexa/setup")
def alexa_setup_update(
    request: Request,
    allowed_skill_ids: str = Form(""),
    enable_alexa: str | None = Form(None),
):
    readiness = ReadinessService().build()
    service = CloudflareWorkerConfigService()
    try:
        edge_settings = service.update_alexa_settings(
            enable_alexa=enable_alexa == "true",
            allowed_skill_ids=[
                value.strip() for value in allowed_skill_ids.split(",") if value.strip()
            ],
        )
        flash_message = "Edge Worker settings updated."
        error_message = None
    except ValueError as exc:
        edge_settings = service.get_alexa_settings()
        flash_message = None
        error_message = str(exc)

    cloudflare_credentials = OperatorSettingsService().describe_cloudflare_worker_credentials()
    return _templates.TemplateResponse(
        request,
        "alexa_setup.html",
        {
            "request": request,
            "readiness": readiness,
            "edge_settings": edge_settings,
            "cloudflare_credentials": cloudflare_credentials,
            "alexa_endpoint": "https://edge-calsync.neonbutterfly.net/alexa",
            "privacy_url": "https://calsync.neonbutterfly.net/privacy",
            "terms_url": "https://calsync.neonbutterfly.net/terms",
            "simulator_url": "/alexa/simulator",
            "flash_message": flash_message,
            "error_message": error_message,
        },
        status_code=200 if error_message is None else 400,
    )


@router.post("/alexa/setup/cloudflare")
def alexa_setup_update_cloudflare_credentials(
    request: Request,
    cloudflare_account_id: str = Form(""),
    cloudflare_api_token: str = Form(""),
):
    readiness = ReadinessService().build()
    operator_settings = OperatorSettingsService()
    try:
        operator_settings.set_cloudflare_worker_credentials(
            account_id=cloudflare_account_id,
            api_token=cloudflare_api_token,
            preserve_existing_token=True,
        )
        flash_message = "Cloudflare Worker credentials saved securely."
        error_message = None
    except ValueError as exc:
        flash_message = None
        error_message = str(exc)

    edge_settings = CloudflareWorkerConfigService().get_alexa_settings()
    cloudflare_credentials = operator_settings.describe_cloudflare_worker_credentials()
    return _templates.TemplateResponse(
        request,
        "alexa_setup.html",
        {
            "request": request,
            "readiness": readiness,
            "edge_settings": edge_settings,
            "cloudflare_credentials": cloudflare_credentials,
            "alexa_endpoint": "https://edge-calsync.neonbutterfly.net/alexa",
            "privacy_url": "https://calsync.neonbutterfly.net/privacy",
            "terms_url": "https://calsync.neonbutterfly.net/terms",
            "simulator_url": "/alexa/simulator",
            "flash_message": flash_message,
            "error_message": error_message,
        },
        status_code=200 if error_message is None else 400,
    )


@router.get("/alexa/simulator")
def alexa_simulator_page(request: Request):
    service = AppointmentService()
    return _templates.TemplateResponse(
        request,
        "alexa_simulator.html",
        {
            "request": request,
            "simulation_result": None,
            "error_message": None,
            "form_values": _default_alexa_simulator_values(),
            "calendar_name_options": _calendar_name_options(service),
        },
    )


@router.post("/alexa/simulator")
def alexa_simulator_run(
    request: Request,
    request_type: str = Form(...),
    intent_name: str = Form(""),
    title: str = Form(""),
    date: str = Form(""),
    start_time: str = Form(""),
    end_time: str = Form(""),
    location: str = Form(""),
    notes: str = Form(""),
    calendar_name: str = Form(""),
    duration_minutes: str = Form(""),
    end_date: str = Form(""),
    new_date: str = Form(""),
    new_start_time: str = Form(""),
    new_end_time: str = Form(""),
    new_calendar_name: str = Form(""),
):
    form_values = {
        "request_type": request_type,
        "intent_name": intent_name,
        "title": title,
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "location": location,
        "notes": notes,
        "calendar_name": calendar_name,
        "duration_minutes": duration_minutes,
        "end_date": end_date,
        "new_date": new_date,
        "new_start_time": new_start_time,
        "new_end_time": new_end_time,
        "new_calendar_name": new_calendar_name,
    }
    slots = {
        "title": title,
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "location": location,
        "notes": notes,
        "calendar_name": calendar_name,
        "duration_minutes": duration_minutes,
        "end_date": end_date,
        "new_date": new_date,
        "new_start_time": new_start_time,
        "new_end_time": new_end_time,
        "new_calendar_name": new_calendar_name,
    }
    try:
        simulation_result = AlexaSimulatorService().simulate(
            request_type=request_type,
            intent_name=intent_name or None,
            slots=slots,
        )
        error_message = None
    except ValueError as exc:
        simulation_result = None
        error_message = str(exc)

    return _templates.TemplateResponse(
        request,
        "alexa_simulator.html",
        {
            "request": request,
            "simulation_result": simulation_result,
            "error_message": error_message,
            "form_values": form_values,
            "calendar_name_options": _calendar_name_options(
                AppointmentService()
            ),
        },
        status_code=200 if simulation_result is not None else 400,
    )


@router.get("/alexa/skill-package.zip")
def alexa_skill_package_zip() -> StreamingResponse:
    package_root = files("calsync.alexa_setup")
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, "w") as archive:
        archive.writestr(
            "skill-package/skill.json",
            (package_root / "skill-package" / "skill.json").read_text(encoding="utf-8"),
        )
        archive.writestr(
            "skill-package/interactionModels/custom/en-US.json",
            (
                package_root
                / "skill-package"
                / "interactionModels"
                / "custom"
                / "en-US.json"
            ).read_text(encoding="utf-8"),
        )
    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="calsync-alexa-skill-package.zip"'
        },
    )


@router.get("/")
def scheduling_console(
    request: Request,
    created: str | None = None,
    updated: str | None = None,
    cancelled: str | None = None,
    view: str = "week",
    appointment_id: str | None = None,
    show_cancelled: bool = False,
    availability_date_from: str | None = None,
    availability_date_to: str | None = None,
    availability_duration_minutes: int = 60,
):
    service = AppointmentService()
    readiness = ReadinessService().build()
    date_from, date_to, selected_window = _resolve_window(view)
    try:
        appointments = service.list_range(
            date_from=date_from.isoformat(),
            date_to=date_to.isoformat(),
            include_cancelled=show_cancelled,
        ).items
        selected_detail = _resolve_selected_detail(service, appointments, appointment_id)
        schedule_error = None
    except (
        AppleCalDAVError,
        GoogleCalendarError,
        ModuleNotFoundError,
        SQLAlchemyError,
        ValueError,
    ):
        appointments = []
        selected_detail = None
        schedule_error = "Schedule data is unavailable right now."
    availability_form_values = _default_availability_form_values()
    if availability_date_from:
        availability_form_values["date_from"] = availability_date_from
    if availability_date_to:
        availability_form_values["date_to"] = availability_date_to
    availability_form_values["duration_minutes"] = availability_duration_minutes
    availability_results: list[AvailabilitySlot] = []
    availability_error: str | None = None
    availability_searched = bool(availability_date_from or availability_date_to)
    if availability_searched:
        try:
            availability_results = service.find_availability(
                date_from=str(availability_form_values["date_from"]),
                date_to=str(availability_form_values["date_to"]),
                duration_minutes=availability_duration_minutes,
            ).items
        except (AppleCalDAVError, GoogleCalendarError, ValueError) as exc:
            availability_error = str(exc)
    return _templates.TemplateResponse(
        request,
        "console.html",
        _build_console_context(
            request,
            service=service,
            appointments=appointments,
            selected_detail=selected_detail,
            flash_message=_flash_message(created, updated, cancelled),
            error_message=schedule_error,
            form_values=_empty_form_values(),
            availability_form_values=availability_form_values,
            availability_results=availability_results,
            availability_error=availability_error,
            availability_searched=availability_searched,
            selected_window=selected_window,
            show_cancelled=show_cancelled,
            readiness=readiness,
        ),
    )


@router.post("/appointments")
def create_appointment_from_console(
    request: Request,
    title: str = Form(...),
    date_value: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    timezone: str = Form(...),
    location: str = Form(""),
    notes: str = Form(""),
    attendees_text: str = Form(""),
    target_calendar_url: str = Form(""),
    all_day: bool = Form(False),
):
    payload = CreateAppointmentRequest(
        title=title,
        date=date_value,
        start_time=start_time,
        end_time=end_time,
        timezone=timezone,
        location=location or None,
        notes=notes or None,
        attendees_text=attendees_text or None,
        target_calendar_url=target_calendar_url or None,
        all_day=all_day,
    )
    service = AppointmentService()
    try:
        created = service.create(payload, actor="console")
        return RedirectResponse(
            url=f"/?created=1&view=week&appointment_id={created.appointment_id}",
            status_code=303,
        )
    except (AppleCalDAVError, GoogleCalendarError, ValueError) as exc:
        date_from, date_to, selected_window = _resolve_window("week")
        appointments = service.list_range(
            date_from=date_from.isoformat(),
            date_to=date_to.isoformat(),
        ).items
        selected_detail = _resolve_selected_detail(service, appointments, None)
        return _templates.TemplateResponse(
            request,
            "console.html",
            _build_console_context(
                request,
                service=service,
                appointments=appointments,
                selected_detail=selected_detail,
                flash_message=None,
                error_message=str(exc),
                form_values={
                    "title": title,
                    "date": date_value,
                    "start_time": start_time,
                    "end_time": end_time,
                    "timezone": timezone,
                    "location": location,
                    "notes": notes,
                    "attendees_text": attendees_text,
                    "target_calendar_url": target_calendar_url,
                    "all_day": all_day,
                },
                availability_form_values=_default_availability_form_values(),
                availability_results=[],
                availability_error=None,
                availability_searched=False,
                selected_window=selected_window,
                show_cancelled=False,
                readiness=ReadinessService().build(),
            ),
            status_code=400,
        )


@router.get("/appointments/{appointment_id}/edit")
def edit_appointment_page(appointment_id: str, request: Request):
    service = AppointmentService()
    try:
        appointment = service.get_detail(appointment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _templates.TemplateResponse(
        request,
        "appointment_edit.html",
        {
            "request": request,
            "appointment": appointment,
            "form_values": {
                "title": appointment.title,
                "date": appointment.date,
                "start_time": appointment.start_time,
                "end_time": appointment.end_time,
                "timezone": appointment.timezone,
                "location": appointment.location or "",
                "notes": appointment.notes or "",
                "attendees_text": appointment.attendees_text or "",
                "target_calendar_url": appointment.calendar_url or "",
                "all_day": appointment.all_day,
            },
            "calendar_options": _calendar_options(
                service,
                selected_calendar_url=appointment.calendar_url,
            ),
            "error_message": None,
            "window_options": _window_options(
                selected_window="week",
                show_cancelled=False,
                selected_appointment_id=appointment_id,
            ),
        },
    )


@router.post("/appointments/{appointment_id}/edit")
def edit_appointment_from_console(
    appointment_id: str,
    request: Request,
    title: str = Form(...),
    date_value: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    timezone: str = Form(...),
    location: str = Form(""),
    notes: str = Form(""),
    attendees_text: str = Form(""),
    target_calendar_url: str = Form(""),
    all_day: bool = Form(False),
):
    payload = UpdateAppointmentRequest(
        title=title,
        date=date_value,
        start_time=start_time,
        end_time=end_time,
        timezone=timezone,
        location=location or None,
        notes=notes or None,
        attendees_text=attendees_text or None,
        target_calendar_url=target_calendar_url or None,
        all_day=all_day,
    )
    service = AppointmentService()
    try:
        service.update(appointment_id, payload, actor="console")
        return RedirectResponse(
            url=f"/?updated=1&view=week&appointment_id={appointment_id}",
            status_code=303,
        )
    except ValueError as exc:
        if "not found" in str(exc).lower():
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        appointment = service.get(appointment_id)
        return _templates.TemplateResponse(
            request,
            "appointment_edit.html",
            {
                "request": request,
                "appointment": appointment,
                "form_values": {
                    "title": title,
                    "date": date_value,
                    "start_time": start_time,
                    "end_time": end_time,
                    "timezone": timezone,
                    "location": location,
                    "notes": notes,
                    "attendees_text": attendees_text,
                    "target_calendar_url": target_calendar_url,
                    "all_day": all_day,
                },
                "calendar_options": _calendar_options(
                    service,
                    selected_calendar_url=target_calendar_url or None,
                ),
                "error_message": str(exc),
                "window_options": _window_options(
                    selected_window="week",
                    show_cancelled=False,
                    selected_appointment_id=appointment_id,
                ),
            },
            status_code=400,
        )
    except (AppleCalDAVError, GoogleCalendarError) as exc:
        appointment = service.get(appointment_id)
        return _templates.TemplateResponse(
            request,
            "appointment_edit.html",
            {
                "request": request,
                "appointment": appointment,
                "form_values": {
                    "title": title,
                    "date": date_value,
                    "start_time": start_time,
                    "end_time": end_time,
                    "timezone": timezone,
                    "location": location,
                    "notes": notes,
                    "attendees_text": attendees_text,
                    "target_calendar_url": target_calendar_url,
                    "all_day": all_day,
                },
                "calendar_options": _calendar_options(
                    service,
                    selected_calendar_url=target_calendar_url or None,
                ),
                "error_message": str(exc),
                "window_options": _window_options(
                    selected_window="week",
                    show_cancelled=False,
                    selected_appointment_id=appointment_id,
                ),
            },
            status_code=400,
        )


@router.post("/appointments/{appointment_id}/cancel")
def cancel_appointment_from_console(appointment_id: str):
    service = AppointmentService()
    try:
        service.cancel(appointment_id, actor="console")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (AppleCalDAVError, GoogleCalendarError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url="/?cancelled=1&view=week", status_code=303)


def _today_in_alaska() -> date:
    return datetime.now(UTC).astimezone(ZoneInfo("America/Anchorage")).date()


def _resolve_window(view: str) -> tuple[date, date, str]:
    selected_window = view if view in _WINDOWS else "week"
    label, day_span = _WINDOWS[selected_window]
    del label
    start = _today_in_alaska()
    return start, start + timedelta(days=day_span), selected_window


def _resolve_selected_detail(
    service: AppointmentService,
    appointments: list[AppointmentListItem],
    appointment_id: str | None,
) -> AppointmentDetailResponse | None:
    selected_appointment_id = appointment_id or (appointments[0].appointment_id if appointments else None)
    if not selected_appointment_id:
        return None
    try:
        return service.get_detail(selected_appointment_id)
    except ValueError:
        return None


def _build_console_context(
    request: Request,
    *,
    service: AppointmentService,
    appointments: list[AppointmentListItem],
    selected_detail: AppointmentDetailResponse | None,
    flash_message: str | None,
    error_message: str | None,
    form_values: dict[str, object],
    availability_form_values: dict[str, object],
    availability_results: list[AvailabilitySlot],
    availability_error: str | None,
    availability_searched: bool,
    selected_window: str,
    show_cancelled: bool,
    readiness: dict[str, object],
) -> dict[str, object]:
    hero_subject = appointments[0] if appointments else None
    return {
        "request": request,
        "flash_message": flash_message,
        "error_message": error_message,
        "reference_message": (
            "Showing cancelled appointments for reference."
            if show_cancelled
            else None
        ),
        "form_values": form_values,
        "availability_form_values": availability_form_values,
        "availability_results": _serialize_availability_results(availability_results),
        "availability_error": availability_error,
        "availability_searched": availability_searched,
        "calendar_label": service.display_calendar_name,
        "account_label": service.display_account_label,
        "calendar_options": _calendar_options(
            service,
            selected_calendar_url=str(form_values.get("target_calendar_url") or ""),
        ),
        "selected_window": selected_window,
        "show_cancelled": show_cancelled,
        "window_options": _window_options(
            selected_window=selected_window,
            show_cancelled=show_cancelled,
            selected_appointment_id=selected_detail.appointment_id if selected_detail else None,
        ),
        "window_label": _WINDOWS[selected_window][0],
        "window_summary": _window_summary(selected_window),
        "schedule_sections": _build_schedule_sections(
            appointments,
            selected_window=selected_window,
            show_cancelled=show_cancelled,
            selected_appointment_id=selected_detail.appointment_id if selected_detail else None,
        ),
        "selected_appointment": _serialize_detail(selected_detail),
        "appointment_count": len(appointments),
        "active_count": len(appointments),
        "cancelled_count": sum(1 for item in appointments if item.status == "cancelled"),
        "next_up_label": _next_up_label(hero_subject),
        "readiness": readiness,
    }


def _build_schedule_sections(
    appointments: list[AppointmentListItem],
    *,
    selected_window: str,
    show_cancelled: bool,
    selected_appointment_id: str | None,
) -> list[dict[str, object]]:
    sections: list[dict[str, object]] = []
    grouped: dict[str, list[AppointmentListItem]] = {}
    for item in appointments:
        grouped.setdefault(item.date, []).append(item)

    for day, items in grouped.items():
        sections.append(
            {
                "date_label": _friendly_date_label(day),
                "eyebrow": _schedule_eyebrow(day),
                "entries": [
                    {
                        "appointment_id": item.appointment_id,
                        "title": item.title,
                        "status": item.status,
                        "time_label": _time_label(item),
                        "people_label": item.attendees_text,
                        "location_label": item.location,
                        "detail_href": _detail_href(
                            selected_window=selected_window,
                            appointment_id=item.appointment_id,
                            show_cancelled=show_cancelled,
                        ),
                        "is_selected": item.appointment_id == selected_appointment_id,
                    }
                    for item in items
                ],
            }
        )
    return sections


def _serialize_detail(detail: AppointmentDetailResponse | None) -> dict[str, object] | None:
    if detail is None:
        return None
    return {
        "appointment_id": detail.appointment_id,
        "title": detail.title,
        "status": detail.status,
        "date_label": _friendly_date_label(detail.date, include_weekday=True),
        "time_label": _time_label(detail),
        "timezone": detail.timezone,
        "location": detail.location,
        "notes": detail.notes,
        "attendees_text": detail.attendees_text,
        "calendar_name": detail.calendar_name,
        "account_label": detail.account_label,
        "provider_type_label": _provider_label(detail.provider_type),
        "provider_event_id": detail.provider_event_id,
        "provider_href": detail.provider_href,
        "created_label": _friendly_timestamp(detail.created_at),
        "updated_label": _friendly_timestamp(detail.updated_at),
        "audit_entries": [
            {
                "timestamp_label": _friendly_timestamp(item.created_at),
                "actor_label": _actor_label(item.actor),
                "action_label": _action_label(item.action),
                "summary": _audit_summary(item.action, item.payload_json),
            }
            for item in detail.audit_entries
        ],
    }


def _next_up_label(item: AppointmentListItem | None) -> str:
    if item is None:
        return "No appointments in this window yet."
    return f"{item.title} · {_friendly_date_label(item.date, include_weekday=True)} · {_time_label(item)}"


def _window_summary(selected_window: str) -> str:
    if selected_window == "day":
        return "Today only, so you can sanity-check the immediate family schedule."
    if selected_window == "month":
        return "The next 30 days, for a fuller planning view without falling into raw provider clutter."
    return "The next 7 days, for a useful planning horizon that still feels lightweight."


def _window_options(
    *,
    selected_window: str,
    show_cancelled: bool,
    selected_appointment_id: str | None,
) -> list[dict[str, object]]:
    options: list[dict[str, object]] = []
    for value, (label, _) in _WINDOWS.items():
        href = f"/?view={value}"
        if show_cancelled:
            href = f"{href}&show_cancelled=1"
        if selected_appointment_id:
            href = f"{href}&appointment_id={selected_appointment_id}"
        options.append(
            {
                "label": label,
                "href": href,
                "is_active": value == selected_window,
            }
        )
    return options


def _detail_href(
    *,
    selected_window: str,
    appointment_id: str,
    show_cancelled: bool,
) -> str:
    href = f"/?view={selected_window}&appointment_id={appointment_id}"
    if show_cancelled:
        href = f"{href}&show_cancelled=1"
    return href


def _friendly_date_label(day: str, *, include_weekday: bool = False) -> str:
    parsed = date.fromisoformat(day)
    current_year = _today_in_alaska().year
    month_day = parsed.strftime("%b %d").replace(" 0", " ")
    if include_weekday:
        weekday = parsed.strftime("%A")
        base = f"{weekday}, {month_day}"
    else:
        base = month_day
    if parsed.year != current_year:
        return f"{base}, {parsed.year}"
    return base


def _schedule_eyebrow(day: str) -> str:
    parsed = date.fromisoformat(day)
    today = _today_in_alaska()
    if parsed == today:
        return "Today"
    if parsed == today + timedelta(days=1):
        return "Tomorrow"
    return parsed.strftime("%A").upper()


def _time_label(item: AppointmentListItem | AppointmentDetailResponse) -> str:
    if item.all_day:
        return "All day"
    start = _to_12_hour(item.start_time)
    end = _to_12_hour(item.end_time)
    return f"{start} - {end}"


def _to_12_hour(value: str) -> str:
    parsed = datetime.strptime(value, "%H:%M")
    return parsed.strftime("%I:%M %p").lstrip("0")


def _friendly_timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    timezone = ZoneInfo(parsed.tzinfo.key if parsed.tzinfo and hasattr(parsed.tzinfo, "key") else "America/Anchorage")
    localized = parsed.astimezone(timezone)
    month_day = localized.strftime("%b %d").replace(" 0", " ")
    return f"{month_day}, {localized.year} at {localized.strftime('%I:%M %p').lstrip('0')} {localized.tzname()}"


def _provider_label(provider_type: str) -> str:
    if provider_type == "icloud_caldav":
        return "Apple Calendar"
    if provider_type == "google_calendar":
        return "Google Calendar"
    if provider_type == "microsoft_calendar":
        return "Microsoft Calendar"
    return provider_type.replace("_", " ").title()


def _write_test_success_message(result: dict[str, str]) -> str:
    return (
        f"Write test passed for {result['calendar_name']} on "
        f"{result['provider_label']}"
        + (f" ({result['account_label']})" if result["account_label"] else "")
        + "."
    )


def _record_write_test_verification(
    operator_settings: OperatorSettingsService,
    service: AppointmentService,
    *,
    target_calendar_url: str,
    passed: bool,
    message: str,
    result: dict[str, str] | None,
) -> None:
    try:
        described_target = service.describe_target_calendar(target_calendar_url)
        target = {
            "provider_type": str(
                (result or {}).get("provider_type")
                or described_target["provider_type"]
            ),
            "provider_label": str(
                (result or {}).get("provider_label")
                or described_target["provider_label"]
            ),
            "account_label": str(
                (result or {}).get("account_label")
                or described_target.get("account_label")
                or ""
            ),
            "calendar_name": str(
                (result or {}).get("calendar_name")
                or described_target["calendar_name"]
            ),
            "target_value": str(
                (result or {}).get("target_value")
                or target_calendar_url
            ),
        }
        operator_settings.record_calendar_write_verification(
            target_value=target["target_value"],
            provider_type=str(target["provider_type"]),
            provider_label=str(target["provider_label"]),
            account_label=str(target.get("account_label") or ""),
            calendar_name=str(target["calendar_name"]),
            passed=passed,
            message=message,
            checked_at=datetime.now(UTC).isoformat(),
        )
    except ValueError:
        return


def _build_connections_context(
    request: Request,
    *,
    flash_message: str | None,
    error_message: str | None,
) -> dict[str, object]:
    operator_settings = OperatorSettingsService()
    apple_runtime_service = AppleRuntimeConfigService(operator_settings=operator_settings)
    google_runtime_service = GoogleRuntimeConfigService(operator_settings=operator_settings)
    microsoft_runtime_service = MicrosoftRuntimeConfigService(operator_settings=operator_settings)
    apple_settings = operator_settings.describe_apple_calendar_settings()
    google_settings = operator_settings.describe_google_oauth_settings()
    microsoft_settings = operator_settings.describe_microsoft_oauth_settings()
    apple_runtime = apple_runtime_service.resolve()
    google_runtime = google_runtime_service.resolve()
    microsoft_runtime = microsoft_runtime_service.resolve()
    readiness = ReadinessService().build()
    verification_map = {
        str(item["target_value"]): item
        for item in operator_settings.get_calendar_write_verifications()
    }
    apple_targets = _decorate_connection_targets(
        apple_runtime_service.list_calendars(),
        provider_type="apple",
        verification_map=verification_map,
    )
    google_targets = _decorate_connection_targets(
        google_runtime_service.list_calendars(),
        provider_type="google",
        verification_map=verification_map,
    )
    microsoft_targets = _decorate_connection_targets(
        microsoft_runtime_service.list_calendars(),
        provider_type="microsoft",
        verification_map=verification_map,
    )
    verification_targets = [
        *apple_targets,
        *google_targets,
        *microsoft_targets,
    ]
    passed_verifications = [
        item for item in verification_targets if item["verification_status"] == "passed"
    ]
    failed_verifications = [
        item for item in verification_targets if item["verification_status"] == "failed"
    ]
    setup_checklist = [
        {
            "label": "Apple calendar path",
            "status_label": "Ready" if apple_runtime["ready"] else "Needs setup",
            "detail": (
                "Apple credentials and a writable target are available."
                if apple_runtime["ready"]
                else "Save the household Apple connection to unlock the first live calendar path."
            ),
        },
        {
            "label": "Google calendar path",
            "status_label": "Ready" if google_runtime["ready"] else "Needs setup",
            "detail": (
                "Google OAuth, account connect, and at least one writable target are ready."
                if google_runtime["ready"]
                else "Save the shared Google OAuth app and connect a browser-approved account."
            ),
        },
        {
            "label": "Microsoft calendar path",
            "status_label": "Ready" if microsoft_runtime["ready"] else "Needs setup",
            "detail": (
                "Microsoft OAuth, account connect, and at least one writable target are ready."
                if microsoft_runtime["ready"]
                else "Save the shared Microsoft OAuth app and connect an Outlook account."
            ),
        },
        {
            "label": "Alexa edge route",
            "status_label": (
                "Ready"
                if readiness.get("edge", {}).get("reachable")
                and readiness.get("edge", {}).get("alexa", {}).get("enabled")
                else "Needs setup"
            ),
            "detail": (
                "The edge Worker can accept Alexa traffic."
                if readiness.get("edge", {}).get("reachable")
                and readiness.get("edge", {}).get("alexa", {}).get("enabled")
                else "Finish edge enablement and skill allowlisting before real device traffic is live."
            ),
        },
    ]
    return {
        "request": request,
        "apple_settings": apple_settings,
        "apple_runtime": apple_runtime,
        "apple_accounts": apple_runtime_service.list_accounts(),
        "apple_calendar_catalog": apple_runtime_service.list_calendars(),
        "google_settings": google_settings,
        "google_runtime": google_runtime,
        "google_accounts": google_runtime_service.list_accounts(),
        "google_calendar_catalog": google_runtime_service.list_calendars(),
        "microsoft_settings": microsoft_settings,
        "microsoft_runtime": microsoft_runtime,
        "microsoft_accounts": microsoft_runtime_service.list_accounts(),
        "microsoft_calendar_catalog": microsoft_runtime_service.list_calendars(),
        "readiness": readiness,
        "flash_message": flash_message,
        "error_message": error_message,
        "setup_checklist": setup_checklist,
        "apple_targets": apple_targets,
        "google_targets": google_targets,
        "microsoft_targets": microsoft_targets,
        "verification_targets": verification_targets,
        "passed_verification_count": len(passed_verifications),
        "failed_verification_count": len(failed_verifications),
        "verified_target_count": len(
            [item for item in verification_targets if item["verification_status"] != "unverified"]
        ),
    }


def _decorate_connection_targets(
    targets: list[dict[str, object]],
    *,
    provider_type: str,
    verification_map: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    decorated: list[dict[str, object]] = []
    for item in targets:
        target_value = str(
            item.get("target_value")
            or item.get("calendar_url")
            or item.get("calendar_id")
            or ""
        )
        verification = verification_map.get(target_value)
        verification_status = (
            str(verification["status"]) if verification is not None else "unverified"
        )
        decorated.append(
            {
                "provider_type": provider_type,
                "provider_label": _provider_label(
                    {
                        "apple": "icloud_caldav",
                        "google": "google_calendar",
                        "microsoft": "microsoft_calendar",
                    }[provider_type]
                ),
                "target_value": target_value,
                "calendar_name": str(item.get("calendar_name") or ""),
                "account_label": str(
                    item.get("account_label")
                    or item.get("username")
                    or item.get("account_email")
                    or ""
                ),
                "is_default": bool(item.get("is_default")),
                "verification_status": verification_status,
                "verification_status_label": {
                    "passed": "Verified",
                    "failed": "Needs attention",
                    "unverified": "Not yet verified",
                }[verification_status],
                "verification_message": (
                    str(verification["message"])
                    if verification is not None
                    else "Run the in-product write test to prove this path can create, update, and cancel safely."
                ),
                "verification_checked_at_label": (
                    _friendly_timestamp(str(verification["checked_at"]))
                    if verification is not None
                    else ""
                ),
            }
        )
    return decorated


def _actor_label(actor: str) -> str:
    if actor == "console":
        return "CalSync workspace"
    if actor == "api":
        return "CalSync API"
    if actor.startswith("worker:"):
        channel = actor.split(":", 1)[1]
        if channel == "chatgpt":
            return "ChatGPT"
        if channel == "shortcuts":
            return "Apple Shortcuts"
        if channel == "alexa":
            return "Alexa"
        return f"Worker {channel}"
    return actor.replace("_", " ").title()


def _action_label(action: str) -> str:
    if action == "create_appointment":
        return "Created appointment"
    if action == "update_appointment":
        return "Updated appointment"
    if action == "cancel_appointment":
        return "Cancelled appointment"
    return action.replace("_", " ").title()


def _audit_summary(action: str, payload_json: dict[str, object] | None) -> str:
    payload = payload_json or {}
    if action == "create_appointment":
        title = payload.get("title")
        if isinstance(title, str) and title:
            return f"Created with the title “{title}”."
        return "Created in CalSync and written to the connected calendar."
    if action == "update_appointment":
        changed_fields = []
        for key in ("title", "date", "start_time", "end_time", "location", "notes"):
            if key in payload:
                changed_fields.append(key.replace("_", " "))
        if changed_fields:
            readable = ", ".join(changed_fields)
            return f"Updated {readable} and synced the same connected calendar event."
        return "Updated this appointment and synced the same connected calendar event."
    if action == "cancel_appointment":
        return "Cancelled in CalSync and removed from the connected calendar."
    return "Recorded activity for this appointment."


def _flash_message(
    created: str | None,
    updated: str | None,
    cancelled: str | None,
) -> str | None:
    if created:
        return "Appointment created on the connected calendar."
    if updated:
        return "Appointment updated on the connected calendar."
    if cancelled:
        return "Appointment cancelled on the connected calendar."
    return None


def _empty_form_values() -> dict[str, object]:
    next_day = _today_in_alaska() + timedelta(days=1)
    return {
        "title": "",
        "date": next_day.isoformat(),
        "start_time": "10:00",
        "end_time": "11:00",
        "timezone": "America/Anchorage",
        "location": "",
        "notes": "",
        "attendees_text": "",
        "target_calendar_url": "",
        "all_day": False,
    }


def _default_availability_form_values() -> dict[str, object]:
    start = _today_in_alaska()
    return {
        "date_from": start.isoformat(),
        "date_to": (start + timedelta(days=6)).isoformat(),
        "duration_minutes": 60,
    }


def _serialize_availability_results(
    items: list[AvailabilitySlot],
) -> list[dict[str, str]]:
    return [
        {
            "date_label": _friendly_date_label(item.date, include_weekday=True),
            "time_label": f"{_to_12_hour(item.start_time)} - {_to_12_hour(item.end_time)}",
            "timezone": item.timezone,
        }
        for item in items
    ]


def _calendar_options(
    service: AppointmentService,
    *,
    selected_calendar_url: str | None,
) -> list[dict[str, object]]:
    selected_value = selected_calendar_url or ""
    options: list[dict[str, object]] = []
    for item in service.available_calendars:
        calendar_url = str(item["calendar_url"])
        account_label = str(item.get("account_label") or "").strip()
        provider_type = str(item.get("provider_type") or "").strip()
        provider_label = _provider_label(provider_type) if provider_type else ""
        label_parts = [str(item["calendar_name"])]
        if provider_label:
            label_parts.append(provider_label)
        if account_label:
            label_parts.append(account_label)
        options.append(
            {
                "label": " · ".join(label_parts),
                "value": calendar_url,
                "is_selected": calendar_url == selected_value
                or (not selected_value and bool(item.get("is_default"))),
            }
        )
    return options


def _default_alexa_simulator_values() -> dict[str, str]:
    next_day = _today_in_alaska() + timedelta(days=1)
    return {
        "request_type": "IntentRequest",
        "intent_name": "CreateAppointmentIntent",
        "title": "",
        "date": next_day.isoformat(),
        "start_time": "10:00",
        "end_time": "11:00",
        "location": "",
        "notes": "",
        "calendar_name": "",
        "duration_minutes": "60",
        "end_date": next_day.isoformat(),
        "new_date": next_day.isoformat(),
        "new_start_time": "13:00",
        "new_end_time": "14:00",
        "new_calendar_name": "",
    }


def _calendar_name_options(
    service: AppointmentService,
) -> list[dict[str, str]]:
    return service.calendar_name_targets
