"""Tests for the real approval pause/resume contract."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mnemos.agentic.runtime.approval_queue import (
    ApprovalDecision,
    InMemoryApprovalQueue,
)
from mnemos.agentic.runtime.checkpoint import _serialise_state
from mnemos.agentic.runtime.workflow import InvestigationPipeline
from mnemos.agentic.schemas.specialized import FinalReport


@pytest.mark.asyncio
async def test_approved_snapshot_resumes_to_final_response() -> None:
    queue = InMemoryApprovalQueue()
    report = FinalReport(
        title="P-117 review",
        summary="Evidence supports a controlled maintenance review.",
        sections={},
        confidence_statement="Moderate confidence based on available evidence.",
        signal_value=0.8,
    )
    state = {
        "investigation_id": "qry_resume_001",
        "query": "Can this RCA be closed?",
        "context": {"final_report": report},
        "phase": "approval",
        "approval_required": True,
        "approval_result": None,
        "pending_approval_request": {},
        "evidence": [],
        "claims": [],
        "agent_outputs": {},
        "messages": [],
        "events": [],
        "checkpoints": [],
        "last_checkpoint_id": None,
        "agent_metadata": {},
        "supervisor_decisions": [],
        "iteration": 0,
        "max_iterations": 3,
        "replan_requests": [],
        "is_complete": False,
        "should_abstain": False,
        "abstention_reason": None,
        "termination_reason": None,
        "pending_agents": [],
        "completed_agents": [],
        "errors": [],
        "steps_completed": [],
        "trace_id": "trace_resume_001",
        "created_at": datetime.now(UTC),
    }

    request = await queue.submit_request(
        investigation_id="qry_resume_001",
        gate_type="rca_closure",
        state_snapshot=_serialise_state(state),
    )
    await queue.submit_decision(
        request.request_id,
        ApprovalDecision(
            decision="approve",
            reviewer="reviewer@example.com",
            comments="Approved after evidence review.",
        ),
    )

    pipeline = InvestigationPipeline(
        approval_queue=queue,
        auto_checkpoint=True,
    )
    result = await pipeline.resume_from_approval(request.request_id)

    assert result["is_complete"] is True
    assert result["final_response"].answer.startswith(
        "Evidence supports a controlled maintenance review."
    )
    assert "human_approval:approved" in result["steps_completed"]
    assert "final_response:completed" in result["steps_completed"]


def test_state_serialisation_is_recursive_and_json_safe() -> None:
    report = FinalReport(
        title="Nested model",
        summary="Nested serialization test.",
        sections={},
        confidence_statement="Test confidence.",
        signal_value=0.5,
    )
    snapshot = _serialise_state(
        {
            "context": {
                "final_report": report,
                "nested": [{"timestamp": datetime(2026, 7, 18, tzinfo=UTC)}],
            }
        }
    )

    assert snapshot["context"]["final_report"]["title"] == "Nested model"
    assert snapshot["context"]["nested"][0]["timestamp"].startswith("2026-07-18")


def test_pending_approval_result_requires_request_id() -> None:
    from pydantic import ValidationError

    from mnemos.schemas.agent import AgentQueryResult

    with pytest.raises(ValidationError):
        AgentQueryResult(run_id="run_1", status="pending_approval")

    result = AgentQueryResult(
        run_id="run_1",
        status="pending_approval",
        approval_request_id="apr_123",
    )
    assert result.approval_request_id == "apr_123"
