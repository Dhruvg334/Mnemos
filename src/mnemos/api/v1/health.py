from fastapi import APIRouter
from fastapi.responses import ORJSONResponse

from mnemos.services.operations.health import (
    readiness_checks,
    vector_health_check,
    graph_health_check,
)

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


@router.get("/vector/health")
async def vector_health():
    status = await vector_health_check()
    return ORJSONResponse(
        status_code=200 if status == "healthy" else 503,
        content={"status": status},
    )


@router.get("/graph/health")
async def graph_health():
    status = await graph_health_check()
    return ORJSONResponse(
        status_code=200 if status == "healthy" else 503,
        content={"status": status},
    )
