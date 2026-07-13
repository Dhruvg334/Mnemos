from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from mnemos.core.errors import AppError

T = TypeVar("T")


async def retry_async(
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int,
    base_delay_seconds: float,
) -> tuple[T, int]:
    attempts = max(1, attempts)
    last_error: Exception | None = None

    for attempt in range(attempts):
        try:
            return await operation(), attempt
        except AppError as exc:
            last_error = exc
            if not exc.retryable or attempt == attempts - 1:
                raise
        except Exception as exc:
            last_error = exc
            if attempt == attempts - 1:
                raise

        await asyncio.sleep(base_delay_seconds * (2**attempt))

    assert last_error is not None
    raise last_error
