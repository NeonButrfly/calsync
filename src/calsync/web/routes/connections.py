from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from calsync.models import AdminUser
from calsync.web.deps import get_db, get_templates, require_admin

from .accounts import render_connections_page


router = APIRouter(prefix="/admin/connections")


@router.get("")
def connections_page(
    request: Request,
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
):
    return render_connections_page(
        request,
        session,
        templates,
        current_admin=current_admin,
    )
