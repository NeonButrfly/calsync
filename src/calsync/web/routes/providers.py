from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from calsync.config import build_google_callback_url, validate_google_callback_url
from calsync.models import AdminUser
from calsync.services.provider_config import (
    get_google_provider_configuration_snapshot,
    save_google_oauth_configuration,
)
from calsync.web.deps import (
    get_db,
    get_encryption_key,
    get_templates,
    require_admin,
)


router = APIRouter(prefix="/admin/providers")


@router.get("")
def provider_settings_page(
    request: Request,
    saved: str | None = Query(default=None),
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
):
    return _render_provider_settings_page(
        request,
        session,
        templates,
        current_admin=current_admin,
        success_message="Google OAuth app settings saved." if saved == "google" else None,
    )


@router.post("/google")
def save_google_provider_settings(
    request: Request,
    client_id: str = Form(...),
    client_secret: str = Form(""),
    scopes: str = Form(""),
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
    encryption_key: str = Depends(get_encryption_key),
):
    normalized_client_id = client_id.strip()
    if not normalized_client_id:
        return _render_provider_settings_page(
            request,
            session,
            templates,
            current_admin=current_admin,
            error_message="Google client ID is required.",
            status_code=400,
        )

    try:
        save_google_oauth_configuration(
            session,
            client_id=normalized_client_id,
            client_secret=client_secret,
            scopes=scopes,
            encryption_key=encryption_key,
            settings=request.app.state.settings,
        )
    except ValueError as exc:
        return _render_provider_settings_page(
            request,
            session,
            templates,
            current_admin=current_admin,
            error_message=str(exc),
            status_code=400,
        )

    session.commit()
    return RedirectResponse(url="/admin/providers?saved=google", status_code=303)


def _render_provider_settings_page(
    request: Request,
    session: Session,
    templates: Jinja2Templates,
    *,
    current_admin: AdminUser,
    error_message: str | None = None,
    success_message: str | None = None,
    status_code: int = 200,
):
    settings = request.app.state.settings
    google_snapshot = get_google_provider_configuration_snapshot(
        session,
        settings=settings,
    )
    callback_url = build_google_callback_url(request, settings=settings)
    callback_error = validate_google_callback_url(callback_url)
    return templates.TemplateResponse(
        request,
        "providers.html",
        {
            "current_admin": current_admin,
            "error_message": error_message,
            "success_message": success_message,
            "google_client_id": google_snapshot["client_id"],
            "google_scopes": google_snapshot["scopes"],
            "google_has_secret": google_snapshot["has_secret"],
            "google_source": google_snapshot["source"],
            "google_configured": google_snapshot["configured"],
            "google_callback_url": callback_url,
            "google_callback_error": callback_error,
        },
        status_code=status_code,
    )
