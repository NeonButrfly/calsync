from fastapi import APIRouter

from .accounts import router as accounts_router
from .auth import router as auth_router
from .calendars import router as calendars_router
from .connections import router as connections_router
from .dashboard import router as dashboard_router
from .events import router as events_router
from .feeds import router as feeds_router
from .flightboard import router as flightboard_router
from .google import router as google_router
from .microsoft import router as microsoft_router
from .problems import router as problems_router
from .providers import router as providers_router
from .review import router as review_router
from .setup import router as setup_router
from .sync import router as sync_router


router = APIRouter()
router.include_router(setup_router)
router.include_router(auth_router)
router.include_router(google_router)
router.include_router(microsoft_router)
router.include_router(feeds_router)
router.include_router(dashboard_router)
router.include_router(events_router)
router.include_router(problems_router)
router.include_router(flightboard_router)
router.include_router(review_router)
router.include_router(providers_router)
router.include_router(connections_router)
router.include_router(accounts_router)
router.include_router(calendars_router)
router.include_router(sync_router)

__all__ = ["router"]
