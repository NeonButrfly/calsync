from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from calsync.models import AdminUser, Event, EventGroup
from calsync.services.reconciliation import (
    collect_trust_metrics,
    duplicate_group_anchor_id,
    list_group_events,
    list_duplicate_groups,
    prefer_event_in_group,
    rebuild_duplicate_groups,
    restore_hidden_duplicate,
    restore_hidden_duplicates_in_group,
)
from calsync.services.source_labels import copy_label_for_event, source_line_for_event
from calsync.web.deps import get_db, get_templates, require_admin


router = APIRouter(prefix="/admin/review")


@dataclass
class ReviewEventView:
    id: str
    title: str
    starts_at: object
    source_line: str
    location: str | None
    event_visibility_state: str
    is_preferred: bool
    keep_label: str


@dataclass
class ReviewGroupView:
    group: object
    anchor_id: str
    preferred_starts_at: object
    preferred_copy_label: str
    events: list[ReviewEventView]


def _build_review_groups(session: Session) -> list[ReviewGroupView]:
    review_groups: list[ReviewGroupView] = []
    for duplicate_group in list_duplicate_groups(session, attention_only=True):
        preferred_event = next(
            event
            for event in duplicate_group.events
            if event.id == duplicate_group.group.preferred_event_id
        )
        review_groups.append(
            ReviewGroupView(
                group=duplicate_group.group,
                anchor_id=duplicate_group.anchor_id,
                preferred_starts_at=duplicate_group.group.preferred_starts_at,
                preferred_copy_label=copy_label_for_event(session, preferred_event),
                events=[
                    ReviewEventView(
                        id=event.id,
                        title=event.title,
                        starts_at=event.starts_at,
                        source_line=source_line_for_event(session, event),
                        location=event.location,
                        event_visibility_state=event.event_visibility_state,
                        is_preferred=duplicate_group.group.preferred_event_id == event.id,
                        keep_label=f"Keep {copy_label_for_event(session, event)}",
                    )
                    for event in duplicate_group.events
                ],
            )
        )
    return review_groups


@router.get("")
def review_page(
    request: Request,
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
):
    rebuild_duplicate_groups(session)
    metrics = collect_trust_metrics(session, attention_only=True)
    duplicate_groups = _build_review_groups(session)
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
    group_events = list_group_events(session, group_id)
    try:
        prefer_event_in_group(session, group_id, event_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return RedirectResponse(url=f"/admin/review#{duplicate_group_anchor_id(group_events)}", status_code=303)


@router.post("/groups/{group_id}/restore-all")
def restore_duplicate_group(
    group_id: str,
    session: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    group = session.get(EventGroup, group_id)
    group_events = list_group_events(session, group_id)
    try:
        restore_hidden_duplicates_in_group(session, group_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.commit()
    redirect_target = f"/admin/review#{duplicate_group_anchor_id(group_events)}" if group is not None else "/admin/review"
    return RedirectResponse(url=redirect_target, status_code=303)


@router.post("/events/{event_id}/restore")
def restore_duplicate_event(
    event_id: str,
    session: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    event = session.get(Event, event_id)
    group_id = event.canonical_group_id if event is not None else None
    group_events = list_group_events(session, group_id) if group_id else []
    try:
        restore_hidden_duplicate(session, event_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.commit()
    redirect_target = f"/admin/review#{duplicate_group_anchor_id(group_events)}" if group_events else "/admin/review"
    return RedirectResponse(url=redirect_target, status_code=303)
