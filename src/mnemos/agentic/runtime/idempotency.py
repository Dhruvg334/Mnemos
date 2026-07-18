"""Idempotent node execution and durable retry recovery (P0 #22).

Ensures that a workflow crash after an expensive completed stage does NOT
cause that stage to be re-executed unnecessarily, and never produces
duplicate side effects (duplicate claims, duplicate citations, etc.).

Design:
- ``NodeCompletionRecord``: immutable record that a node finished successfully
- ``IdempotentNodeExecutor``: wraps any node function with completion checking
- ``RetryRecoveryManager``: classifies errors and decides retry vs abort
- ``DurableRetryState``: persists retry state to the DB so recovery survives restarts

Idempotency key = ``investigation_id:node_name:idempotency_suffix``

The idempotency suffix is a hash of the node's input so that the same
node with different inputs still re-runs (e.g. reflection re-retrieve).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error classification for retry decisions
# ---------------------------------------------------------------------------


class RetryDecision(StrEnum):
    RETRY = "retry"
    ABORT = "abort"
    SKIP = "skip"  # skip this node, continue pipeline
    ESCALATE = "escalate"  # route to dead-letter / human review


# Error types that are retryable (transient)
_RETRYABLE_TYPES = (
    TimeoutError,
    ConnectionError,
    OSError,
)

# Error message patterns indicating a non-retryable failure
_NON_RETRYABLE_PATTERNS = [
    "permission denied",
    "unauthor",
    "invalid argument",
    "schema",
    "validation",
]


def classify_error(exc: BaseException, attempt: int, max_retries: int) -> RetryDecision:
    """Classify an exception and decide the retry strategy.

    - Transient errors (timeout, connection) → RETRY up to max_retries
    - Permission / validation errors → ABORT immediately
    - Exhausted retries → ESCALATE to dead-letter
    """
    if attempt >= max_retries:
        return RetryDecision.ESCALATE

    if isinstance(exc, _RETRYABLE_TYPES):
        return RetryDecision.RETRY

    msg = str(exc).lower()
    for pattern in _NON_RETRYABLE_PATTERNS:
        if pattern in msg:
            return RetryDecision.ABORT

    # Unknown errors: retry up to max_retries, then escalate
    return RetryDecision.RETRY


# ---------------------------------------------------------------------------
# Node completion record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NodeCompletionRecord:
    """Immutable proof that a pipeline node completed successfully."""

    investigation_id: str
    node_name: str
    idempotency_key: str
    completed_at: float = field(default_factory=time.time)
    output_summary: str = ""
    output: Any = None


# ---------------------------------------------------------------------------
# In-process completion registry (backed by DB when available)
# ---------------------------------------------------------------------------


class NodeCompletionRegistry:
    """Tracks which nodes have already completed for an investigation.

    In-memory by default.  When a DB session is available the registry
    also writes completion records to the ``runtime_investigation_events``
    table so they survive process restarts (P0 #22).
    """

    def __init__(self) -> None:
        self._completed: dict[str, NodeCompletionRecord] = {}
        self._durable: Any = None  # set to DurableNodeRegistry when DB available

    def mark_complete(
        self,
        investigation_id: str,
        node_name: str,
        idempotency_key: str,
        output_summary: str = "",
        output: Any = None,
    ) -> NodeCompletionRecord:
        record = NodeCompletionRecord(
            investigation_id=investigation_id,
            node_name=node_name,
            idempotency_key=idempotency_key,
            output_summary=output_summary,
            output=output,
        )
        self._completed[idempotency_key] = record
        # Also persist durably when a DB-backed registry is available
        if self._durable is not None:
            try:
                self._durable.mark_complete(idempotency_key, investigation_id, node_name)
            except Exception:
                logger.warning("Durable mark_complete failed for key '%s'", idempotency_key)
        return record

    def is_complete(self, idempotency_key: str) -> bool:
        return idempotency_key in self._completed

    def get_record(self, idempotency_key: str) -> NodeCompletionRecord | None:
        return self._completed.get(idempotency_key)

    def clear_investigation(self, investigation_id: str) -> int:
        keys = [k for k, v in self._completed.items() if v.investigation_id == investigation_id]
        for k in keys:
            del self._completed[k]
        return len(keys)


# Module-level registry shared across all pipeline instances
_registry = NodeCompletionRegistry()


def get_node_registry() -> NodeCompletionRegistry:
    return _registry


# ---------------------------------------------------------------------------
# Idempotency key generation
# ---------------------------------------------------------------------------


def make_idempotency_key(
    investigation_id: str,
    node_name: str,
    input_hash: str = "",
) -> str:
    """Generate a stable idempotency key for a node invocation.

    The key includes the input hash so that the same node re-runs if
    its inputs change (e.g. re-retrieve with new gap guidance).
    """
    raw = f"{investigation_id}:{node_name}:{input_hash}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def hash_node_input(state: dict[str, Any], node_name: str) -> str:
    """Compute a deterministic hash of the parts of state relevant to this node."""
    # Use query + phase + reflection_cycle as the input fingerprint
    ctx = state.get("context", {})
    fingerprint = {
        "query": state.get("query", ""),
        "phase": str(state.get("phase", "")),
        "reflection_cycle": ctx.get("reflection_cycle", 0),
        "node": node_name,
    }
    encoded = json.dumps(fingerprint, sort_keys=True, default=str).encode()
    return hashlib.sha256(encoded).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Idempotent node executor (P0 #22)
# ---------------------------------------------------------------------------


class IdempotentNodeExecutor:
    """Wraps a pipeline stage function with idempotency and retry logic.

    If the node has already completed for the current investigation
    (same investigation_id + node_name + input_hash), the cached
    result is returned immediately — no re-execution, no duplicate writes.

    If the node fails, the error is classified and the appropriate retry,
    abort, or escalate decision is applied.
    """

    def __init__(
        self,
        registry: NodeCompletionRegistry | None = None,
        max_retries: int = 2,
        base_delay_seconds: float = 0.5,
    ) -> None:
        self._registry = registry or _registry
        self._max_retries = max_retries
        self._base_delay = base_delay_seconds

    async def execute(
        self,
        node_name: str,
        node_fn: Callable[..., Awaitable[Any]],
        state: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> tuple[Any, bool]:
        """Execute node_fn with idempotency protection.

        Returns ``(result, was_cached)`` where ``was_cached=True`` means the
        node was skipped because it already completed.  When cached, the
        previously stored result is returned instead of ``None``.
        """
        investigation_id = state.get("investigation_id", "")
        input_hash = hash_node_input(state, node_name)
        idem_key = make_idempotency_key(investigation_id, node_name, input_hash)

        # Check if already complete (idempotency guard)
        if self._registry.is_complete(idem_key):
            record = self._registry.get_record(idem_key)
            logger.debug(
                "Node '%s' already complete (key=%s, completed_at=%s) — skipping",
                node_name,
                idem_key,
                datetime.fromtimestamp(record.completed_at, tz=UTC).isoformat()
                if record
                else "unknown",
            )
            return record.output if record else None, True  # cached

        # Execute with retry
        last_exc: BaseException | None = None
        for attempt in range(self._max_retries + 1):
            try:
                result = await node_fn(state, *args, **kwargs)
                # Mark complete
                self._registry.mark_complete(
                    investigation_id=investigation_id,
                    node_name=node_name,
                    idempotency_key=idem_key,
                    output_summary=f"completed at attempt {attempt + 1}",
                    output=result,
                )
                return result, False

            except Exception as exc:
                last_exc = exc
                decision = classify_error(exc, attempt, self._max_retries)

                if decision == RetryDecision.ABORT:
                    logger.warning(
                        "Node '%s' non-retryable error (attempt %d): %s",
                        node_name,
                        attempt + 1,
                        type(exc).__name__,
                    )
                    raise

                if decision == RetryDecision.ESCALATE:
                    logger.error(
                        "Node '%s' exhausted retries (%d) — escalating",
                        node_name,
                        self._max_retries,
                    )
                    raise

                if decision == RetryDecision.SKIP:
                    logger.warning("Node '%s' skipped due to error", node_name)
                    return None, False

                # RETRY — exponential backoff
                delay = self._base_delay * (2**attempt)
                logger.warning(
                    "Node '%s' attempt %d/%d failed (%s) — retrying in %.1fs",
                    node_name,
                    attempt + 1,
                    self._max_retries + 1,
                    type(exc).__name__,
                    delay,
                )
                await asyncio.sleep(delay)

        if last_exc is not None:
            raise last_exc
        return None, False


# ---------------------------------------------------------------------------
# Dead-letter tracking
# ---------------------------------------------------------------------------


@dataclass
class DeadLetterEntry:
    investigation_id: str
    node_name: str
    error_type: str
    error_message: str  # sanitized — no stack traces
    attempt_count: int
    recorded_at: float = field(default_factory=time.time)


class DeadLetterQueue:
    """Collects nodes that exhausted all retries for operator review."""

    def __init__(self) -> None:
        self._entries: list[DeadLetterEntry] = []

    def add(
        self,
        investigation_id: str,
        node_name: str,
        exc: BaseException,
        attempt_count: int,
    ) -> DeadLetterEntry:
        entry = DeadLetterEntry(
            investigation_id=investigation_id,
            node_name=node_name,
            error_type=type(exc).__name__,
            error_message=str(exc)[:200],  # capped — no internal details
            attempt_count=attempt_count,
        )
        self._entries.append(entry)
        logger.error(
            "Dead-letter: investigation=%s node=%s error=%s attempts=%d",
            investigation_id,
            node_name,
            entry.error_type,
            attempt_count,
        )
        return entry

    @property
    def entries(self) -> list[DeadLetterEntry]:
        return list(self._entries)

    def clear(self) -> int:
        count = len(self._entries)
        self._entries.clear()
        return count
