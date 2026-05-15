from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from calsync.models import AdminUser, Event, ProviderCalendar
from calsync.web.deps import get_db, get_templates, require_admin


router = APIRouter(prefix="/admin")

_FLIGHTBOARD_TEMPLATE = """
{% extends "base.html" %}

{% block title %}CalSync Flightboard{% endblock %}
{% block page_title %}Flightboard{% endblock %}

{% block content %}
<section class="panel">
  <h2>Enabled calendar events</h2>
  {% if events %}
  <ul class="event-list">
    {% for event in events %}
    <li>
      <strong>{{ event.title }}</strong>
      <span>{{ event.calendar_name }}</span>
      <span>{{ event.starts_at }}</span>
    </li>
    {% endfor %}
  </ul>
  {% else %}
  <p>No enabled calendar events available.</p>
  {% endif %}
</section>
{% endblock %}
"""


@router.get("/flightboard", response_class=HTMLResponse)
def flightboard_page(
    request: Request,
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
) -> HTMLResponse:
    events = session.execute(
        select(Event.title, Event.starts_at, ProviderCalendar.name)
        .join(ProviderCalendar, Event.provider_calendar_pk == ProviderCalendar.id)
        .where(ProviderCalendar.enabled.is_(True))
        .order_by(Event.starts_at, Event.id)
    ).all()

    template = templates.env.from_string(_FLIGHTBOARD_TEMPLATE)
    return HTMLResponse(
        content=template.render(
            current_admin=current_admin,
            events=[
                {
                    "title": title,
                    "starts_at": starts_at,
                    "calendar_name": calendar_name or "Unnamed calendar",
                }
                for title, starts_at, calendar_name in events
            ],
            request=request,
        )
    )
