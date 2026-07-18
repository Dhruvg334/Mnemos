"""Evidence Verification Agent.

Validates the raw evidence bundle produced by the EvidenceRetrieval
agent. Performs version-aware provenance grounding, cross-encoder
reranking, contradiction detection, citation extraction, confidence
calculation, and security boundary checks.
"""

from __future__ import annotations

from typing import Any

from mnemos.agentic.agents.retrieval._base import _BaseRetrievalAgent
from mnemos.agentic.deps import get_graph_client
from mnemos.agentic.retrieval.citation_extractor import CitationExtractor
from mnemos.agentic.retrieval.confidence import ConfidenceCalculator
from mnemos.agentic.retrieval.contradiction import ContradictionDetector
from mnemos.agentic.retrieval.graph_rag import GraphRAGLayer
from mnemos.agentic.retrieval.source_reliability import SourceReliabilityScorer
from mnemos.agentic.runtime.types import AgentCapability, AgentRole
from mnemos.agentic.schemas.base import EvidenceBundle, EvidenceSource
from mnemos.agentic.schemas.state import AgentState
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("agents.evidence_verification")


class EvidenceVerificationAgent(_BaseRetrievalAgent):
    """Verifies and grounds the raw evidence bundle.

    Uses the ``GraphRAGLayer`` to:
    1. Ground evidence regions to version-aware provenance chains
    2. Cross-encoder rerank for relevance
    3. Filter by minimum relevance threshold
    4. Detect contradictions across evidence sources
    5. Extract structured citations
    6. Calculate confidence scores
    7. Score source reliability
    8. Detect superseded documents
    9. Enforce permission boundaries

    Reads from state:
    - ``context["evidence_bundle"]`` (an ``EvidenceBundle``)
    - ``context`` (for permission context: site_id, org_id)

    Writes to state:
    - ``context["evidence_bundle"]`` (updated with verified_evidence,
      citations, confidence_signals, contradictions, missing_evidence)
    - ``context["contradictions"]``
    - ``evidence`` list (updated with verified items)
    """

    name = "evidence_verification"
    role = AgentRole.VERIFICATION
    description = (
        "Verifies evidence provenance, detects contradictions, "
        "extracts citations, and calculates confidence."
    )
    timeout_seconds = 90.0

    def _capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability(
                name="evidence_verification",
                description=(
                    "Grounds evidence to provenance, reranks, detects "
                    "contradictions, extracts citations, and verifies permissions."
                ),
                input_types=["evidence_bundle"],
                output_types=[
                    "verified_evidence",
                    "contradictions",
                    "citations",
                    "confidence_signals",
                ],
                dependencies=["evidence_gathering"],
            ),
        ]

    @property
    def required_dependencies(self) -> list[str]:
        return ["evidence_retrieval"]

    async def execute(self, state: AgentState) -> AgentState:
        ctx = dict(state.get("context", {}))
        bundle: EvidenceBundle | None = ctx.get("evidence_bundle")

        if bundle is None:
            logger.warning("No evidence bundle to verify; skipping.")
            return state

        graph_client = await get_graph_client()
        rag_layer = GraphRAGLayer(self.db, graph_client)

        query_text = state.get("query", "")

        logger.info(
            f"Verifying evidence bundle: {len(bundle.raw_vector_data)} candidates, "
            f"{len(bundle.raw_graph_data)} graph sources"
        )

        # 1. Graph-Vector Fusion: ground + rerank
        verified: list[EvidenceSource] = await rag_layer.process_bundle(bundle, query_text)
        bundle.verified_evidence = verified

        # 2. Detect contradictions
        contradiction_detector = ContradictionDetector()
        bundle.contradictions = await contradiction_detector.detect(bundle)

        # 3. Source reliability scoring
        reliability_scorer = SourceReliabilityScorer()
        source_reliabilities = reliability_scorer.score_bundle(bundle)

        # 4. Confidence calculation
        confidence_calculator = ConfidenceCalculator()
        confidence, signals = confidence_calculator.calculate_bundle_confidence(
            bundle, source_reliabilities
        )
        bundle.confidence_signals = signals
        bundle.metadata["overall_confidence"] = confidence

        # 5. Citation extraction
        citation_extractor = CitationExtractor()
        bundle.citations = citation_extractor.extract(bundle)

        # 6. Security boundary enforcement
        self.guardrails.check_permissions(ctx, verified)

        # 7. Update state
        ctx["evidence_bundle"] = bundle
        ctx["contradictions"] = [c.model_dump() for c in bundle.contradictions]
        ctx["citations"] = [c.model_dump() for c in bundle.citations]
        ctx["confidence"] = confidence
        state["context"] = ctx

        # 8. Update the shared evidence list with verified items
        evidence_list: list[dict[str, Any]] = list(state.get("evidence", []))
        for source in verified:
            evidence_list.append(
                {
                    "source": "verified",
                    "content": source.text_excerpt,
                    "relevance_score": source.relevance_score,
                    "confidence_score": source.confidence_score,
                    "verification_status": source.verification_status.value,
                    "document_id": source.provenance.document_id,
                    "page": source.provenance.page_number,
                }
            )

        state["evidence"] = evidence_list

        logger.info(
            f"Verification complete: {len(verified)} verified sources, "
            f"{len(bundle.contradictions)} contradictions, "
            f"{len(bundle.citations)} citations, "
            f"confidence={confidence:.3f}"
        )

        return state
