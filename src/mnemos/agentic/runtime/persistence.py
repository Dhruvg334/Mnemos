"""Durable persistence for the agentic runtime (P0 #4, P0 #5).

Provides DB-backed implementations of ``CheckpointManager``,
``AuditLogger``, and ``InvestigationEventLog`` that write through
to PostgreSQL via SQLAlchemy AsyncSession.

All durable writers are **fire-and-forget**: a failed DB write is
logged but never raises, so the pipeline can continue even if the
database is temporarily unreachable.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.runtime.audit import AuditLogger
from mnemos.agentic.runtime.checkpoint import CheckpointManager
from mnemos.agentic.runtime.events import InvestigationEventLog
from mnemos.agentic.runtime.types import Checkpoint, CheckpointMetadata, CheckpointType
from mnemos.agentic.schemas.base import AuditEntry
from mnemos.models import (
    RuntimeAuditEntry,
    RuntimeCheckpoint,
    RuntimeInvestigationEvent,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ======================================================================
# Durable Checkpoint Manager (P0 #4)
# ======================================================================


class DurableCheckpointManager(CheckpointManager):
    """Writes checkpoints to PostgreSQL in addition to in-memory storage.

    Falls back to in-memory only on DB errors so the pipeline never
    breaks due to persistence issues.
    """

    def __init__(self, investigation_id: str, db: AsyncSession) -> None:
        super().__init__(investigation_id)
        self._db = db

    def _persist(self, checkpoint: Checkpoint) -> None:
        """Persist a checkpoint to the current DB transaction."""
        try:
            self._db.add(
                RuntimeCheckpoint(
                    id=checkpoint.metadata.checkpoint_id,
                    investigation_id=checkpoint.metadata.investigation_id,
                    checkpoint_type=checkpoint.metadata.checkpoint_type.value
                    if hasattr(checkpoint.metadata.checkpoint_type, "value")
                    else str(checkpoint.metadata.checkpoint_type),
                    phase=checkpoint.metadata.phase.value
                    if hasattr(checkpoint.metadata.phase, "value")
                    else str(checkpoint.metadata.phase),
                    agent_name=checkpoint.metadata.agent_name,
                    description=checkpoint.metadata.description,
                    state_hash=checkpoint.metadata.state_hash,
                    state_snapshot=checkpoint.state_snapshot,
                    event_log_offset=checkpoint.event_log_offset,
                    version=1,
                    created_at=_utcnow(),
                )
            )
            return
        except Exception as exc:
            logger.warning(
                "DurableCheckpoint: failed to stage DB persist: %s", exc,
            )
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._async_persist(checkpoint))
            else:
                loop.run_until_complete(self._async_persist(checkpoint))
        except RuntimeError:
            # No running event loop — schedule via a new task if possible
            try:
                asyncio.get_event_loop().call_soon(
                    asyncio.ensure_future,
                    self._async_persist(checkpoint),
                )
            except Exception:
                logger.warning(
                    "DurableCheckpoint: could not schedule DB persist "
                    "(no event loop)"
                )

    async def _async_persist(self, checkpoint: Checkpoint) -> None:
        try:
            await self._db.execute(
                text(
                    """
                    INSERT INTO runtime_checkpoints
                        (id, investigation_id, checkpoint_type, phase,
                         agent_name, description, state_hash,
                         state_snapshot, event_log_offset, version,
                         created_at)
                    VALUES
                        (:id, :investigation_id, :checkpoint_type, :phase,
                         :agent_name, :description, :state_hash,
                         :state_snapshot, :event_log_offset, :version,
                         :created_at)
                    """
                ),
                {
                    "id": checkpoint.metadata.checkpoint_id,
                    "investigation_id": checkpoint.metadata.investigation_id,
                    "checkpoint_type": checkpoint.metadata.checkpoint_type.value
                    if hasattr(checkpoint.metadata.checkpoint_type, "value")
                    else str(checkpoint.metadata.checkpoint_type),
                    "phase": checkpoint.metadata.phase.value
                    if hasattr(checkpoint.metadata.phase, "value")
                    else str(checkpoint.metadata.phase),
                    "agent_name": checkpoint.metadata.agent_name,
                    "description": checkpoint.metadata.description,
                    "state_hash": checkpoint.metadata.state_hash,
                    "state_snapshot": json.dumps(
                        checkpoint.state_snapshot, default=str,
                    ),
                    "event_log_offset": checkpoint.event_log_offset,
                    "version": 1,
                    "created_at": _utcnow(),
                },
            )
            await self._db.flush()
        except Exception as exc:
            logger.warning(
                "DurableCheckpoint: failed to persist to DB: %s", exc,
            )

    def _load_all(self) -> list[Checkpoint]:
        # NOTE: synchronous fallback — callers should use load_latest_async
        return []

    async def load_latest_async(self) -> Checkpoint | None:
        """Load the most recent checkpoint from DB."""
        try:
            result = await self._db.execute(
                text(
                    """
                    SELECT id, investigation_id, checkpoint_type, phase,
                           agent_name, description, state_hash,
                           state_snapshot, event_log_offset, created_at
                    FROM runtime_checkpoints
                    WHERE investigation_id = :investigation_id
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"investigation_id": self.investigation_id},
            )
            row = result.mappings().first()
            if row is None:
                return None

            snapshot = json.loads(row["state_snapshot"])
            phase_val = row["phase"]
            cp_type_val = row["checkpoint_type"]

            metadata = CheckpointMetadata(
                investigation_id=row["investigation_id"],
                checkpoint_type=CheckpointType(cp_type_val)
                if cp_type_val in {e.value for e in CheckpointType}
                else CheckpointType.AUTOMATIC,
                phase=phase_val,
                agent_name=row["agent_name"],
                description=row["description"] or "",
                state_hash=row["state_hash"],
            )
            return Checkpoint(
                metadata=metadata,
                state_snapshot=snapshot,
                event_log_offset=row["event_log_offset"] or 0,
            )
        except Exception as exc:
            logger.warning(
                "DurableCheckpoint: failed to load from DB: %s", exc,
            )
            return None


