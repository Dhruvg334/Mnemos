"""Shared state definitions for the agentic workflow.

This module provides two state schemas:
1. ``AgentState`` -- the legacy TypedDict used by existing LangGraph nodes.
2. ``InvestigationState`` -- the new runtime state that supports the full
   collaborative multi-agent architecture.

Both are kept for backward compatibility; the runtime imports from
``mnemos.agentic.runtime.state`` for the canonical definition.
"""

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
from mnemos.agentic.schemas.base import (
    AgentResponse,
    EvidenceBundle,
    GroundedClaim,
    QueryIntent,
    ResolvedEntity,
    RetrievalPlan,
)


class AgentState(TypedDict, total=False):
    """Main state for the agentic workflow.

    Uses LangGraph's functional state management with ``add`` reducers
    for append-only fields.  This is the legacy state schema kept for
    backward compatibility with existing LangGraph nodes.
    """

    # The original query from the user
    query: str

    # Metadata about the user/context (site_id, org_id, trace_id)
    context: dict[str, Any]

    # Classified intent of the query
    intent: QueryIntent | None

    # Entities resolved from the query (e.g. Asset tags)
    resolved_entities: list[ResolvedEntity]

    # The dynamic plan for retrieval
    retrieval_plan: RetrievalPlan | None

    # The complete bundle of evidence retrieved
    evidence_bundle: EvidenceBundle | None

    # History of messages in the current session
    messages: Annotated[list[AgentMessage], add]

    # Extracted claims and their verification status
    claims: Annotated[list[GroundedClaim], add]

    # Final response object
    final_response: AgentResponse | None

    # List of steps completed for tracing
    steps_completed: Annotated[list[str], add]

    # Errors encountered during execution
    errors: Annotated[list[str], add]


class InvestigationStateCompat(TypedDict, total=False):
    """Extended state that bridges the legacy AgentState with the new
    runtime InvestigationState.

    New runtime nodes should prefer the full ``InvestigationState`` from
    ``mnemos.agentic.runtime.state``.  This compatibility layer allows
    existing nodes to gradually migrate.
    """

    # -- Legacy fields (from AgentState) ----------------------------------
    query: str
    context: dict[str, Any]
    intent: QueryIntent | None
    resolved_entities: list[ResolvedEntity]
    retrieval_plan: RetrievalPlan | None
    evidence_bundle: EvidenceBundle | None
    messages: Annotated[list[AgentMessage], add]
    claims: Annotated[list[GroundedClaim], add]
    final_response: AgentResponse | None
    steps_completed: Annotated[list[str], add]
    errors: Annotated[list[str], add]

    # -- New runtime fields ------------------------------------------------
    investigation_id: str
    phase: InvestigationPhase
    agent_outputs: dict[str, dict[str, Any]]
    events: Annotated[list[InvestigationEvent], add]
    checkpoints: list[Checkpoint]
    last_checkpoint_id: str | None
    agent_metadata: dict[str, AgentInvocationMetadata]
    supervisor_decisions: Annotated[list[SupervisorDecision], add]
    iteration: int
    max_iterations: int
    replan_requests: Annotated[list[ReplanRequest], add]
    approval_required: bool
    approval_result: dict[str, Any] | None
    pending_approval_request: dict[str, Any] | None
    is_complete: bool
    should_abstain: bool
    abstention_reason: str | None
    termination_reason: TerminationReason | None
    pending_agents: list[str]
    completed_agents: list[str]
    trace_id: str | None
