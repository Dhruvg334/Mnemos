from __future__ import annotations

from sqlalchemy import text

from mnemos.core.config import settings
from mnemos.core.db import SessionLocal
from mnemos.core.rate_limit import _client
from mnemos.integrations.storage import S3Storage

_REQUIRED_HEALTHY = {"healthy"}
_OPTIONAL_ACCEPTABLE = {"healthy", "disabled", "unavailable"}


async def readiness_checks() -> dict[str, str]:
    checks: dict[str, str] = {}

    try:
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception:
        checks["database"] = "unhealthy"

    if settings.external_health_checks_enabled:
        try:
            await _client().ping()
            checks["redis"] = "healthy"
        except Exception:
            checks["redis"] = "unhealthy"

        try:
            await S3Storage().ensure_bucket()
            checks["object_storage"] = "healthy"
        except Exception:
            checks["object_storage"] = "unhealthy"

        checks["neo4j"] = await graph_health_check()
    else:
        checks["redis"] = "disabled"
        checks["object_storage"] = "disabled"
        checks["neo4j"] = "disabled"

    checks["pgvector"] = await vector_health_check()
    return checks


def assess_readiness(checks: dict[str, str]) -> tuple[bool, str]:
    """Return whether required dependencies are ready and the aggregate status."""
    required = {"database", "pgvector"}
    if settings.external_health_checks_enabled:
        required.update({"redis", "object_storage"})
    if settings.neo4j_required_for_readiness:
        required.add("neo4j")

    required_ready = all(checks.get(name) in _REQUIRED_HEALTHY for name in required)
    if not required_ready:
        return False, "unhealthy"

    optional_names = set(checks) - required
    optional_ready = all(checks[name] in _OPTIONAL_ACCEPTABLE for name in optional_names)
    if not optional_ready:
        return True, "degraded"

    has_optional_outage = any(checks[name] == "unavailable" for name in optional_names)
    return True, "degraded" if has_optional_outage else "healthy"


async def vector_health_check() -> str:
    try:
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1 FROM chunk_embeddings LIMIT 1"))
        return "healthy"
    except Exception:
        return "unhealthy"


async def graph_health_check() -> str:
    from mnemos.core.neo4j import check_neo4j_health

    return await check_neo4j_health()