# ======================================================================
# Durable Audit Logger (P0 #5)
# ======================================================================


class DurableAuditLogger(AuditLogger):
    """Writes audit entries to PostgreSQL in addition to in-memory.

    Each ``log()`` call creates an ``AuditEntry`` in memory (as before)
    and fires a DB insert.  DB errors are logged but never raised.
    """

    def __init__(
        self, investigation_id: str, db: AsyncSession | None = None,
    ) -> None:
        super().__init__(investigation_id)
        self._db = db

    def log(self, action: Any, **kwargs: Any) -> AuditEntry:  # noqa: ANN401
        entry = super().log(action, **kwargs)
        if self._db is not None:
            self._schedule_persist(entry)
        return entry

    def _schedule_persist(self, entry: AuditEntry) -> None:
        try:
            self._db.add(
                RuntimeAuditEntry(
                    id=entry.audit_id,
                    investigation_id=entry.investigation_id,
                    trace_id=entry.trace_id,
                    agent_name=entry.agent_name,
                    action=entry.action.value
                    if hasattr(entry.action, "value")
                    else str(entry.action),
                    tool_name=entry.tool_name,
                    resource_type=entry.resource_type,
                    resource_id=entry.resource_id,
                    input_data=entry.input_data,
                    output_data=entry.output_data,
                    guardrail_checks=[
                        c.value if hasattr(c, "value") else str(c)
                        for c in entry.guardrail_checks
                    ],
                    guardrail_verdicts=[
                        v.value if hasattr(v, "value") else str(v)
                        for v in entry.guardrail_verdicts
                    ],
                    approval_gate=entry.approval_gate,
                    approval_decision=entry.approval_decision,
                    success=entry.success,
                    error_code=None,
                    error_message=entry.error,
                    duration_ms=entry.metadata.get("duration_ms", 0.0)
                    if isinstance(entry.metadata, dict)
                    else 0.0,
                    metadata_json=entry.metadata
                    if isinstance(entry.metadata, dict)
                    else {},
                    created_at=entry.timestamp,
                )
            )
            return
        except Exception as exc:
            logger.warning(
                "DurableAuditLogger: failed to stage DB persist: %s", exc,
            )
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._async_persist(entry))
            else:
                loop.run_until_complete(self._async_persist(entry))
        except RuntimeError:
            try:
                asyncio.get_event_loop().call_soon(
                    asyncio.ensure_future,
                    self._async_persist(entry),
                )
            except Exception:
                logger.warning(
                    "DurableAuditLogger: could not schedule DB persist"
                )

    async def _async_persist(self, entry: AuditEntry) -> None:
        try:
            await self._db.execute(
                text(
                    """
                    INSERT INTO runtime_audit_entries
                        (id, investigation_id, trace_id, agent_name,
                         action, tool_name, resource_type, resource_id,
                         input_data, output_data, guardrail_checks,
                         guardrail_verdicts, approval_gate,
                         approval_decision, success, error_code,
                         error_message, duration_ms, metadata_json,
                         created_at)
                    VALUES
                        (:id, :investigation_id, :trace_id, :agent_name,
                         :action, :tool_name, :resource_type, :resource_id,
                         :input_data, :output_data, :guardrail_checks,
                         :guardrail_verdicts, :approval_gate,
                         :approval_decision, :success, :error_code,
                         :error_message, :duration_ms, :metadata_json,
                         :created_at)
                    """
                ),
                {
                    "id": entry.audit_id,
                    "investigation_id": entry.investigation_id,
                    "trace_id": entry.trace_id,
                    "agent_name": entry.agent_name,
                    "action": entry.action.value
                    if hasattr(entry.action, "value")
                    else str(entry.action),
                    "tool_name": entry.tool_name,
                    "resource_type": entry.resource_type,
                    "resource_id": entry.resource_id,
                    "input_data": json.dumps(entry.input_data, default=str),
                    "output_data": json.dumps(entry.output_data, default=str),
                    "guardrail_checks": json.dumps(
                        [c.value if hasattr(c, "value") else str(c)
                         for c in entry.guardrail_checks],
                    ),
                    "guardrail_verdicts": json.dumps(
                        [v.value if hasattr(v, "value") else str(v)
                         for v in entry.guardrail_verdicts],
                    ),
                    "approval_gate": entry.approval_gate,
                    "approval_decision": entry.approval_decision,
                    "success": entry.success,
                    "error_code": None,
                    "error_message": entry.error,
                    "duration_ms": entry.metadata.get("duration_ms", 0.0)
                    if isinstance(entry.metadata, dict)
                    else 0.0,
                    "metadata_json": json.dumps(
                        entry.metadata, default=str,
                    )
                    if isinstance(entry.metadata, dict)
                    else json.dumps({}),
                    "created_at": entry.timestamp,
                },
            )
            await self._db.flush()
        except Exception as exc:
            logger.warning(
                "DurableAuditLogger: failed to persist to DB: %s", exc,
            )


