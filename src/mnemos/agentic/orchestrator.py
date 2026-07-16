import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.langgraph.workflow import create_agent_workflow
from mnemos.agentic.schemas.base import AgentResponse
from mnemos.agentic.schemas.state import AgentState
from mnemos.agentic.utils.logging import StructuredLogger, setup_trace
from mnemos.models import AgentRun, Citation, Query, QueryClaim
from mnemos.services.query_execution import add_query_event

logger = StructuredLogger("orchestrator")

class MnemosAIOrchestrator:
    """
    High-performance AI orchestrator for industrial operations.
    Manages the execution of grounded reasoning workflows with full tracing and safety.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.workflow = create_agent_workflow(db)

    async def run_query(self, query_id: str, run_id: str) -> AgentResponse:
        """
        Executes the AI workflow for a specific query.
        Updates progress in real-time and persists final grounded results.
        Fixes duplicate execution by capturing state from astream.
        """
        trace_id = setup_trace(f"query_{query_id}_{uuid.uuid4().hex[:8]}")

        query = await self.db.get(Query, query_id)
        run = await self.db.get(AgentRun, run_id)

        if not query or not run:
            logger.error(f"Execution context missing. Query: {query_id}, Run: {run_id}")
            raise ValueError("Invalid execution context.")

        initial_state: AgentState = {
            "query": query.question,
            "context": {
                "query_id": query_id,
                "run_id": run_id,
                "site_id": query.site_id,
                "org_id": query.organisation_id,
                "user_id": query.user_id,
                "trace_id": trace_id,
                "mode": query.mode
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
            "errors": []
        }

        logger.info(f"Starting analysis for: '{query.question[:50]}...'")

        try:
            # Execute workflow using astream and capture the final state
            # This avoids the double-execution of using astream followed by ainvoke
            final_state = initial_state
            async for event in self.workflow.astream(
                initial_state,
                config={"configurable": {"thread_id": trace_id}}
            ):
                for node_name, state_update in event.items():
                    # Update our local tracking of the state
                    # LangGraph astream yields chunks of the state that were updated
                    if isinstance(state_update, dict):
                        final_state.update(state_update)

                    await self._log_step_progress(query_id, node_name)

            response: AgentResponse = final_state.get("final_response")

            if not response:
                if final_state.get("errors"):
                    raise RuntimeError(f"Workflow failed with errors: {final_state['errors']}")
                raise RuntimeError("Workflow terminated without a final response.")

            # Persist result with citations and provenance
            await self._persist_final_report(query, run, response)
            return response

        except Exception as e:
            logger.error(f"Orchestration failure: {str(e)}", exc_info=True)
            await self._handle_failure(query, run, str(e))
            raise

    async def _log_step_progress(self, query_id: str, node_name: str):
        """Maps internal nodes to user-friendly progress indicators."""
        progress_map = {
            "query_router": (15, "Classifying industrial intent"),
            "entity_resolver": (25, "Locating assets in knowledge graph"),
            "retrieval_planner": (35, "Planning retrieval strategy"),
            "evidence_retrieval": (60, "Gathering grounded evidence"),
            "evidence_verification": (75, "Verifying provenance and conflicts"),
            "asset_agent": (85, "Synthesizing asset health passport"),
            "rca_agent": (85, "Investigating root causes"),
            "compliance_agent": (85, "Evaluating regulatory gaps"),
            "lessons_learned_agent": (85, "Detecting recurrence patterns"),
            "response_composer": (95, "Synthesizing final intelligence report")
        }

        if node_name in progress_map:
            percent, msg = progress_map[node_name]
            await add_query_event(self.db, query_id=query_id, stage=node_name, progress_percent=percent, message=msg)
            await self.db.commit()

    async def _persist_final_report(self, query: Query, run: AgentRun, response: AgentResponse):
        """Atomically persists the grounded response and all supporting evidence."""
        query.answer = response.answer
        query.confidence_score = response.confidence_score
        query.status = "succeeded"
        query.completed_at = datetime.now(UTC)
        query.missing_evidence = response.missing_evidence
        query.conflicts = [c.model_dump() for c in response.contradictions]

        # Persist Grounded Claims
        for c_idx, grounded_claim in enumerate(response.claims):
            claim = QueryClaim(
                query_id=query.id,
                external_id=grounded_claim.claim_id or f"clm_{c_idx}",
                text=grounded_claim.text,
                support_status=grounded_claim.status
            )
            self.db.add(claim)
            await self.db.flush()

            # Persist Citations with Provenance
            for source in grounded_claim.sources:
                citation = Citation(
                    query_id=query.id,
                    claim_id=claim.id,
                    claim_text=claim.text,
                    support_status=claim.support_status,
                    document_id=source.provenance.document_id,
                    document_title=source.provenance.source_filename,
                    document_version=source.provenance.document_version,
                    text_excerpt=source.text_excerpt,
                    page_or_sheet=source.provenance.page_number,
                    locator=source.provenance.locator,
                    evidence_region_id=source.provenance.evidence_region_id,
                    retrieval_sources=["graph_rag"],
                    access_allowed=True
                )
                self.db.add(citation)

        run.status = "succeeded"
        run.completed_at = datetime.now(UTC)

        await add_query_event(self.db, query_id=query.id, stage="completed", progress_percent=100, message="Intelligence report generated.")
        await self.db.commit()

    async def _handle_failure(self, query: Query, run: AgentRun, error_msg: str):
        query.status = "failed"
        run.status = "failed"
        run.error_message = error_msg
        run.completed_at = datetime.now(UTC)
        await add_query_event(self.db, query_id=query.id, stage="failed", progress_percent=100, message=f"Analysis failed: {error_msg}")
        await self.db.commit()
