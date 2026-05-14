from fastapi import APIRouter

from .accounts import router as accounts_router
from .auth import router as auth_router
from .calendars import router as calendars_router
from .dashboard import router as dashboard_router
from .feeds import router as feeds_router
from .google import router as google_router
from .setup import router as setup_router
from .sync import router as sync_router


router = APIRouter()
router.include_router(setup_router)
router.include_router(auth_router)
router.include_router(google_router)
router.include_router(feeds_router)
router.include_router(dashboard_router)
router.include_router(accounts_router)
router.include_router(calendars_router)
router.include_router(sync_router)

__all__ = ["router"]
