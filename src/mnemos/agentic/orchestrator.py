import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.langgraph.workflow import create_agent_workflow
from mnemos.agentic.schemas.base import AgentResponse
from mnemos.agentic.schemas.state import AgentState
from mnemos.agentic.utils.logging import StructuredLogger, setup_trace
from mnemos.schemas.agent import AgentQueryRequest

logger = StructuredLogger("orchestrator")


class MnemosAIOrchestrator:
    """
    Executes the industrial reasoning workflow without mutating backend-owned
    query, run, claim, citation, or progress tables.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.workflow = create_agent_workflow(db)

    async def run_query(self, request: AgentQueryRequest) -> AgentResponse:
        trace_id = setup_trace(
            f"query_{request.query_id}_{uuid.uuid4().hex[:8]}"
        )

        initial_state: AgentState = {
            "query": request.question,
            "context": {
                "query_id": request.query_id,
                "run_id": request.run_id,
                "site_id": request.site_id,
                "org_id": request.organisation_id,
                "user_id": request.user_id,
                "trace_id": trace_id,
                "mode": request.query_type,
                "asset_ids": list(request.scope.asset_ids),
                "document_ids": list(request.scope.document_ids),
                "allowed_document_types": list(
                    request.scope.allowed_document_types
                ),
                "access_classifications": list(
                    request.scope.access_classifications
                ),
            },
            "intent": None,
            "resolved_entities": [],
            "retrieval_plan": None,
            "evidence_bundle": None,
            "messages": [],
            "claims": [],
            "final_response": None,
            "steps_completed": [],
            "current_node": "START",
            "errors": [],
        }

        logger.info(
            f"Starting analysis for query {request.query_id}"
        )

        final_state = initial_state
        async for event in self.workflow.astream(
            initial_state,
            config={"configurable": {"thread_id": trace_id}},
        ):
            for node_name, state_update in event.items():
                if isinstance(state_update, dict):
                    final_state.update(state_update)
                logger.info(
                    f"Completed workflow node {node_name} "
                    f"for query {request.query_id}"
                )

        response = final_state.get("final_response")
        if response is not None:
            return response

        if final_state.get("errors"):
            logger.error(
                f"Workflow returned controlled errors for query "
                f"{request.query_id}"
            )
            raise RuntimeError("Agent workflow could not complete.")

        raise RuntimeError("Agent workflow ended without a response.")
