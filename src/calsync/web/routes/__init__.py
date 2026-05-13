from fastapi import APIRouter

from .auth import router as auth_router
from .setup import router as setup_router


router = APIRouter()
router.include_router(setup_router)
router.include_router(auth_router)

__all__ = ["router"]
