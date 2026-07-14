import logging

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
    Implementation of the AgentGateway protocol using LangGraph.
    This allows the AI Layer to be plugged into the existing
    query_execution.py by only changing the factory.
    """
    name: str = "langgraph_ai_layer"

    async def execute_query(self, request: AgentQueryRequest) -> AgentQueryResult:
        """
        Entry point called by the background execution service.
        Maps the system's AgentQueryRequest to the internal AI Layer state.
        """
        async with SessionLocal() as db:
            orchestrator = MnemosAIOrchestrator(db)

            try:
                # Run the internal orchestration
                agent_response = await orchestrator.run_query(
                    query_id=request.query_id,
                    run_id=request.run_id
                )

                # Map back to the system's shared AgentQueryResult schema
                return AgentQueryResult(
                    run_id=request.run_id,
                    status="succeeded",
                    answer=agent_response.answer,
                    confidence=AgentConfidence(
                        label="high" if agent_response.confidence_score > 0.8 else "medium",
                        score=agent_response.confidence_score
                    ),
                    claims=[
                        AgentClaim(
                            id=c.claim_id,
                            text=c.text,
                            support_status=self._map_status(c.status)
                        ) for c in agent_response.claims
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
                            evidence_region_id=s.provenance.evidence_region_id
                        ) for i, c in enumerate(agent_response.claims) for s in c.sources
                    ],
                    missing_evidence=agent_response.missing_evidence,
                    run_metadata=AgentRunMetadata(
                        pipeline_version="v1.0-langgraph"
                    )
                )

            except Exception as e:
                logger.error(f"AI Gateway Execution Failed: {str(e)}", exc_info=True)
                return AgentQueryResult(
                    run_id=request.run_id,
                    status="failed",
                    error_code="AI_ORCHESTRATION_ERROR",
                    error_message=str(e)
                )

    def _map_status(self, status: ClaimSupportStatus) -> str:
        mapping = {
            ClaimSupportStatus.SUPPORTED: "supported",
            ClaimSupportStatus.PARTIALLY_SUPPORTED: "partially_supported",
            ClaimSupportStatus.REFUTED: "conflicting",
            ClaimSupportStatus.UNCERTAIN: "not_evaluated",
            ClaimSupportStatus.NO_EVIDENCE: "unsupported"
        }
        return mapping.get(status, "not_evaluated")
