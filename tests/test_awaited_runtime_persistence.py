"""Tests for awaited audit, event, idempotency, and runtime commits."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from mnemos.agentic.runtime.idempotency import IdempotentNodeExecutor, NodeCompletionRegistry
from mnemos.agentic.runtime.persistence import DurableAuditLogger, DurableEventLog
from mnemos.agentic.runtime.types import EventType, InvestigationPhase
from mnemos.agentic.schemas.base import AuditAction

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_audit_entries_are_awaited_before_pending_queue_is_cleared() -> None:
    db = MagicMock()
    db.flush = AsyncMock()
    audit = DurableAuditLogger("inv_audit", db)

    audit.log(AuditAction.AGENT_INVOKED, agent_name="query_router")

    assert len(audit._pending) == 1
    await audit.flush_async()

    assert db.add.call_count == 1
    db.flush.assert_awaited_once()
    assert audit._pending == []


@pytest.mark.asyncio
async def test_events_are_awaited_before_pending_queue_is_cleared() -> None:
    db = MagicMock()
    db.flush = AsyncMock()
    events = DurableEventLog("inv_events", db)

    events.append(
        EventType.INVESTIGATION_STARTED,
        phase=InvestigationPhase.INITIALIZATION,
        data={"query": "Why did P-117 fail?"},
    )

    assert len(events._pending) == 1
    await events.flush_async()

    assert db.add.call_count == 1
    db.flush.assert_awaited_once()
    assert events._pending == []


@pytest.mark.asyncio
async def test_idempotency_completion_is_durable_before_node_returns() -> None:
    ordering: list[str] = []

    class DurableRegistry:
        async def mark_complete_async(
            self,
            idempotency_key: str,
            investigation_id: str,
            node_name: str,
        ) -> None:
            assert idempotency_key
            assert investigation_id == "inv_idempotent"
            assert node_name == "retrieval"
            ordering.append("durable")

    registry = NodeCompletionRegistry()
    registry._durable = DurableRegistry()
    executor = IdempotentNodeExecutor(registry=registry)

    async def node(state: dict[str, object]) -> dict[str, object]:
        ordering.append("node")
        return {**state, "completed": True}

    result, was_cached = await executor.execute(
        "retrieval",
        node,
        {"investigation_id": "inv_idempotent", "query": "P-117"},
    )
    ordering.append("returned")

    assert was_cached is False
    assert result["completed"] is True
    assert ordering == ["node", "durable", "returned"]


def test_runtime_gateway_commits_isolated_runtime_transaction() -> None:
    source = (ROOT / "src/mnemos/agentic/gateway.py").read_text(encoding="utf-8")

    assert source.count("await db.commit()") >= 2
    assert "await db.rollback()" in source


def test_audit_event_and_idempotency_paths_have_no_fire_and_forget_writes() -> None:
    persistence = (ROOT / "src/mnemos/agentic/runtime/persistence.py").read_text(
        encoding="utf-8"
    )
    idempotency = (ROOT / "src/mnemos/agentic/runtime/idempotency.py").read_text(
        encoding="utf-8"
    )

    assert "ensure_future(self._async_persist" not in persistence
    assert "_schedule_persist" not in persistence
    assert "await self._registry.mark_complete_async" in idempotency
