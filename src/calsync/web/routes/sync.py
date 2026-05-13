from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from calsync.models import AdminUser, ProviderAccount, SyncLog
from calsync.services.sync import sync_account
from calsync.web.deps import get_db, get_templates, require_admin


router = APIRouter(prefix="/admin/sync")


@router.get("")
def sync_status_page(
    request: Request,
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
):
    accounts = session.scalars(
        select(ProviderAccount)
        .options(selectinload(ProviderAccount.calendars))
        .order_by(ProviderAccount.display_name, ProviderAccount.provider_account_id)
    ).all()
    latest_logs = {
        account.id: session.scalar(
            select(SyncLog)
            .where(SyncLog.provider_account_pk == account.id)
            .order_by(SyncLog.started_at.desc(), SyncLog.id.desc())
        )
        for account in accounts
    }
    return templates.TemplateResponse(
        request,
        "sync_status.html",
        {
            "current_admin": current_admin,
            "accounts": accounts,
            "latest_logs": latest_logs,
        },
    )


@router.post("/accounts/{account_id}/run")
def run_sync_now(
    account_id: str,
    session: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    account = session.get(ProviderAccount, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found.")

    sync_account(session, account_id, trigger="manual")
    session.commit()
    return RedirectResponse(url="/admin/sync", status_code=303)
