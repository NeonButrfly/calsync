from fastapi import APIRouter

from calsync.services.readiness import ReadinessService

router = APIRouter(prefix="/api/readiness", tags=["readiness"])


@router.get("")
def get_readiness() -> dict[str, object]:
    return ReadinessService().build()
