from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from calsync.services.publishing import render_feed_for_token
from calsync.web.deps import get_db


router = APIRouter()
FEED_CACHE_CONTROL = "private, no-store"


@router.get("/feeds/{token}.ics")
def get_feed(
    token: str,
    session: Session = Depends(get_db),
) -> Response:
    try:
        payload = render_feed_for_token(session, token)
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail="Feed not found.",
            headers={"Cache-Control": FEED_CACHE_CONTROL},
        ) from exc

    return Response(
        content=payload,
        media_type="text/calendar",
        headers={"Cache-Control": FEED_CACHE_CONTROL},
    )
