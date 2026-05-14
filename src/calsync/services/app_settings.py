from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from calsync.config import Settings
from calsync.repos.state import get_app_state_text


PUBLIC_BASE_URL_STATE_KEY = "public_base_url"


def get_saved_public_base_url(session: Session) -> str | None:
    return get_app_state_text(session, PUBLIC_BASE_URL_STATE_KEY)


def resolve_public_base_url(
    request: Request,
    *,
    session: Session | None,
    settings: Settings,
) -> str:
    saved_public_url = get_saved_public_base_url(session) if session is not None else None
    if saved_public_url:
        return saved_public_url
    if settings.public_base_url:
        return str(settings.public_base_url)
    return str(request.base_url)
