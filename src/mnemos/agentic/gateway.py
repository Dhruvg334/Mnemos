"""LangGraph Agent Gateway -- bridges the application service layer
with the AI orchestration runtime.

This module implements the ``AgentGateway`` protocol used by
``query_execution.py``.  It translates system-level request/response
schemas into the AI layer's internal format and delegates to the
``MnemosAIOrchestrator``.

The gateway performs NO persistence.  The backend query-execution
service validates and persists the result in exactly one transaction.
"""

from __future__ import annotations

import logging
import time

from mnemos.agentic.orchestrator import MnemosAIOrchestrator
from mnemos.agentic.runtime.workflow import _ApprovalPendingError
from mnemos.agentic.schemas.base import ClaimSupportStatus
from mnemos.core.db import SessionLocal
from mnemos.schemas.agent import (
    AgentCitation,
    AgentClaim,
    AgentConfidence,
    AgentQueryRequest,
    AgentQueryResult,
    AgentRunMetadata,
)

logger = logging.getLogger(__name__)

# Sanitised error codes that may safely surface to the caller.
_SAFE_ERROR_CODES = frozenset({
    "AGENT_RESPONSE_INVALID",
    "AGENT_EVIDENCE_FORBIDDEN",
    "AGENT_EVIDENCE_INVALID",
    "AGENT_EVIDENCE_OUT_OF_SCOPE",
    "AI_ORCHESTRATION_FAILED",
    "AI_ORCHESTRATION_TIMEOUT",
    "AI_APPROVAL_PENDING",
})


def _sanitize_error(exc: BaseException) -> tuple[str, str]:
    code = getattr(exc, "code", None)
    if code and code in _SAFE_ERROR_CODES:
        return code, str(getattr(exc, "message", str(exc)[:200]))

    if isinstance(exc, TimeoutError):
        return "AI_ORCHESTRATION_TIMEOUT", "The analysis request timed out."

    if isinstance(exc, ValueError):
        return "AI_ORCHESTRATION_FAILED", "Invalid input for analysis."

    if isinstance(exc, RuntimeError):
        return "AI_ORCHESTRATION_FAILED", "The analysis could not be completed."

    return "AI_ORCHESTRATION_FAILED", "An internal error occurred during analysis."


class LangGraphAgentGateway:
    """Implementation of the AgentGateway protocol using the multi-agent runtime.

    This allows the AI Layer to be plugged into the existing
    ``query_execution.py`` by only changing the factory.
    """

    name: str = "langgraph_ai_layer"

    async def execute_query(self, request: AgentQueryRequest) -> AgentQueryResult:
        """Entry point called by the background execution service.

        Maps the system's ``AgentQueryRequest`` to the internal AI Layer
        state and returns the mapped ``AgentQueryResult``.

        The full request (question, organisation_id, site_id, user_id,
        query_type, scope, options) is passed to the orchestrator which
        forwards it to the ``InvestigationPipeline`` as the runtime context.
        """
        started = time.perf_counter()

        if not request.question or not request.question.strip():
            return AgentQueryResult(
                run_id=request.run_id,
                status="failed",
                answer="",
                confidence=AgentConfidence(label="none", score=0.0),
                claims=[],
                citations=[],
                missing_evidence=[],
                run_metadata=AgentRunMetadata(
                    pipeline_version="v2.0-multi-agent-runtime",
                    latency_ms=0,
                    error="Question cannot be empty",
                ),
            )
        if not request.organisation_id:
            return AgentQueryResult(
                run_id=request.run_id,
                status="failed",
                answer="",
                confidence=AgentConfidence(label="none", score=0.0),
                claims=[],
                citations=[],
                missing_evidence=[],
                run_metadata=AgentRunMetadata(
                    pipeline_version="v2.0-multi-agent-runtime",
                    latency_ms=0,
                    error="organisation_id is required",
                ),
            )

        async with SessionLocal() as db:
            orchestrator = MnemosAIOrchestrator(db)

            try:
                agent_response = await orchestrator.run_query(
                    request=request,
                )

                latency_ms = int((time.perf_counter() - started) * 1000)

                return AgentQueryResult(
                    run_id=request.run_id,
                    status="succeeded",
                    answer=agent_response.answer,
                    confidence=AgentConfidence(
                        label="high" if agent_response.confidence_score > 0.8 else "medium",
                        score=agent_response.confidence_score,
                    ),
                    claims=[
                        AgentClaim(
                            id=c.claim_id,
                            text=c.text,
                            support_status=self._map_status(c.status),
                        )
                        for c in agent_response.claims
                    ],
                    citations=[
                        AgentCitation(
                            id=f"cit_{i}",
                            document_id=s.provenance.document_id,
                            document_title=s.provenance.source_filename,
                            document_version=s.provenance.document_version,
                            text_excerpt=s.text_excerpt,
                            page_or_sheet=s.provenance.page_number,
                            locator=s.provenance.locator,
                            evidence_region_id=s.provenance.evidence_region_id,
                        )
                        for i, c in enumerate(agent_response.claims)
                        for s in c.sources
                    ],
                    missing_evidence=agent_response.missing_evidence,
                    run_metadata=AgentRunMetadata(
                        pipeline_version="v2.0-multi-agent-runtime",
                        latency_ms=latency_ms,
                    ),
                )

            except _ApprovalPendingError:
                latency_ms = int((time.perf_counter() - started) * 1000)
                return AgentQueryResult(
                    run_id=request.run_id,
                    status="pending_approval",
                    answer="",
                    confidence=AgentConfidence(label="low", score=0.0),
                    run_metadata=AgentRunMetadata(
                        pipeline_version="v2.0-multi-agent-runtime",
                        latency_ms=latency_ms,
                    ),
                )

            except Exception as exc:
                error_code, error_message = _sanitize_error(exc)
                logger.error(
                    "LangGraph agent execution failed: code=%s",
                    error_code,
                    extra={
                        "query_id": request.query_id,
                        "run_id": request.run_id,
                        "safe_error_code": error_code,
                    },
                )
                latency_ms = int((time.perf_counter() - started) * 1000)
                return AgentQueryResult(
                    run_id=request.run_id,
                    status="failed",
                    error_code=error_code,
                    error_message=error_message,
                    run_metadata=AgentRunMetadata(
                        pipeline_version="v2.0-multi-agent-runtime",
                        latency_ms=latency_ms,
                    ),
                )

    @staticmethod
    def _map_status(status: ClaimSupportStatus) -> str:
        mapping = {
            ClaimSupportStatus.SUPPORTED: "supported",
            ClaimSupportStatus.PARTIALLY_SUPPORTED: "partially_supported",
            ClaimSupportStatus.REFUTED: "conflicting",
            ClaimSupportStatus.UNCERTAIN: "not_evaluated",
            ClaimSupportStatus.NO_EVIDENCE: "unsupported",
        }
        return mapping.get(status, "not_evaluated")
