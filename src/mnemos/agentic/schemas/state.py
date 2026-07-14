from typing import Annotated, Any, Dict, List, Optional, TypedDict, Union
from operator import add

from mnemos.agentic.schemas.base import (
    AgentMessage,
    GroundedClaim,
    AgentResponse,
    QueryIntent,
    RetrievalPlan,
    ResolvedEntity,
    EvidenceBundle
)


class AgentState(TypedDict):
    """
    Main state for the agentic workflow.
    Uses LangGraph's functional state management.
    """
    # The original query from the user
    query: str

    # Metadata about the user/context (site_id, org_id, trace_id)
    context: Dict[str, Any]

    # Classified intent of the query
    intent: QueryIntent | None

    # Entities resolved from the query (e.g. Asset tags)
    resolved_entities: List[ResolvedEntity]

    # The dynamic plan for retrieval
    retrieval_plan: RetrievalPlan | None

    # The complete bundle of evidence retrieved
    evidence_bundle: EvidenceBundle | None

    # History of messages in the current session
    messages: Annotated[List[AgentMessage], add]

    # Extracted claims and their verification status
    claims: Annotated[List[GroundedClaim], add]

    # Final response object
    final_response: AgentResponse | None

    # List of steps completed for tracing
    steps_completed: Annotated[List[str], add]

    # Errors encountered during execution
    errors: Annotated[List[str], add]
