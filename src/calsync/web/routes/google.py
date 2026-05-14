from __future__ import annotations

from secrets import token_urlsafe

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from calsync.config import build_google_callback_url
from calsync.services.providers.google import (
    GoogleOAuthError,
    build_google_authorization_url,
    connect_google_account_from_callback,
)
from calsync.services.sync import discover_calendars
from calsync.web.deps import (
    get_db,
    get_encryption_key,
    get_templates,
    require_admin,
    require_session_secret,
)
from calsync.models import AdminUser
from .accounts import render_accounts_page_with_error


GOOGLE_OAUTH_SESSION_KEY = "google_oauth_state"

router = APIRouter()


@router.get("/auth/google/start")
def start_google_oauth(
    request: Request,
    force_consent: bool = Query(default=False),
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
    _: str = Depends(require_session_secret),
):
    settings = request.app.state.settings
    callback_url = build_google_callback_url(request, settings=settings)
    state = token_urlsafe(24)
    request.session[GOOGLE_OAUTH_SESSION_KEY] = {"state": state}
    try:
        authorization_url = build_google_authorization_url(
            callback_url,
            state,
            settings=settings,
            force_consent=force_consent,
        )
    except GoogleOAuthError as exc:
        return render_accounts_page_with_error(
            request,
            session,
            templates,
            current_admin=current_admin,
            error_message=str(exc),
        )

    return RedirectResponse(url=authorization_url, status_code=303)


@router.get("/auth/google/callback")
def google_oauth_callback(
    request: Request,
    state: str | None = None,
    code: str | None = None,
    error: str | None = None,
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
    _: str = Depends(require_session_secret),
    encryption_key: str = Depends(get_encryption_key),
):
    pending_state = request.session.pop(GOOGLE_OAUTH_SESSION_KEY, None)
    if not isinstance(pending_state, dict) or pending_state.get("state") != state:
        raise HTTPException(status_code=400, detail="Google OAuth state mismatch.")

    if error:
        return render_accounts_page_with_error(
            request,
            session,
            templates,
            current_admin=current_admin,
            error_message="Google sign-in was cancelled or denied.",
        )
    if not code:
        return render_accounts_page_with_error(
            request,
            session,
            templates,
            current_admin=current_admin,
            error_message="Google did not return an authorization code.",
        )

    try:
        account = connect_google_account_from_callback(
            session,
            code=code,
            callback_base_url=str(request.app.state.settings.public_base_url or request.base_url),
            settings=request.app.state.settings,
            encryption_key=encryption_key,
        )
        discover_calendars(
            session,
            account.id,
            settings=request.app.state.settings,
        )
    except GoogleOAuthError as exc:
        session.rollback()
        return render_accounts_page_with_error(
            request,
            session,
            templates,
            current_admin=current_admin,
            error_message=str(exc),
        )

    session.commit()
    return RedirectResponse(url="/admin/accounts", status_code=303)