# ======================================================================
# Durable Investigation Event Log (P0 #5)
# ======================================================================


class DurableEventLog(InvestigationEventLog):
    """Writes investigation events to PostgreSQL in addition to in-memory.

    Each ``append()`` call creates an ``InvestigationEvent`` in memory
    and fires a DB insert.  DB errors are logged but never raised.
    """

    def __init__(
        self, investigation_id: str, db: AsyncSession | None = None,
    ) -> None:
        super().__init__(investigation_id)
        self._db = db

    def append(self, event_type: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        event = super().append(event_type, **kwargs)
        if self._db is not None:
            self._schedule_persist(event)
        return event

    def _schedule_persist(self, event: Any) -> None:  # noqa: ANN401
        try:
            data = event.model_dump(mode="json") if hasattr(event, "model_dump") else {}
            self._db.add(
                RuntimeInvestigationEvent(
                    id=f"revt_{uuid.uuid4().hex[:12]}",
                    investigation_id=self.investigation_id,
                    event_type=data.get("event_type", "unknown"),
                    phase=data.get("phase", "unknown"),
                    agent_name=data.get("agent_name"),
                    data_json=data.get("data", {}),
                    correlation_id=data.get("correlation_id"),
                    created_at=getattr(event, "timestamp", None) or _utcnow(),
                )
            )
            return
        except Exception as exc:
            logger.warning(
                "DurableEventLog: failed to stage DB persist: %s", exc,
            )
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._async_persist(event))
            else:
                loop.run_until_complete(self._async_persist(event))
        except RuntimeError:
            try:
                asyncio.get_event_loop().call_soon(
                    asyncio.ensure_future,
                    self._async_persist(event),
                )
            except Exception:
                logger.warning(
                    "DurableEventLog: could not schedule DB persist"
                )

    async def _async_persist(self, event: Any) -> None:  # noqa: ANN401
        try:
            data = event.model_dump(mode="json") if hasattr(event, "model_dump") else {}
            await self._db.execute(
                text(
                    """
                    INSERT INTO runtime_investigation_events
                        (id, investigation_id, event_type, phase,
                         agent_name, data_json, correlation_id,
                         created_at)
                    VALUES
                        (:id, :investigation_id, :event_type, :phase,
                         :agent_name, :data_json, :correlation_id,
                         :created_at)
                    """
                ),
                {
                    "id": f"revt_{uuid.uuid4().hex[:12]}",
                    "investigation_id": self.investigation_id,
                    "event_type": data.get("event_type", "unknown"),
                    "phase": data.get("phase", "unknown"),
                    "agent_name": data.get("agent_name"),
                    "data_json": json.dumps(data.get("data", {}), default=str),
                    "correlation_id": data.get("correlation_id"),
                    "created_at": data.get(
                        "timestamp",
                        _utcnow().isoformat(),
                    ),
                },
            )
            await self._db.flush()
        except Exception as exc:
            logger.warning(
                "DurableEventLog: failed to persist to DB: %s", exc,
            )


