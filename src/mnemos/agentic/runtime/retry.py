"""Retry Policies and Timeout Handling for the multi-agent runtime.

Provides configurable retry strategies (fixed, exponential, linear)
and per-agent timeout enforcement.  Used by the supervisor when
dispatching agents that may fail due to transient errors.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from mnemos.agentic.runtime.types import (
    AgentRegistration,
    AgentStatus,
    RetryStrategy,
)

T = TypeVar("T")


class RetryPolicy:
    """Configurable retry policy for agent invocations."""

    def __init__(
        self,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
        max_retries: int = 2,
        base_delay_seconds: float = 1.0,
        max_delay_seconds: float = 30.0,
        jitter: bool = True,
    ) -> None:
        self.strategy = strategy
        self.max_retries = max_retries
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.jitter = jitter

    @classmethod
    def from_registration(cls, reg: AgentRegistration) -> RetryPolicy:
        return cls(
            strategy=reg.retry_strategy,
            max_retries=reg.max_retries,
        )

    def get_delay(self, attempt: int) -> float:
        if attempt <= 0:
            return 0.0

        if self.strategy == RetryStrategy.NO_RETRY:
            return 0.0

        if self.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.base_delay_seconds

        elif self.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.base_delay_seconds * attempt

        elif self.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.base_delay_seconds * (2 ** (attempt - 1))

        else:
            delay = self.base_delay_seconds

        delay = min(delay, self.max_delay_seconds)

        if self.jitter:
            import random

            delay *= 0.5 + random.random() * 0.5

        return delay

    @property
    def should_retry(self) -> bool:
        return self.strategy != RetryStrategy.NO_RETRY

    def __repr__(self) -> str:
        return (
            f"RetryPolicy(strategy={self.strategy}, "
            f"max_retries={self.max_retries}, "
            f"base_delay={self.base_delay_seconds}s)"
        )


class TimeoutManager:
    """Enforces per-agent timeouts using ``asyncio.wait_for``."""

    def __init__(self, default_timeout_seconds: float = 120.0) -> None:
        self.default_timeout_seconds = default_timeout_seconds

    def get_timeout(self, agent_registration: AgentRegistration | None) -> float:
        if agent_registration is None:
            return self.default_timeout_seconds
        return agent_registration.timeout_seconds or self.default_timeout_seconds

    async def execute_with_timeout(
        self,
        coro: Awaitable[T],
        timeout_seconds: float,
    ) -> T:
        try:
            return await asyncio.wait_for(coro, timeout=timeout_seconds)
        except TimeoutError:
            raise AgentTimeoutError(f"Agent exceeded timeout of {timeout_seconds}s") from None


class AgentTimeoutError(Exception):
    """Raised when an agent invocation exceeds its timeout."""


async def execute_with_retry(
    func: Callable[..., Awaitable[T]],
    *args: Any,
    retry_policy: RetryPolicy | None = None,
    timeout_manager: TimeoutManager | None = None,
    timeout_seconds: float | None = None,
    on_retry: Callable[[int, Exception], Awaitable[None]] | None = None,
    **kwargs: Any,
) -> tuple[T | None, AgentStatus, int]:
    """Execute an async function with retry and timeout logic.

    Returns:
        A tuple of (result, final_status, total_attempts).
    """
    if retry_policy is None:
        retry_policy = RetryPolicy()
    if timeout_manager is None:
        timeout_manager = TimeoutManager()

    last_error: Exception | None = None
    max_attempts = retry_policy.max_retries + 1 if retry_policy.should_retry else 1

    for attempt in range(1, max_attempts + 1):
        try:
            if timeout_seconds and timeout_manager:
                result = await timeout_manager.execute_with_timeout(
                    func(*args, **kwargs), timeout_seconds
                )
            else:
                result = await func(*args, **kwargs)
            return result, AgentStatus.COMPLETED, attempt

        except AgentTimeoutError:
            last_error = AgentTimeoutError(f"Timeout on attempt {attempt}/{max_attempts}")
            if attempt < max_attempts and retry_policy.should_retry:
                delay = retry_policy.get_delay(attempt)
                if on_retry:
                    await on_retry(attempt, last_error)
                await asyncio.sleep(delay)
                continue
            return None, AgentStatus.TIMEOUT, attempt

        except Exception as exc:
            last_error = exc
            if attempt < max_attempts and retry_policy.should_retry:
                delay = retry_policy.get_delay(attempt)
                if on_retry:
                    await on_retry(attempt, exc)
                await asyncio.sleep(delay)
                continue
            return None, AgentStatus.FAILED, attempt

    return None, AgentStatus.FAILED, max_attempts
