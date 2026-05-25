from __future__ import annotations

from secrets import token_urlsafe
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from calsync.models import AdminUser
from calsync.services.app_settings import build_external_url
from calsync.services.providers.microsoft import (
    MicrosoftOAuthError,
    build_microsoft_authorization_url,
    connect_microsoft_account_from_callback,
)
from calsync.services.sync import discover_calendars
from calsync.web.deps import (
    get_db,
    get_encryption_key,
    get_templates,
    require_admin,
    require_session_secret,
)
from .accounts import render_accounts_page_with_error


MICROSOFT_OAUTH_SESSION_KEY = "microsoft_oauth_state"

router = APIRouter()


@router.get("/auth/microsoft/start")
def start_microsoft_oauth(
    request: Request,
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
    _: str = Depends(require_session_secret),
):
    settings = request.app.state.settings
    callback_url = build_external_url(
        request,
        settings.microsoft_oauth_redirect_path,
        session=session,
        settings=settings,
    )
    state = token_urlsafe(24)
    request.session[MICROSOFT_OAUTH_SESSION_KEY] = {"state": state}
    try:
        authorization_url = build_microsoft_authorization_url(
            callback_url,
            state,
            settings=settings,
            session=session,
        )
    except MicrosoftOAuthError as exc:
        return render_accounts_page_with_error(
            request,
            session,
            templates,
            current_admin=current_admin,
            error_message=str(exc),
        )

    return RedirectResponse(url=authorization_url, status_code=303)


@router.get("/auth/microsoft/callback")
def microsoft_oauth_callback(
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
    pending_state = request.session.pop(MICROSOFT_OAUTH_SESSION_KEY, None)
    if not isinstance(pending_state, dict) or pending_state.get("state") != state:
        raise HTTPException(status_code=400, detail="Microsoft OAuth state mismatch.")

    if error:
        return render_accounts_page_with_error(
            request,
            session,
            templates,
            current_admin=current_admin,
            error_message="Microsoft sign-in was cancelled or denied.",
        )
    if not code:
        return render_accounts_page_with_error(
            request,
            session,
            templates,
            current_admin=current_admin,
            error_message="Microsoft did not return an authorization code.",
        )

    callback_url = build_external_url(
        request,
        request.app.state.settings.microsoft_oauth_redirect_path,
        session=session,
        settings=request.app.state.settings,
    )

    try:
        account = connect_microsoft_account_from_callback(
            session,
            code=code,
            callback_base_url=_callback_base_url_from_callback_url(
                callback_url,
                redirect_path=request.app.state.settings.microsoft_oauth_redirect_path,
            ),
            settings=request.app.state.settings,
            encryption_key=encryption_key,
        )
        discover_calendars(session, account.id, settings=request.app.state.settings)
    except MicrosoftOAuthError as exc:
        session.rollback()
        return render_accounts_page_with_error(
            request,
            session,
            templates,
            current_admin=current_admin,
            error_message=str(exc),
        )

    session.commit()
    return RedirectResponse(url="/admin/calendars", status_code=303)


def _callback_base_url_from_callback_url(
    callback_url: str,
    *,
    redirect_path: str,
) -> str:
    split = urlsplit(callback_url)
    path = split.path
    if redirect_path and path.endswith(redirect_path):
        path = path[: -len(redirect_path)]
    return urlunsplit((split.scheme, split.netloc, path, "", ""))
