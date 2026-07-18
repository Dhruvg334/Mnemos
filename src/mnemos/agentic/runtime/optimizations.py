"""Production Optimizations for the multi-agent runtime.

Provides caching, batching, parallel execution control, and timeout
recovery strategies that plug into the workflow pipeline to improve
throughput and resilience under load.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import Any

from mnemos.agentic.config import AgenticSettings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash_cache_key(tool_name: str, arguments: dict[str, Any]) -> str:
    """Deterministic cache key from tool name + serialized arguments."""
    canonical = json.dumps(arguments, sort_keys=True, default=str)
    digest = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    return f"{tool_name}:{digest}"


# ---------------------------------------------------------------------------
# ResponseCache
# ---------------------------------------------------------------------------


class ResponseCache:
    """LRU cache for MCP tool call results with TTL expiration.

    Stores results keyed by tool name and serialized arguments.  Entries
    automatically expire after their TTL and the LRU policy evicts the
    oldest entry when the cache is full.
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl_seconds: float = 300.0,
    ) -> None:
        self._max_size = max_size
        self._default_ttl = default_ttl_seconds
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    # -- public API --------------------------------------------------------

    def get(self, tool_name: str, arguments: dict[str, Any]) -> Any | None:
        """Return cached result if valid, None otherwise.

        Lookup moves the entry to the end of the LRU ordering.  Expired
        entries are evicted on access.
        """
        key = _hash_cache_key(tool_name, arguments)
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None

        result, expires_at = entry
        if time.monotonic() > expires_at:
            self._store.pop(key, None)
            self._misses += 1
            return None

        self._store.move_to_end(key)
        self._hits += 1
        return result

    def put(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: Any,
        ttl_seconds: float | None = None,
    ) -> None:
        """Store a result in the cache.

        If the cache is full the least-recently-used entry is evicted.
        An explicit *ttl_seconds* overrides the default TTL for this entry.
        """
        key = _hash_cache_key(tool_name, arguments)
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        if ttl <= 0:
            expires_at = 0.0
        else:
            expires_at = time.monotonic() + ttl

        if key in self._store:
            self._store.move_to_end(key)
        elif len(self._store) >= self._max_size:
            self._store.popitem(last=False)

        self._store[key] = (result, expires_at)

    def invalidate(self, tool_name: str | None = None) -> int:
        """Invalidate cache entries.

        When *tool_name* is provided only entries for that tool are
        removed.  Otherwise every entry is cleared.  Returns the count
        of invalidated entries.
        """
        if tool_name is None:
            count = len(self._store)
            self._store.clear()
            return count

        keys_to_remove = [k for k in self._store if k.startswith(f"{tool_name}:")]
        for k in keys_to_remove:
            self._store.pop(k, None)
        return len(keys_to_remove)

    def stats(self) -> dict[str, Any]:
        """Return cache statistics: hits, misses, size, hit_rate."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._store),
            "max_size": self._max_size,
            "hit_rate": round(hit_rate, 4),
        }

    def cleanup(self) -> int:
        """Remove expired entries.  Returns count of removed entries."""
        now = time.monotonic()
        expired_keys = [k for k, (_, expires_at) in self._store.items() if now > expires_at]
        for k in expired_keys:
            self._store.pop(k, None)
        return len(expired_keys)


# ---------------------------------------------------------------------------
# BatchRetrievalManager
# ---------------------------------------------------------------------------


class _PendingRequest:
    """Internal bookkeeping for a single request waiting inside a batch."""

    __slots__ = ("request_id", "query", "strategy", "parameters", "future")

    def __init__(
        self,
        request_id: str,
        query: str,
        strategy: str,
        parameters: dict[str, Any],
        future: asyncio.Future[Any],
    ) -> None:
        self.request_id = request_id
        self.query = query
        self.strategy = strategy
        self.parameters = parameters
        self.future = future


class BatchRetrievalManager:
    """Batches multiple retrieval requests for efficiency.

    Incoming requests are queued until either *max_batch_size* is
    reached or *max_wait_seconds* elapses (whichever comes first), at
    which point the batch is flushed and each caller receives the
    result matching its request_id.
    """

    def __init__(
        self,
        max_batch_size: int = 10,
        max_wait_seconds: float = 0.1,
    ) -> None:
        self._max_batch_size = max_batch_size
        self._max_wait = max_wait_seconds
        self._pending: list[_PendingRequest] = []
        self._flush_lock = asyncio.Lock()
        self._flush_task: asyncio.Task[None] | None = None
        self._batch_fn: Callable[[list[_PendingRequest]], Awaitable[dict[str, Any]]] | None = None

    def set_batch_handler(
        self,
        handler: Callable[[list[_PendingRequest]], Awaitable[dict[str, Any]]],
    ) -> None:
        """Register the callable that executes a full batch.

        The handler receives a list of ``_PendingRequest`` objects and
        must return a dict mapping ``request_id`` -> result.
        """
        self._batch_fn = handler

    async def add_request(
        self,
        request_id: str,
        query: str,
        strategy: str,
        parameters: dict[str, Any],
    ) -> Any:
        """Add a retrieval request to the batch.  Returns when batch is executed."""
        future: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
        req = _PendingRequest(request_id, query, strategy, parameters, future)

        async with self._flush_lock:
            self._pending.append(req)

            if len(self._pending) >= self._max_batch_size:
                await self._flush_internal()
            elif self._flush_task is None or self._flush_task.done():
                self._flush_task = asyncio.ensure_future(self._delayed_flush())

        return await future

    async def _delayed_flush(self) -> None:
        await asyncio.sleep(self._max_wait)
        async with self._flush_lock:
            if self._pending:
                await self._flush_internal()

    async def flush(self) -> dict[str, Any]:
        """Execute all pending requests as a batch."""
        async with self._flush_lock:
            return await self._flush_internal()

    async def _flush_internal(self) -> dict[str, Any]:
        """Internal flush -- caller must hold *_flush_lock*."""
        if not self._pending:
            return {}

        batch = list(self._pending)
        self._pending.clear()

        results: dict[str, Any] = {}
        if self._batch_fn is not None:
            try:
                results = await self._batch_fn(batch)
            except Exception as exc:
                for req in batch:
                    if not req.future.done():
                        req.future.set_exception(exc)
                return results

        for req in batch:
            if not req.future.done():
                value = results.get(req.request_id)
                req.future.set_result(value)

        return results

    def pending_count(self) -> int:
        """Number of pending requests."""
        return len(self._pending)


# ---------------------------------------------------------------------------
# ParallelExecutor
# ---------------------------------------------------------------------------


class ParallelExecutor:
    """Manages parallel agent execution with concurrency limits.

    Uses :class:`asyncio.Semaphore` to cap the number of simultaneously
    executing tasks and per-agent semaphores to respect per-agent
    concurrency limits.
    """

    def __init__(
        self,
        max_concurrent: int = 5,
        max_per_agent: int = 2,
    ) -> None:
        self._max_concurrent = max_concurrent
        self._max_per_agent = max_per_agent
        self._global_semaphore = asyncio.Semaphore(max_concurrent)
        self._agent_semaphores: dict[str, asyncio.Semaphore] = {}
        self._active = 0
        self._total_completed = 0
        self._total_failed = 0
        self._total_time_ms = 0.0

    def _get_agent_semaphore(self, agent_name: str) -> asyncio.Semaphore:
        if agent_name not in self._agent_semaphores:
            self._agent_semaphores[agent_name] = asyncio.Semaphore(
                self._max_per_agent,
            )
        return self._agent_semaphores[agent_name]

    async def execute_parallel(
        self,
        tasks: list[tuple[str, Callable, tuple, dict]],
    ) -> dict[str, Any]:
        """Execute multiple agent tasks in parallel with concurrency control.

        Each element of *tasks* is ``(task_name, callable, args, kwargs)``.
        Returns ``{task_name: result}``.  Failed tasks store the exception
        instance as their value instead of a return value.
        """
        results: dict[str, Any] = {}

        async def _run_one(
            name: str,
            fn: Callable,
            fn_args: tuple,
            fn_kwargs: dict[str, Any],
        ) -> None:
            nonlocal results
            agent_sem = self._get_agent_semaphore(name)
            async with self._global_semaphore:
                async with agent_sem:
                    self._active += 1
                    start = time.monotonic()
                    try:
                        value = await fn(*fn_args, **fn_kwargs)
                        results[name] = value
                        self._total_completed += 1
                    except Exception as exc:
                        results[name] = exc
                        self._total_failed += 1
                    finally:
                        elapsed = (time.monotonic() - start) * 1000
                        self._total_time_ms += elapsed
                        self._active -= 1

        coros = [_run_one(name, fn, args, kwargs) for name, fn, args, kwargs in tasks]
        await asyncio.gather(*coros, return_exceptions=True)
        return results

    def active_count(self) -> int:
        """Number of currently executing tasks."""
        return self._active

    def stats(self) -> dict[str, Any]:
        """Return execution statistics."""
        total = self._total_completed + self._total_failed
        avg_ms = self._total_time_ms / total if total > 0 else 0.0
        return {
            "active": self._active,
            "max_concurrent": self._max_concurrent,
            "max_per_agent": self._max_per_agent,
            "total_completed": self._total_completed,
            "total_failed": self._total_failed,
            "total_time_ms": round(self._total_time_ms, 2),
            "avg_time_ms": round(avg_ms, 2),
        }


# ---------------------------------------------------------------------------
# TimeoutRecoveryManager
# ---------------------------------------------------------------------------


class _TimeoutRecord:
    __slots__ = ("agent_name", "timestamp", "partial_result")

    def __init__(
        self,
        agent_name: str,
        timestamp: float,
        partial_result: Any | None,
    ) -> None:
        self.agent_name = agent_name
        self.timestamp = timestamp
        self.partial_result = partial_result


class TimeoutRecoveryManager:
    """Handles agent timeout with graceful degradation.

    Tracks per-agent timeout history and supports two recovery
    strategies:

    * **skip_and_continue** -- discard the timed-out agent's partial
      work and proceed with remaining agents.
    * **retry_with_shorter_timeout** -- retry the agent once with a
      reduced timeout (50 % of the original).

    Escalation triggers after 3 consecutive timeouts for the same
    agent.
    """

    _ESCALATION_THRESHOLD = 3
    _TIMEOUT_WINDOW_SECONDS = 600.0

    def __init__(self, recovery_strategy: str = "skip_and_continue") -> None:
        self._strategy = recovery_strategy
        self._history: list[_TimeoutRecord] = []

    async def handle_timeout(
        self,
        agent_name: str,
        state: dict[str, Any],
        partial_result: Any | None = None,
    ) -> dict[str, Any]:
        """Handle a timeout event.  May return partial state or trigger recovery."""
        self._history.append(
            _TimeoutRecord(
                agent_name=agent_name,
                timestamp=time.monotonic(),
                partial_result=partial_result,
            )
        )

        if self._strategy == "retry_with_shorter_timeout" and not self.should_escalate(agent_name):
            state["pending_agents"] = list(state.get("pending_agents", []))
            if agent_name not in state["pending_agents"]:
                state["pending_agents"].append(agent_name)
            state.setdefault("_timeout_retries", {})
            retry_count = state["_timeout_retries"].get(agent_name, 0)
            state["_timeout_retries"][agent_name] = retry_count + 1
            state.setdefault("errors", []).append(
                f"TIMEOUT_RETRY: {agent_name} (attempt {retry_count + 1})"
            )
            return state

        state.setdefault("errors", []).append(f"TIMEOUT_SKIPPED: {agent_name}")

        pending = list(state.get("pending_agents", []))
        if agent_name in pending:
            pending.remove(agent_name)
        state["pending_agents"] = pending

        if partial_result is not None and isinstance(partial_result, dict):
            for key, value in partial_result.items():
                if key in state and isinstance(state[key], list) and isinstance(value, list):
                    state[key].extend(value)
                elif key in state and isinstance(state[key], dict) and isinstance(value, dict):
                    state[key].update(value)
                else:
                    state[key] = value

        return state

    def get_timeout_history(self) -> list[dict[str, Any]]:
        """Return history of timeout events."""
        return [
            {
                "agent_name": rec.agent_name,
                "timestamp": rec.timestamp,
                "has_partial_result": rec.partial_result is not None,
            }
            for rec in self._history
        ]

    def should_escalate(self, agent_name: str) -> bool:
        """Determine if repeated timeouts warrant escalation.

        Returns ``True`` when the agent has timed out >= 3 times within
        the rolling window.
        """
        now = time.monotonic()
        recent = [
            rec
            for rec in self._history
            if rec.agent_name == agent_name and (now - rec.timestamp) < self._TIMEOUT_WINDOW_SECONDS
        ]
        return len(recent) >= self._ESCALATION_THRESHOLD


# ---------------------------------------------------------------------------
# ProductionOptimizer  (unified facade)
# ---------------------------------------------------------------------------


class ProductionOptimizer:
    """Unified production optimizer combining all optimization strategies.

    Instantiate once and pass to workflow nodes that need caching,
    batching, parallel control, or timeout recovery.
    """

    def __init__(self, config: AgenticSettings | None = None) -> None:
        self._config = config
        self._cache = ResponseCache(
            max_size=1000,
            default_ttl_seconds=300.0,
        )
        self._batch_manager = BatchRetrievalManager(
            max_batch_size=10,
            max_wait_seconds=0.1,
        )
        self._parallel_executor = ParallelExecutor(
            max_concurrent=5,
            max_per_agent=2,
        )
        self._timeout_recovery = TimeoutRecoveryManager(
            recovery_strategy="skip_and_continue",
        )

    @property
    def cache(self) -> ResponseCache:
        """Access the response cache."""
        return self._cache

    @property
    def batch_manager(self) -> BatchRetrievalManager:
        """Access the batch retrieval manager."""
        return self._batch_manager

    @property
    def parallel_executor(self) -> ParallelExecutor:
        """Access the parallel executor."""
        return self._parallel_executor

    @property
    def timeout_recovery(self) -> TimeoutRecoveryManager:
        """Access the timeout recovery manager."""
        return self._timeout_recovery

    def get_optimization_report(self) -> dict[str, Any]:
        """Return combined statistics from all optimizers."""
        return {
            "cache": self._cache.stats(),
            "batch": {
                "pending_requests": self._batch_manager.pending_count(),
            },
            "parallel": self._parallel_executor.stats(),
            "timeout_recovery": {
                "strategy": self._timeout_recovery._strategy,
                "total_timeouts": len(self._timeout_recovery.get_timeout_history()),
                "history": self._timeout_recovery.get_timeout_history(),
            },
        }

    async def cleanup(self) -> None:
        """Run cleanup across all optimizers (cache eviction, etc.)."""
        self._cache.cleanup()
        await self._batch_manager.flush()
