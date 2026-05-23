from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from calsync.models import AdminUser
from calsync.services.event_explain import build_event_explain_view
from calsync.services.reconciliation import rebuild_duplicate_groups
from calsync.web.deps import get_db, get_templates, require_admin


router = APIRouter(prefix="/admin/events")


@router.get("/{event_id}")
def event_explain_page(
    event_id: str,
    request: Request,
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
):
    rebuild_duplicate_groups(session)
    try:
        event_view = build_event_explain_view(session, event_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()

    return templates.TemplateResponse(
        request,
        "event_explain.html",
        {
            "current_admin": current_admin,
            "event_view": event_view,
        },
    )
