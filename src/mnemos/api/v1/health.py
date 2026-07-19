from fastapi import APIRouter
from fastapi.responses import ORJSONResponse

from mnemos.agentic.agents.tool_metrics import tool_metrics
from mnemos.core.config import settings
from mnemos.services.operations.health import (
    graph_health_check,
    readiness_checks,
    vector_health_check,
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


@router.get("/agent-tools")
async def agent_tool_health() -> ORJSONResponse:
    snapshot = tool_metrics.snapshot(
        failure_rate_threshold=settings.tool_health_failure_rate_threshold,
        latency_threshold_ms=settings.tool_health_p95_latency_ms,
    )
    return ORJSONResponse(
        status_code=200 if snapshot["status"] == "healthy" else 503,
        content=snapshot,
    )
