from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from calsync.models import AdminUser, ProviderAccount
from calsync.services.problems import build_problem_summary, list_operator_problems
from calsync.services.reconciliation import rebuild_duplicate_groups
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