# ======================================================================
# Durable Node Completion Registry (P0 #22)
# ======================================================================


class DurableNodeRegistry:
    """Writes node completion records to ``runtime_investigation_events``
    so idempotency keys survive process restarts.

    Used by ``IdempotentNodeExecutor`` when a DB session is available.
    In-memory fallback is automatic on DB errors.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        # In-memory cache so same-process lookups don't hit DB every time
        self._cache: dict[str, bool] = {}

    def mark_complete(self, idempotency_key: str, investigation_id: str,
                      node_name: str) -> None:
        self._cache[idempotency_key] = True
        try:
            self._db.add(
                RuntimeInvestigationEvent(
                    id=f"revt_{uuid.uuid4().hex[:12]}",
                    investigation_id=investigation_id,
                    event_type="node_completed",
                    phase="idempotency",
                    agent_name=node_name,
                    data_json={"idempotency_key": idempotency_key,
                               "node_name": node_name},
                    created_at=_utcnow(),
                )
            )
        except Exception as exc:
            logger.warning(
                "DurableNodeRegistry: failed to persist node completion "
                "%s: %s", idempotency_key, exc
            )

    def is_complete(self, idempotency_key: str) -> bool:
        return self._cache.get(idempotency_key, False)

    async def load_completions(self, investigation_id: str) -> set[str]:
        """Load all previously completed node keys for an investigation
        from the DB — used on pipeline resume after a process restart."""
        try:
            result = await self._db.execute(
                text(
                    """
                    SELECT data_json
                    FROM runtime_investigation_events
                    WHERE investigation_id = :inv_id
                      AND event_type = 'node_completed'
                    """
                ),
                {"inv_id": investigation_id},
            )
            keys: set[str] = set()
            for row in result.mappings():
                data = row["data_json"] or {}
                if isinstance(data, str):
                    try:
                        import json as _json
                        data = _json.loads(data)
                    except Exception:
                        data = {}
                key = data.get("idempotency_key")
                if key:
                    keys.add(key)
                    self._cache[key] = True
            return keys
        except Exception as exc:
            logger.warning(
                "DurableNodeRegistry: failed to load completions for %s: %s",
                investigation_id, exc,
            )
            return set()
