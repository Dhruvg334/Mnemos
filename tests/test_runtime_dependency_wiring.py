"""Tests for explicit durable dependency wiring in the canonical runtime."""

from __future__ import annotations

from unittest.mock import MagicMock

from mnemos.agentic.runtime.approval_queue import DurableApprovalQueue
from mnemos.agentic.runtime.factory import build_investigation_pipeline
from mnemos.agentic.runtime.persistence import (
    DurableAuditLogger,
    DurableCheckpointManager,
    DurableEventLog,
    DurableNodeRegistry,
)


def test_factory_wires_all_durable_runtime_dependencies() -> None:
    db = MagicMock()

    pipeline = build_investigation_pipeline(db=db)

    assert isinstance(pipeline._approval_queue, DurableApprovalQueue)
    assert isinstance(pipeline._node_registry, DurableNodeRegistry)

    checkpoint = pipeline._create_checkpoint_manager("inv_factory")
    event_log = pipeline._create_event_log("inv_factory")
    audit_log = pipeline._create_audit_logger("inv_factory")

    assert isinstance(checkpoint, DurableCheckpointManager)
    assert isinstance(event_log, DurableEventLog)
    assert isinstance(audit_log, DurableAuditLogger)


def test_injected_dependency_factory_is_used_without_volatile_fallback() -> None:
    db = MagicMock()
    pipeline = build_investigation_pipeline(db=db)

    sentinel = object()
    pipeline._checkpoint_store = lambda investigation_id: sentinel

    try:
        pipeline._create_checkpoint_manager("inv_invalid")
    except TypeError as exc:
        assert "checkpoint_store must resolve to CheckpointManager" in str(exc)
    else:
        raise AssertionError("Invalid durable dependency must fail immediately")
