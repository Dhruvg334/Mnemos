from operator import add
from typing import Annotated, Any, TypedDict

from mnemos.agentic.schemas.base import (
    AgentMessage,
    AgentResponse,
    EvidenceBundle,
    GroundedClaim,
    QueryIntent,
    ResolvedEntity,
    RetrievalPlan,
)


class AgentState(TypedDict):
    """
    Main state for the agentic workflow.
    Uses LangGraph's functional state management.
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
