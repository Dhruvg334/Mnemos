"""LangGraph Agent Gateway -- bridges the application service layer
with the AI orchestration runtime.

This module implements the ``AgentGateway`` protocol used by
``query_execution.py``.  It translates system-level request/response
schemas into the AI layer's internal format and delegates to the
``MnemosAIOrchestrator``.
"""

from __future__ import annotations

import logging
import time

from mnemos.agentic.orchestrator import MnemosAIOrchestrator
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


class LangGraphAgentGateway:
    """
    In-process LangGraph adapter.

    The adapter performs read-only retrieval and reasoning. The backend query
    execution service remains the only authority that persists query state,
    claims, citations, run status, and public progress events.
    """

    name: str = "langgraph_ai_layer"

    async def execute_query(
        self,
        request: AgentQueryRequest,
    ) -> AgentQueryResult:
        started = time.perf_counter()

        async with SessionLocal() as db:
            orchestrator = MnemosAIOrchestrator(db)

            try:
                response = await orchestrator.run_query(request)

                citations: list[AgentCitation] = []
                claims: list[AgentClaim] = []

                for claim_index, grounded_claim in enumerate(response.claims):
                    citation_ids: list[str] = []

                    for source_index, source in enumerate(
                        grounded_claim.sources
                    ):
                        citation_id = (
                            f"cit_{claim_index}_{source_index}"
                        )
                        citation_ids.append(citation_id)
                        citations.append(
                            AgentCitation(
                                id=citation_id,
                                document_id=(
                                    source.provenance.document_id
                                ),
                                document_title=(
                                    source.provenance.source_filename
                                ),
                                document_version=(
                                    source.provenance.document_version
                                ),
                                chunk_id=source.provenance.chunk_id,
                                text_excerpt=source.text_excerpt,
                                page_or_sheet=(
                                    source.provenance.page_number
                                ),
                                locator=source.provenance.locator,
                                evidence_region_id=(
                                    source.provenance.evidence_region_id
                                ),
                                retrieval_sources=[
                                    "vector",
                                    "graph",
                                ],
                                access_allowed=True,
                            )
                        )

                    claims.append(
                        AgentClaim(
                            id=grounded_claim.claim_id,
                            text=grounded_claim.text,
                            support_status=self._map_status(
                                grounded_claim.status
                            ),
                            citation_ids=citation_ids,
                        )
                    )

                latency_ms = int(
                    (time.perf_counter() - started) * 1000
                )

                return AgentQueryResult(
                    run_id=request.run_id,
                    status="succeeded",
                    answer=response.answer,
                    confidence=AgentConfidence(
                        label=self._confidence_label(
                            response.confidence_score
                        ),
                        score=response.confidence_score,
                    ),
                    claims=claims,
                    citations=citations,
                    missing_evidence=response.missing_evidence,
                    conflicts=[
                        contradiction.model_dump(mode="json")
                        for contradiction in response.contradictions
                    ],
                    run_metadata=AgentRunMetadata(
                        pipeline_version="v2.0-multi-agent-runtime",
                        latency_ms=latency_ms,
                    ),
                )
            except Exception:
                logger.exception(
                    "LangGraph agent execution failed",
                    extra={
                        "query_id": request.query_id,
                        "run_id": request.run_id,
                    },
                )
                return AgentQueryResult(
                    run_id=request.run_id,
                    status="failed",
                    error_code="AI_ORCHESTRATION_FAILED",
                    error_message=(
                        "The analysis could not be completed."
                    ),
                )

    @staticmethod
    def _confidence_label(score: float) -> str:
        if score >= 0.8:
            return "high"
        if score >= 0.5:
            return "medium"
        return "low"

    @staticmethod
    def _map_status(status: ClaimSupportStatus) -> str:
        mapping = {
            ClaimSupportStatus.SUPPORTED: "supported",
            ClaimSupportStatus.PARTIALLY_SUPPORTED: (
                "partially_supported"
            ),
            ClaimSupportStatus.REFUTED: "conflicting",
            ClaimSupportStatus.UNCERTAIN: "not_evaluated",
            ClaimSupportStatus.NO_EVIDENCE: "unsupported",
        }
        return mapping.get(status, "not_evaluated")
