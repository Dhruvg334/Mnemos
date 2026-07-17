"""AI Orchestrator -- bridges the application layer with the runtime.

This module is responsible for:
1. Loading investigation context from the database
2. Building the runtime workflow with registered agents
3. Executing the workflow
4. Persisting results back to the database

It delegates all orchestration decisions to the runtime's
``SupervisorAgent`` and ``create_investigation_workflow``.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.runtime import (
    AgentCapability,
    AgentRegistration,
    AgentRegistry,
    AgentRole,
    RetryStrategy,
    create_initial_state,
    create_investigation_workflow,
)
from mnemos.agentic.schemas.base import AgentResponse
from mnemos.agentic.utils.logging import StructuredLogger, setup_trace
from mnemos.models import AgentRun, Citation, Query, QueryClaim
from mnemos.services.query_execution import add_query_event

logger = StructuredLogger("orchestrator")


class MnemosAIOrchestrator:
    """High-performance AI orchestrator for industrial operations.

    Manages the execution of grounded reasoning workflows with full
    tracing and safety.  Uses the new multi-agent runtime for
    supervisor-driven, collaborative execution.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._agent_functions: dict[str, Callable[..., Awaitable[dict[str, Any]]]] = {}
        self._registry = AgentRegistry()

    # ------------------------------------------------------------------
    # Agent registration
    # ------------------------------------------------------------------

    def register_agent(
        self,
        name: str,
        fn: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
        *,
        role: AgentRole = AgentRole.GENERIC,
        capabilities: list[AgentCapability] | None = None,
        max_retries: int = 2,
        timeout_seconds: float = 120.0,
        retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
        can_run_in_parallel: bool = True,
        requires_human_approval: bool = False,
    ) -> None:
        """Register an agent function with the runtime."""
        self._agent_functions[name] = fn
        self._registry.register(AgentRegistration(
            name=name,
            role=role,
            capabilities=capabilities or [],
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            retry_strategy=retry_strategy,
            can_run_in_parallel=can_run_in_parallel,
            requires_human_approval=requires_human_approval,
        ))

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run_query(self, query_id: str, run_id: str) -> AgentResponse:
        """Execute the multi-agent investigation for a specific query.

        Updates progress in real-time and persists final grounded results.
        """
        trace_id = setup_trace(f"query_{query_id}_{uuid.uuid4().hex[:8]}")

        query = await self.db.get(Query, query_id)
        run = await self.db.get(AgentRun, run_id)

        if not query or not run:
            logger.error(f"Execution context missing. Query: {query_id}, Run: {run_id}")
            raise ValueError("Invalid execution context.")

        # Build initial state
        initial_state = create_initial_state(
            investigation_id=query_id,
            query=query.question,
            context={
                "query_id": query_id,
                "run_id": run_id,
                "site_id": query.site_id,
                "org_id": query.organisation_id,
                "user_id": query.user_id,
                "trace_id": trace_id,
                "mode": query.mode,
            },
            trace_id=trace_id,
        )

        logger.info(f"Starting investigation for: '{query.question[:50]}...'")

        try:
            # Build the workflow with registered agents
            workflow = create_investigation_workflow(
                agent_registry=self._registry,
                agent_functions=self._agent_functions,
            )

            compiled = workflow.compile()

            # Execute using astream to capture progress
            final_state = dict(initial_state)
            async for event in compiled.astream(
                initial_state,
                config={"configurable": {"thread_id": trace_id}},
            ):
                for node_name, state_update in event.items():
                    if isinstance(state_update, dict):
                        final_state.update(state_update)
                    await self._log_step_progress(query_id, node_name)

            # Extract response
            response = self._extract_response(final_state)

            if not response:
                if final_state.get("errors"):
                    raise RuntimeError(
                        f"Workflow failed with errors: {final_state['errors']}"
                    )
                raise RuntimeError("Workflow terminated without a final response.")

            # Persist result
            await self._persist_final_report(query, run, response)
            return response

        except Exception as e:
            logger.error(f"Orchestration failure: {str(e)}", exc_info=True)
            await self._handle_failure(query, run, str(e))
            raise

    # ------------------------------------------------------------------
    # Response extraction
    # ------------------------------------------------------------------

    def _extract_response(self, state: dict[str, Any]) -> AgentResponse | None:
        """Extract the final response from the investigation state.

        Looks for a ``final_response`` in the state, or constructs one
        from agent outputs if not explicitly set.
        """
        final = state.get("final_response")
        if final is not None:
            if isinstance(final, AgentResponse):
                return final
            if isinstance(final, dict):
                return AgentResponse(**final)

        # Construct from agent outputs
        agent_outputs = state.get("agent_outputs", {})
        evidence = state.get("evidence", [])
        claims = state.get("claims", [])

        if not agent_outputs and not evidence and not claims:
            return None

        # Find the composition agent's output
        composition_output = agent_outputs.get("composition_agent", {})
        if composition_output:
            return AgentResponse(
                answer=composition_output.get("answer", ""),
                confidence_score=composition_output.get("confidence", 0.0),
                claims=claims if isinstance(claims, list) else [],
                missing_evidence=composition_output.get("missing_evidence", []),
                metadata={"trace_id": state.get("trace_id")},
            )

        # Fallback: aggregate all agent outputs
        parts = []
        total_confidence = 0.0
        count = 0
        for _name, output in agent_outputs.items():
            if isinstance(output, dict):
                if "answer" in output:
                    parts.append(output["answer"])
                if "confidence" in output:
                    total_confidence += output["confidence"]
                    count += 1

        avg_confidence = total_confidence / count if count else 0.0

        return AgentResponse(
            answer="\n\n".join(parts) if parts else "Investigation completed.",
            confidence_score=avg_confidence,
            claims=claims if isinstance(claims, list) else [],
            metadata={"trace_id": state.get("trace_id")},
        )

    # ------------------------------------------------------------------
    # Progress
    # ------------------------------------------------------------------

    async def _log_step_progress(self, query_id: str, node_name: str) -> None:
        progress_map = {
            "supervisor": (10, "Supervisor planning next action"),
            "gather": (50, "Executing agents"),
            "reflection": (75, "Reflecting on investigation quality"),
            "approval": (80, "Awaiting human approval"),
            "checkpoint": (95, "Saving checkpoint"),
        }
        if node_name in progress_map:
            percent, msg = progress_map[node_name]
            await add_query_event(
                self.db, query_id=query_id,
                stage=node_name, progress_percent=percent, message=msg,
            )
            await self.db.commit()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def _persist_final_report(
        self, query: Query, run: AgentRun, response: AgentResponse
    ) -> None:
        query.answer = response.answer
        query.confidence_score = response.confidence_score
        query.status = "succeeded"
        query.completed_at = datetime.now(UTC)
        query.missing_evidence = response.missing_evidence
        query.conflicts = [c.model_dump() for c in response.contradictions]

        for c_idx, grounded_claim in enumerate(response.claims):
            claim = QueryClaim(
                query_id=query.id,
                external_id=grounded_claim.claim_id or f"clm_{c_idx}",
                text=grounded_claim.text,
                support_status=grounded_claim.status,
            )
            self.db.add(claim)
            await self.db.flush()

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
                    access_allowed=True,
                )
                self.db.add(citation)

        run.status = "succeeded"
        run.completed_at = datetime.now(UTC)

        await add_query_event(
            self.db, query_id=query.id,
            stage="completed", progress_percent=100,
            message="Intelligence report generated.",
        )
        await self.db.commit()

    async def _handle_failure(
        self, query: Query, run: AgentRun, error_msg: str
    ) -> None:
        query.status = "failed"
        run.status = "failed"
        run.error_message = error_msg
        run.completed_at = datetime.now(UTC)
        await add_query_event(
            self.db, query_id=query.id,
            stage="failed", progress_percent=100,
            message=f"Analysis failed: {error_msg}",
        )
        await self.db.commit()
