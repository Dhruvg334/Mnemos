"""AI Orchestrator — bridges the application layer with the runtime.

This module is responsible for:
1. Instantiating and registering all agents
2. Building the runtime workflow with registered agents
3. Executing the workflow
4. Returning the AgentResponse to the caller

The orchestrator performs NO persistence.  The backend query-execution
service validates and persists the result in exactly one transaction.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.runtime import (
    AgentCapability,
    AgentRegistration,
    AgentRegistry,
    AgentRole,
    InvestigationPipeline,
    RetryStrategy,
)
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
        "role": "engineer",
        "include_graph_context": request.options.include_graph_context,
        "include_missing_evidence": request.options.include_missing_evidence,
        "include_conflicts": request.options.include_conflicts,
    }


class MnemosAIOrchestrator:
    """High-performance AI orchestrator for industrial operations.

    Manages the execution of grounded reasoning workflows with full
    tracing and safety.  Uses the 11-stage ``InvestigationPipeline``
    as the single canonical runtime.

    On initialisation the orchestrator eagerly instantiates every
    available agent (retrieval + reasoning) and registers it with the
    runtime so that ``run_query`` can dispatch work immediately.

    The orchestrator performs NO persistence.  It returns an
    ``AgentResponse`` and the backend service is responsible for
    validation and persistence in exactly one transaction.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._agent_functions: dict[str, Callable[..., Awaitable[dict[str, Any]]]] = {}
        self._registry = AgentRegistry()
        self._register_all_agents()

    # ------------------------------------------------------------------
    # Production agent registration
    # ------------------------------------------------------------------

    def _register_all_agents(self) -> None:
        """Register every production agent with the runtime.

        All retrieval and reasoning agents are registered eagerly so
        that the orchestrator can dispatch work without additional
        configuration.
        """
        agent_defs: list[dict[str, Any]] = [
            {
                "name": "query_router",
                "role": AgentRole.RETRIEVAL,
                "capabilities": [
                    AgentCapability(
                        name="query_classification",
                        description="Classify query intent and extract entities",
                        output_types=["intent", "entities"],
                    )
                ],
                "max_retries": 2,
                "timeout_seconds": 60.0,
                "retry_strategy": RetryStrategy.EXPONENTIAL_BACKOFF,
                "can_run_in_parallel": False,
            },
            {
                "name": "retrieval_planner",
                "role": AgentRole.RETRIEVAL,
                "capabilities": [
                    AgentCapability(
                        name="retrieval_planning",
                        description="Build retrieval plan with strategies and filters",
                        output_types=["retrieval_plan"],
                    )
                ],
            },
            {
                "name": "evidence_retrieval",
                "role": AgentRole.RETRIEVAL,
                "capabilities": [
                    AgentCapability(
                        name="evidence_retrieval",
                        description="Execute retrieval plan via HybridRetrievalEngine",
                        output_types=["evidence"],
                    )
                ],
            },
            {
                "name": "evidence_verification",
                "role": AgentRole.VERIFICATION,
                "capabilities": [
                    AgentCapability(
                        name="evidence_verification",
                        description="Verify evidence provenance, citations, confidence",
                        output_types=["verified_evidence", "citations"],
                    )
                ],
            },
            {
                "name": "retrieval_reflection",
                "role": AgentRole.REFLECTION,
                "capabilities": [
                    AgentCapability(
                        name="retrieval_reflection",
                        description="Evaluate evidence sufficiency and identify gaps",
                        output_types=["reflection_decision", "gaps"],
                    )
                ],
            },
            {
                "name": "rca_agent",
                "role": AgentRole.ANALYSIS,
                "capabilities": [
                    AgentCapability(
                        name="rca",
                        description="Root cause analysis of failures",
                        input_types=["evidence"],
                        output_types=["rca_findings", "recommended_actions"],
                    )
                ],
            },
            {
                "name": "compliance_agent",
                "role": AgentRole.ANALYSIS,
                "capabilities": [
                    AgentCapability(
                        name="compliance",
                        description="Regulatory and standards compliance checking",
                        input_types=["evidence"],
                        output_types=["compliance_results"],
                    )
                ],
            },
            {
                "name": "asset_intelligence",
                "role": AgentRole.ANALYSIS,
                "capabilities": [
                    AgentCapability(
                        name="asset_intelligence",
                        description="Asset maintenance and performance intelligence",
                        input_types=["evidence"],
                        output_types=["asset_insights"],
                    )
                ],
            },
            {
                "name": "lessons_learned_agent",
                "role": AgentRole.ANALYSIS,
                "capabilities": [
                    AgentCapability(
                        name="lessons_learned",
                        description="Historical lessons learned retrieval",
                        input_types=["evidence"],
                        output_types=["lessons"],
                    )
                ],
            },
            {
                "name": "expert_knowledge_agent",
                "role": AgentRole.ANALYSIS,
                "capabilities": [
                    AgentCapability(
                        name="expert_knowledge",
                        description="Expert knowledge retrieval and reasoning",
                        input_types=["evidence"],
                        output_types=["expert_insights"],
                    )
                ],
            },
            {
                "name": "report_composer",
                "role": AgentRole.COMPOSITION,
                "capabilities": [
                    AgentCapability(
                        name="report_composition",
                        description="Synthesize all outputs into FinalReport",
                        input_types=["evidence", "reasoning_outputs"],
                        output_types=["final_report"],
                    )
                ],
                "can_run_in_parallel": False,
            },
        ]

        for defn in agent_defs:
            name = defn["name"]
            self._registry.register(
                AgentRegistration(
                    name=name,
                    role=defn.get("role", AgentRole.GENERIC),
                    capabilities=defn.get("capabilities", []),
                    max_retries=defn.get("max_retries", 2),
                    timeout_seconds=defn.get("timeout_seconds", 120.0),
                    retry_strategy=defn.get("retry_strategy", RetryStrategy.EXPONENTIAL_BACKOFF),
                    can_run_in_parallel=defn.get("can_run_in_parallel", True),
                    requires_human_approval=defn.get("requires_human_approval", False),
                )
            )

        logger.info(
            f"Registered {len(agent_defs)} production agents with the runtime",
        )

    # ------------------------------------------------------------------
    # Backward-compatible per-agent function registration
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
        """Register an agent function with the runtime (backward compat)."""
        self._agent_functions[name] = fn
        if not self._registry.is_registered(name):
            self._registry.register(
                AgentRegistration(
                    name=name,
                    role=role,
                    capabilities=capabilities or [],
                    max_retries=max_retries,
                    timeout_seconds=timeout_seconds,
                    retry_strategy=retry_strategy,
                    can_run_in_parallel=can_run_in_parallel,
                    requires_human_approval=requires_human_approval,
                )
            )

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

        pipeline = InvestigationPipeline(
            db=self.db,
        )

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

    # ------------------------------------------------------------------
    # Response extraction (kept for backward compatibility)
    # ------------------------------------------------------------------

    def _extract_response(self, state: dict[str, Any]) -> AgentResponse | None:
        """Extract the final response from the investigation state."""
        final = state.get("final_response")
        if final is not None:
            if isinstance(final, AgentResponse):
                return final
            if isinstance(final, dict):
                return AgentResponse(**final)

        agent_outputs = state.get("agent_outputs", {})
        evidence = state.get("evidence", [])
        claims = state.get("claims", [])

        if not agent_outputs and not evidence and not claims:
            return None

        composition_output = agent_outputs.get("composition_agent", {})
        if composition_output:
            return AgentResponse(
                answer=composition_output.get("answer", ""),
                confidence_score=composition_output.get("confidence", 0.0),
                claims=claims if isinstance(claims, list) else [],
                missing_evidence=composition_output.get("missing_evidence", []),
                metadata={"trace_id": state.get("trace_id")},
            )

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
