from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from calsync.services.bootstrap import (
    SetupSubmission,
    complete_first_run_setup,
    get_or_create_pending_setup,
    require_setup_incomplete,
)
from calsync.web.deps import (
    get_db,
    get_encryption_key,
    get_templates,
    require_session_secret,
)


router = APIRouter()


@router.get("/setup")
def setup_page(
    request: Request,
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    _: str = Depends(require_session_secret),
):
    require_setup_incomplete(session)
    pending_setup = get_or_create_pending_setup(request.app, request.session)
    return _render_setup_page(
        request,
        templates,
        pending_setup=pending_setup,
        form_data={},
        errors=[],
    )


@router.post("/setup")
def submit_setup(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirmation: str = Form(...),
    totp_code: str = Form(...),
    recovery_acknowledged: str | None = Form(default=None),
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    _: str = Depends(require_session_secret),
    encryption_key: str = Depends(get_encryption_key),
):
    pending_setup = get_or_create_pending_setup(request.app, request.session)
    result = complete_first_run_setup(
        session,
        request.app,
        request.session,
        submission=SetupSubmission(
            username=username,
            email=email,
            password=password,
            password_confirmation=password_confirmation,
            totp_code=totp_code,
            recovery_acknowledged=recovery_acknowledged == "on",
        ),
        encryption_key=encryption_key,
    )
    if result.errors:
        return _render_setup_page(
            request,
            templates,
            pending_setup=pending_setup,
            form_data={
                "username": username,
                "email": email,
            },
            errors=result.errors,
        )

    return RedirectResponse(url="/login", status_code=303)


def _render_setup_page(
    request: Request,
    templates: Jinja2Templates,
    *,
    pending_setup,
    form_data: dict[str, str],
    errors: list[str],
):
    return templates.TemplateResponse(
        request,
        "setup.html",
        {
            "errors": errors,
            "form_data": form_data,
            "recovery_codes": pending_setup.recovery_codes,
            "totp_secret": pending_setup.enrollment.secret,
            "totp_qr_data_url": pending_setup.enrollment.qr_png_data_url,
        },
    )
