from fastapi import APIRouter

from .auth import router as auth_router
from .feeds import router as feeds_router
from .setup import router as setup_router


router = APIRouter()
router.include_router(setup_router)
router.include_router(auth_router)
router.include_router(feeds_router)

__all__ = ["router"]
