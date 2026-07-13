from __future__ import annotations

import time

from fastapi import Request
from redis.asyncio import Redis

from mnemos.core.config import settings
from mnemos.core.errors import AppError

_redis: Redis | None = None


def _client() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def enforce_rate_limit(request: Request, identity: str) -> None:
    if not settings.rate_limit_enabled:
        return

    bucket = int(time.time() // settings.rate_limit_window_seconds)
    key = f"rate:{identity}:{bucket}"
    client = _client()
    try:
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, settings.rate_limit_window_seconds + 1)
    except Exception:
        return

    if count > settings.rate_limit_requests:
        raise AppError(
            "RATE_LIMITED",
            "Request rate limit exceeded.",
            429,
            details={
                "limit": settings.rate_limit_requests,
                "window_seconds": settings.rate_limit_window_seconds,
            },
            retryable=True,
        )


async def close_rate_limit_client() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
