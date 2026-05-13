from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from calsync.models import AdminUser
from calsync.repos.users import get_admin_by_email, get_admin_by_username
from calsync.services.auth import (
    consume_recovery_code,
    verify_password,
    verify_totp_for_user_once,
)
from calsync.services.bootstrap import is_setup_complete
from calsync.web.deps import get_db, get_encryption_key, get_templates


ADMIN_SESSION_KEY = "admin_session"
PENDING_MFA_SESSION_KEY = "pending_mfa_session"

router = APIRouter()


@router.get("/login")
def login_page(
    request: Request,
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
):
    if not is_setup_complete(session):
        return RedirectResponse(url="/setup", status_code=303)
    return templates.TemplateResponse(
        request,
        "login.html",
        {"errors": [], "identifier": ""},
    )


@router.post("/login")
def submit_login(
    request: Request,
    identifier: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
):
    if not is_setup_complete(session):
        return RedirectResponse(url="/setup", status_code=303)

    normalized_identifier = identifier.strip()
    if "@" in normalized_identifier:
        admin_user = get_admin_by_email(session, normalized_identifier.lower())
    else:
        admin_user = get_admin_by_username(session, normalized_identifier)
    if admin_user is None or admin_user.password_hash is None:
        return _render_login_error(
            request,
            templates,
            identifier=identifier,
            message="Invalid identifier or password.",
        )
    if not verify_password(password, admin_user.password_hash):
        return _render_login_error(
            request,
            templates,
            identifier=identifier,
            message="Invalid identifier or password.",
        )

    request.session[PENDING_MFA_SESSION_KEY] = {
        "user_id": admin_user.id,
        "session_version": admin_user.session_version,
    }
    request.session.pop(ADMIN_SESSION_KEY, None)
    return RedirectResponse(url="/login/mfa", status_code=303)


@router.get("/login/mfa")
def login_mfa_page(
    request: Request,
    templates: Jinja2Templates = Depends(get_templates),
):
    if PENDING_MFA_SESSION_KEY not in request.session:
        raise HTTPException(status_code=400, detail="Password verification required.")

    return templates.TemplateResponse(
        request,
        "mfa_challenge.html",
        {"errors": []},
    )


@router.post("/login/mfa")
def submit_login_mfa(
    request: Request,
    code: str = Form(...),
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    encryption_key: str = Depends(get_encryption_key),
):
    pending_session = request.session.get(PENDING_MFA_SESSION_KEY)
    if pending_session is None:
        raise HTTPException(status_code=400, detail="Password verification required.")

    admin_user = session.get(AdminUser, pending_session["user_id"])
    if admin_user is None or admin_user.session_version != pending_session["session_version"]:
        request.session.pop(PENDING_MFA_SESSION_KEY, None)
        raise HTTPException(status_code=400, detail="MFA challenge is no longer valid.")

    matched_counter = verify_totp_for_user_once(
        admin_user,
        code,
        encryption_key=encryption_key,
        last_accepted_counter=None,
    )
    recovery_code_consumed = False
    if matched_counter is None:
        recovery_code_consumed = consume_recovery_code(session, admin_user, code)
        if recovery_code_consumed:
            session.commit()

    if matched_counter is None and not recovery_code_consumed:
        return templates.TemplateResponse(
            request,
            "mfa_challenge.html",
            {"errors": ["Enter a valid MFA code or recovery code."]},
            status_code=400,
        )

    request.session[ADMIN_SESSION_KEY] = {
        "user_id": admin_user.id,
        "session_version": admin_user.session_version,
    }
    request.session.pop(PENDING_MFA_SESSION_KEY, None)
    return RedirectResponse(url="/", status_code=303)


def _render_login_error(
    request: Request,
    templates: Jinja2Templates,
    *,
    identifier: str,
    message: str,
):
    return templates.TemplateResponse(
        request,
        "login.html",
        {"errors": [message], "identifier": identifier},
        status_code=400,
    )
