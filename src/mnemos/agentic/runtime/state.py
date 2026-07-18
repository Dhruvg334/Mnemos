"""Shared Investigation State for the multi-agent runtime.

This module defines the LangGraph-compatible TypedDict that serves as the
single source of truth for all agents. Agents read from and write to this
state; they never communicate directly.

Uses LangGraph's functional reducers for append-only fields.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from mnemos.agentic.runtime.types import (
    AgentInvocationMetadata,
    AgentMessage,
    Checkpoint,
    InvestigationEvent,
    InvestigationPhase,
    ReplanRequest,
    SupervisorDecision,
    TerminationReason,
)


class InvestigationState(TypedDict, total=False):
    """Global investigation state shared across all agents.

    Agents communicate exclusively through this state and typed messages.
    Append-only fields use LangGraph's ``add`` reducer so that concurrent
    agents can safely append without overwriting each other.
    """

    # ---- Identity --------------------------------------------------------
    investigation_id: str
    query: str
    context: dict[str, Any]

    # ---- Phase -----------------------------------------------------------
    phase: InvestigationPhase

    # ---- Evidence & Claims -----------------------------------------------
    evidence: Annotated[list[dict[str, Any]], add]
    claims: Annotated[list[dict[str, Any]], add]

    # ---- Agent Outputs (keyed by agent name) -----------------------------
    agent_outputs: dict[str, dict[str, Any]]

    # ---- Messages --------------------------------------------------------
    messages: Annotated[list[AgentMessage], add]

    # ---- Event Log -------------------------------------------------------
    events: Annotated[list[InvestigationEvent], add]

    # ---- Checkpoints -----------------------------------------------------
    checkpoints: list[Checkpoint]
    last_checkpoint_id: str | None

    # ---- Agent Metadata (keyed by agent name) ----------------------------
    agent_metadata: dict[str, AgentInvocationMetadata]

    # ---- Supervisor -------------------------------------------------------
    supervisor_decisions: Annotated[list[SupervisorDecision], add]
    iteration: int
    max_iterations: int

    # ---- Replan ----------------------------------------------------------
    replan_requests: Annotated[list[ReplanRequest], add]

    # ---- Human Approval --------------------------------------------------
    approval_required: bool
    approval_result: dict[str, Any] | None
    pending_approval_request: dict[str, Any] | None

    # ---- Termination -----------------------------------------------------
    is_complete: bool
    should_abstain: bool
    abstention_reason: str | None
    termination_reason: TerminationReason | None

    # ---- Concurrency Control ---------------------------------------------
    pending_agents: list[str]
    completed_agents: list[str]

    # ---- Errors & Tracing ------------------------------------------------
    errors: Annotated[list[str], add]
    steps_completed: Annotated[list[str], add]
    trace_id: str | None


def create_initial_state(
    investigation_id: str,
    query: str,
    context: dict[str, Any] | None = None,
    trace_id: str | None = None,
    max_iterations: int = 10,
) -> InvestigationState:
    """Factory for a clean initial InvestigationState.

    Automatically initializes an AgentMemory instance in context["memory"]
    scoped to this investigation.
    """
    from mnemos.agentic.runtime.memory import AgentMemory

    ctx = context or {}
    if "memory" not in ctx:
        ctx["memory"] = AgentMemory(investigation_id=investigation_id)

    return InvestigationState(
        investigation_id=investigation_id,
        query=query,
        context=ctx,
        phase=InvestigationPhase.INITIALIZATION,
        evidence=[],
        claims=[],
        agent_outputs={},
        messages=[],
        events=[],
        checkpoints=[],
        last_checkpoint_id=None,
        agent_metadata={},
        supervisor_decisions=[],
        iteration=0,
        max_iterations=max_iterations,
        replan_requests=[],
        approval_required=False,
        approval_result=None,
        pending_approval_request=None,
        is_complete=False,
        should_abstain=False,
        abstention_reason=None,
        termination_reason=None,
        pending_agents=[],
        completed_agents=[],
        errors=[],
        steps_completed=[],
        trace_id=trace_id,
    )
