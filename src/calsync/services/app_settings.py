from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request
from sqlalchemy.orm import Session

from calsync.repos.state import get_app_state_text


if TYPE_CHECKING:
    from calsync.config import Settings


PUBLIC_BASE_URL_STATE_KEY = "public_base_url"


def get_saved_public_base_url(session: Session) -> str | None:
    return get_app_state_text(session, PUBLIC_BASE_URL_STATE_KEY)


def get_configured_public_base_url(settings: Settings) -> str | None:
    if settings.public_base_url:
        return str(settings.public_base_url)
    return None


def resolve_public_base_url(
    request: Request,
    *,
    session: Session | None,
    settings: Settings,
) -> str:
    saved_public_url = get_saved_public_base_url(session) if session is not None else None
    if saved_public_url:
        return saved_public_url
    configured_public_url = get_configured_public_base_url(settings)
    if configured_public_url:
        return configured_public_url
    return str(request.base_url)


def build_external_url(
    request: Request,
    path: str,
    *,
    session: Session | None,
    settings: Settings,
) -> str:
    from calsync.config import build_external_url as build_config_external_url

    public_base_url = resolve_public_base_url(
        request,
        session=session,
        settings=settings,
    )
    return build_config_external_url(
        request,
        path,
        settings=settings,
        public_base_url=public_base_url,
    )


def build_google_callback_url(
    request: Request,
    *,
    session: Session | None,
    settings: Settings,
) -> str:
    from calsync.config import (
        build_google_callback_url as build_config_google_callback_url,
    )

    public_base_url = resolve_public_base_url(
        request,
        session=session,
        settings=settings,
    )
    return build_config_google_callback_url(
        request,
        settings=settings,
        public_base_url=public_base_url,
    )
