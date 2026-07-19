from __future__ import annotations

from sqlalchemy import text

from mnemos.core.config import settings
from mnemos.core.db import SessionLocal
from mnemos.core.rate_limit import _client
from mnemos.integrations.storage import S3Storage


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


async def vector_health_check() -> str:
    try:
        async with SessionLocal() as db:
            # Query the chunk_embeddings table directly
            await db.execute(text("SELECT 1 FROM chunk_embeddings LIMIT 1"))
        return "healthy"
    except Exception:
        return "unhealthy"


async def graph_health_check() -> str:
    from mnemos.core.neo4j import check_neo4j_health

    return await check_neo4j_health()
