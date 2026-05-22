from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from calsync.models import AdminUser
from calsync.services.reconciliation import (
    collect_trust_metrics,
    list_duplicate_groups,
    prefer_event_in_group,
    rebuild_duplicate_groups,
    restore_hidden_duplicate,
)
from calsync.web.deps import get_db, get_templates, require_admin


router = APIRouter(prefix="/admin/review")


@router.get("")
def review_page(
    request: Request,
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
):
    rebuild_duplicate_groups(session)
    metrics = collect_trust_metrics(session)
    duplicate_groups = list_duplicate_groups(session)
    session.commit()
    return templates.TemplateResponse(
        request,
        "review.html",
        {
            "current_admin": current_admin,
            "trust_metrics": metrics,
            "duplicate_groups": duplicate_groups,
        },
    )


@router.post("/groups/{group_id}/prefer/{event_id}")
def prefer_duplicate_event(
    group_id: str,
    event_id: str,
    session: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    try:
        prefer_event_in_group(session, group_id, event_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return RedirectResponse(url="/admin/review", status_code=303)


@router.post("/events/{event_id}/restore")
def restore_duplicate_event(
    event_id: str,
    session: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    try:
        restore_hidden_duplicate(session, event_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.commit()
    return RedirectResponse(url="/admin/review", status_code=303)
