from __future__ import annotations

from sqlalchemy import text

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

    return checks
