from fastapi import APIRouter
from fastapi.responses import ORJSONResponse

from mnemos.services.operations.health import readiness_checks

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "healthy"}


@router.get("/ready")
async def ready():
    checks = await readiness_checks()
    healthy = all(value == "healthy" for value in checks.values())
    return ORJSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "healthy" if healthy else "degraded",
            "checks": checks,
        },
    )
