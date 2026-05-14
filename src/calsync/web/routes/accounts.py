from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from calsync.config import validate_google_callback_url
from calsync.crypto import encrypt_text
from calsync.models import AdminUser, ProviderAccount
from calsync.repos.providers import upsert_provider_account
from calsync.services.app_settings import build_google_callback_url
from calsync.services.provider_config import get_google_provider_configuration_snapshot
from calsync.services.providers.icloud import ICloudCalDAVError
from calsync.services.sync import sync_account
from calsync.web.deps import (
    get_db,
    get_encryption_key,
    get_templates,
    require_admin,
)


router = APIRouter(prefix="/admin/accounts")


@router.get("")
def accounts_page(
    request: Request,
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
):
    return _render_accounts_page(
        request,
        session,
        templates,
        current_admin=current_admin,
    )


@router.post("/mock/connect")
def connect_mock_account(
    request: Request,
    session: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    existing_mock_count = session.query(ProviderAccount).filter(
        ProviderAccount.provider_type == "mock"
    ).count()
    account_number = existing_mock_count + 1
    account = ProviderAccount(
        provider_type="mock",
        provider_account_id=f"mock-acct-{account_number}",
        display_name=f"Mock Account {account_number}",
        provider_metadata={"source": "accounts-connect"},
    )
    session.add(account)
    session.flush()
    sync_account(
        session,
        account.id,
        trigger="manual",
        settings=request.app.state.settings,
    )
    session.commit()
    return RedirectResponse(url="/admin/accounts", status_code=303)


@router.post("/icloud/connect")
def connect_icloud_account(
    request: Request,
    label: str = Form(""),
    username: str = Form(...),
    app_password: str = Form(...),
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
    encryption_key: str = Depends(get_encryption_key),
):
    normalized_username = username.strip().lower()
    normalized_password = app_password.strip()
    normalized_label = label.strip()

    if not normalized_username:
        return _render_accounts_page(
            request,
            session,
            templates,
            current_admin=current_admin,
            error_message="Apple ID username or email is required.",
            status_code=400,
        )
    if not normalized_password:
        return _render_accounts_page(
            request,
            session,
            templates,
            current_admin=current_admin,
            error_message="Apple app-specific password is required.",
            status_code=400,
        )

    account = upsert_provider_account(
        session,
        provider_type="icloud_caldav",
        provider_account_id=normalized_username,
        display_name=normalized_label or normalized_username,
        provider_metadata={
            "auth_status": "pending",
            "last_auth_error": None,
        },
    )
    account.credential_secret_encrypted = encrypt_text(
        encryption_key,
        normalized_password,
    )
    session.add(account)
    session.flush()

    try:
        sync_account(
            session,
            account.id,
            trigger="manual",
            settings=request.app.state.settings,
        )
    except ICloudCalDAVError as exc:
        metadata = dict(account.provider_metadata or {})
        metadata["auth_status"] = "error"
        metadata["last_auth_error"] = str(exc)
        account.provider_metadata = metadata
        session.add(account)
        session.commit()
        return _render_accounts_page(
            request,
            session,
            templates,
            current_admin=current_admin,
            error_message=str(exc),
            status_code=400,
        )

    session.commit()
    return RedirectResponse(url="/admin/calendars", status_code=303)


def render_accounts_page_with_error(
    request: Request,
    session: Session,
    templates: Jinja2Templates,
    *,
    current_admin: AdminUser,
    error_message: str,
    status_code: int = 400,
):
    return _render_accounts_page(
        request,
        session,
        templates,
        current_admin=current_admin,
        error_message=error_message,
        status_code=status_code,
    )


def _render_accounts_page(
    request: Request,
    session: Session,
    templates: Jinja2Templates,
    *,
    current_admin: AdminUser,
    error_message: str | None = None,
    status_code: int = 200,
):
    settings = request.app.state.settings
    callback_url = build_google_callback_url(
        request,
        session=session,
        settings=settings,
    )
    callback_error = validate_google_callback_url(callback_url)
    google_snapshot = get_google_provider_configuration_snapshot(
        session,
        settings=settings,
    )
    google_block_message = None
    if bool(google_snapshot["configured"]) and callback_error is not None:
        google_block_message = (
            "Google settings are saved, but Google sign-in is still blocked for the current callback URL. "
            f"{callback_error}"
        )
    accounts = session.scalars(
        select(ProviderAccount)
        .options(selectinload(ProviderAccount.calendars))
        .order_by(ProviderAccount.display_name, ProviderAccount.provider_account_id)
    ).all()
    return templates.TemplateResponse(
        request,
        "accounts.html",
        {
            "current_admin": current_admin,
            "accounts": accounts,
            "google_configured": google_snapshot["configured"],
            "google_callback_url": callback_url,
            "google_callback_error": callback_error,
            "google_block_message": google_block_message,
            "google_connect_allowed": bool(google_snapshot["configured"])
            and callback_error is None,
            "google_configuration_source": google_snapshot["source"],
            "google_settings_url": "/admin/providers",
            "account_rows": [_build_account_row(account) for account in accounts],
            "error_message": error_message,
        },
        status_code=status_code,
    )


def _build_account_row(account: ProviderAccount) -> dict[str, object]:
    metadata = dict(account.provider_metadata or {})
    provider_type = account.provider_type
    provider_name = {
        "mock": "Mock",
        "google": "Google",
        "icloud_caldav": "Apple/iCloud",
    }.get(provider_type, provider_type)

    status = "Connected"
    if metadata.get("google_reconnect_required"):
        status = "Reconnect required"
    elif isinstance(metadata.get("google_auth_status"), str):
        status = str(metadata["google_auth_status"]).replace("_", " ").title()
    elif isinstance(metadata.get("auth_status"), str):
        status = str(metadata["auth_status"]).replace("_", " ").title()

    return {
        "provider_name": provider_name,
        "account_name": account.display_name or account.provider_account_id,
        "calendar_count": len(account.calendars),
        "status": status,
        "last_error": metadata.get("last_auth_error") or metadata.get("google_last_auth_error"),
        "manage_calendars_url": "/admin/calendars" if account.calendars else None,
    }
