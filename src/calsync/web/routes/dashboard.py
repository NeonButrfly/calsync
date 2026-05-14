from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from calsync.config import build_external_url
from calsync.models import AdminUser, Event, ProviderAccount, ProviderCalendar, SyncLog
from calsync.services.publishing import ensure_combined_feed, rotate_combined_feed_token
from calsync.web.deps import get_db, get_templates, require_admin


router = APIRouter(prefix="/admin")


@router.get("")
def dashboard_page(
    request: Request,
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
):
    combined_feed = ensure_combined_feed(session)
    session.commit()

    account_count = session.scalar(select(func.count(ProviderAccount.id))) or 0
    latest_sync = session.scalar(
        select(SyncLog).order_by(SyncLog.started_at.desc(), SyncLog.id.desc())
    )
    upcoming_events = session.scalars(
        select(Event).order_by(Event.starts_at, Event.id).limit(8)
    ).all()
    context = {
        "current_admin": current_admin,
        "account_count": account_count,
        "calendar_count": session.scalar(select(func.count(ProviderCalendar.id))) or 0,
        "event_count": session.scalar(select(func.count(Event.id))) or 0,
        "combined_feed_url": build_external_url(
            request,
            f"/feeds/{combined_feed.token}.ics",
            settings=request.app.state.settings,
        ),
        "latest_sync": latest_sync,
        "upcoming_events": upcoming_events,
    }
    return templates.TemplateResponse(request, "dashboard.html", context)


@router.get("/feeds")
def publishing_page(
    request: Request,
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
):
    combined_feed = ensure_combined_feed(session)
    session.commit()
    return templates.TemplateResponse(
        request,
        "ics_publishing.html",
        {
            "current_admin": current_admin,
            "combined_feed_url": build_external_url(
                request,
                f"/feeds/{combined_feed.token}.ics",
                settings=request.app.state.settings,
            ),
            "combined_feed_token": combined_feed.token,
        },
    )


@router.post("/feeds/combined/rotate")
def rotate_combined_feed(
    session: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    rotate_combined_feed_token(session)
    session.commit()
    return RedirectResponse(url="/admin/feeds", status_code=303)

