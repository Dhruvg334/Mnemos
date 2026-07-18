"""AI Orchestrator — bridges the application layer with the runtime.

This module is responsible for:
1. Building the single canonical investigation runtime
2. Passing the authenticated request context into that runtime
3. Executing the workflow
4. Returning the AgentResponse to the caller

The orchestrator performs NO persistence.  The backend query-execution
service validates and persists the result in exactly one transaction.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.runtime.factory import build_investigation_pipeline
from mnemos.agentic.runtime.workflow import _ApprovalPendingError
from mnemos.agentic.schemas.base import AgentResponse
from mnemos.agentic.utils.logging import StructuredLogger, setup_trace
from mnemos.schemas.agent import AgentQueryRequest

logger = StructuredLogger("orchestrator")


def _build_context(request: AgentQueryRequest) -> dict[str, Any]:
    return {
        "query_id": request.query_id,
        "run_id": request.run_id,
        "organisation_id": request.organisation_id,
        "org_id": request.organisation_id,
        "site_id": request.site_id,
        "user_id": request.user_id,
        "query_type": request.query_type,
        "question": request.question,
        "mode": request.query_type,
        "permitted_asset_ids": list(request.scope.asset_ids),
        "asset_ids": list(request.scope.asset_ids),
        "permitted_document_ids": list(request.scope.document_ids),
        "document_ids": list(request.scope.document_ids),
        "permitted_document_types": list(request.scope.allowed_document_types),
        "access_classifications": list(request.scope.access_classifications),
        "membership_id": request.membership_id,
        "role": request.actor_role,
        "include_graph_context": request.options.include_graph_context,
        "include_missing_evidence": request.options.include_missing_evidence,
        "include_conflicts": request.options.include_conflicts,
    }


class MnemosAIOrchestrator:
    """High-performance AI orchestrator for industrial operations.

    Manages the execution of grounded reasoning workflows with full
    tracing and safety.  Uses the 11-stage ``InvestigationPipeline``
    as the single canonical runtime.

    Concrete agent construction and dispatch are owned by the canonical
    ``InvestigationPipeline``. The orchestrator deliberately carries no
    secondary agent registry or compatibility workflow.

    The orchestrator performs NO persistence.  It returns an
    ``AgentResponse`` and the backend service is responsible for
    validation and persistence in exactly one transaction.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # The canonical pipeline owns concrete agent construction and dispatch.
    # Keeping a second registry here previously created two competing sources
    # of truth: metadata registered by the orchestrator and classes
    # instantiated directly by InvestigationPipeline.  Production execution
    # now has one owner only.

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run_query(
        self,
        request: AgentQueryRequest,
    ) -> AgentResponse:
        """Execute the multi-agent investigation for a specific query.

        Builds the runtime state, executes the 11-stage
        ``InvestigationPipeline``, and returns the final
        ``AgentResponse``.

        This method performs NO database writes.  The caller is
        responsible for persisting the result.
        """
        trace_id = setup_trace(f"query_{request.query_id}_{uuid.uuid4().hex[:8]}")
        context = _build_context(request)
        context["trace_id"] = trace_id

        pipeline = build_investigation_pipeline(db=self.db)

        try:
            result = await pipeline.run(
                investigation_id=request.query_id,
                query=request.question,
                context=context,
            )
        except _ApprovalPendingError:
            raise

        response = result.get("final_response")
        if response is None:
            if result.get("errors"):
                raise RuntimeError(f"Workflow failed with errors: {result['errors']}")
            raise RuntimeError("Workflow terminated without a final response.")

        if isinstance(response, dict):
            return AgentResponse(**response)

        return response
