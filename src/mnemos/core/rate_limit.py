from __future__ import annotations

import hashlib
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


async def _enforce(identity: str, scope: str, limit: int, window_seconds: int) -> None:
    if not settings.rate_limit_enabled:
        return
    digest = hashlib.sha256(identity.encode()).hexdigest()
    bucket = int(time.time() // window_seconds)
    key = f"rate:{scope}:{digest}:{bucket}"
    try:
        count = await _client().incr(key)
        if count == 1:
            await _client().expire(key, window_seconds + 1)
    except Exception as exc:
        if settings.rate_limit_fail_closed:
            raise AppError(
                "RATE_LIMIT_UNAVAILABLE",
                "Request throttling is temporarily unavailable.",
                503,
                retryable=True,
            ) from exc
        return
    if count > limit:
        retry_after = window_seconds - (int(time.time()) % window_seconds)
        raise AppError(
            "RATE_LIMITED",
            "Request rate limit exceeded.",
            429,
            details={
                "limit": limit,
                "window_seconds": window_seconds,
                "retry_after_seconds": retry_after,
            },
            retryable=True,
        )


async def enforce_rate_limit(request: Request, identity: str) -> None:
    await _enforce(
        identity, "authenticated", settings.rate_limit_requests, settings.rate_limit_window_seconds
    )


async def enforce_public_rate_limit(
    request: Request, identity: str, *, limit: int, window_seconds: int
) -> None:
    await _enforce(identity, f"public:{request.url.path}", limit, window_seconds)


async def close_rate_limit_client() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
