"""Canonical construction root for the Mnemos investigation runtime.

Every production caller builds the agentic runtime through this module so
checkpointing, audit, events, approvals, and idempotency use the same durable
dependency graph.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.runtime.approval_queue import DurableApprovalQueue
from mnemos.agentic.runtime.persistence import (
    DurableAuditLogger,
    DurableCheckpointManager,
    DurableEventLog,
    DurableNodeRegistry,
)
from mnemos.agentic.runtime.workflow import InvestigationPipeline
from mnemos.core.db import SessionLocal


def build_investigation_pipeline(*, db: AsyncSession) -> InvestigationPipeline:
    """Build the single production investigation pipeline.

    The request-scoped database session is used for runtime checkpoint, audit,
    event, and idempotency records. Approval requests use ``SessionLocal`` so
    they are committed independently before the workflow returns a pending
    approval response.
    """

    return InvestigationPipeline(
        db=db,
        checkpoint_store=lambda investigation_id: DurableCheckpointManager(
            investigation_id,
            db,
        ),
        event_store=lambda investigation_id: DurableEventLog(
            investigation_id,
            db,
        ),
        audit_sink=lambda investigation_id: DurableAuditLogger(
            investigation_id,
            db,
        ),
        approval_queue=DurableApprovalQueue(session_factory=SessionLocal),
        node_registry=DurableNodeRegistry(db),
    )
