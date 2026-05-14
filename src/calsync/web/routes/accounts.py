from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from calsync.config import (
    build_google_callback_url,
    has_google_oauth_config,
    validate_google_callback_url,
)
from calsync.models import AdminUser, ProviderAccount
from calsync.services.sync import sync_account
from calsync.web.deps import get_db, get_templates, require_admin


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
    callback_url = build_google_callback_url(request, settings=settings)
    callback_error = validate_google_callback_url(callback_url)
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
            "google_configured": has_google_oauth_config(settings),
            "google_callback_url": callback_url,
            "google_callback_error": callback_error,
            "google_connect_allowed": has_google_oauth_config(settings)
            and callback_error is None,
            "error_message": error_message,
        },
        status_code=status_code,
    )
