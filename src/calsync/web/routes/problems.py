from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from calsync.models import AdminUser, Event, ProviderAccount
from calsync.services.problems import build_problem_summary, list_operator_problems
from calsync.services.reconciliation import (
    duplicate_group_anchor_id,
    list_group_events,
    prefer_event_in_group,
    rebuild_duplicate_groups,
    restore_hidden_duplicates_in_group,
)
from calsync.services.sync import sync_account
from calsync.web.deps import get_db, get_templates, require_admin


router = APIRouter(prefix="/admin/problems")


@router.get("")
def problems_page(
    request: Request,
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
):
    rebuild_duplicate_groups(session)
    context = {
        "current_admin": current_admin,
        "problem_summary": build_problem_summary(session),
        "problems": list_operator_problems(session),
    }
    session.commit()
    return templates.TemplateResponse(request, "problems.html", context)


@router.post("/actions/sync/{account_id}")
def problem_sync_now(
    account_id: str,
    request: Request,
    session: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    account = session.get(ProviderAccount, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found.")

    sync_account(
        session,
        account_id,
        trigger="manual",
        settings=request.app.state.settings,
    )
    session.commit()
    return RedirectResponse(url="/admin/problems", status_code=303)


@router.post("/actions/event/{event_id}/provider/{provider_type}")
def problem_prefer_provider_copy(
    event_id: str,
    provider_type: str,
    session: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    event = session.get(Event, event_id)
    if event is None or not event.canonical_group_id:
        raise HTTPException(status_code=404, detail="Duplicate event group not found.")

    group_events = list_group_events(session, event.canonical_group_id)
    provider_event = next((candidate for candidate in group_events if candidate.provider_type == provider_type), None)
    if provider_event is None:
        raise HTTPException(status_code=404, detail="Provider copy not found in duplicate group.")

    try:
        prefer_event_in_group(session, event.canonical_group_id, provider_event.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return RedirectResponse(url=f"/admin/problems#{duplicate_group_anchor_id(group_events)}", status_code=303)


@router.post("/actions/event/{event_id}/show-both")
def problem_restore_duplicate_group(
    event_id: str,
    session: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    event = session.get(Event, event_id)
    if event is None or not event.canonical_group_id:
        raise HTTPException(status_code=404, detail="Duplicate event group not found.")
    group_events = list_group_events(session, event.canonical_group_id)

    try:
        restore_hidden_duplicates_in_group(session, event.canonical_group_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.commit()
    return RedirectResponse(url=f"/admin/problems#{duplicate_group_anchor_id(group_events)}", status_code=303)
