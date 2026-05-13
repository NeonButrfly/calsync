from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from calsync.models import PublishedFeed


def get_published_feed_by_scope(
    session: Session,
    *,
    scope_type: str,
    scope_key: str,
) -> PublishedFeed | None:
    return session.scalar(
        select(PublishedFeed).where(
            PublishedFeed.scope_type == scope_type,
            PublishedFeed.scope_key == scope_key,
        )
    )


def get_active_published_feed_by_token(
    session: Session,
    *,
    token: str,
) -> PublishedFeed | None:
    return session.scalar(
        select(PublishedFeed).where(
            PublishedFeed.token == token,
            PublishedFeed.is_active.is_(True),
        )
    )
