"""Confidence Calculator.

Computes multi-signal confidence scores for evidence bundles by
combining relevance, source reliability, provenance validation,
corroboration, and recency signals.
"""

from __future__ import annotations

from mnemos.agentic.schemas.base import (
    ConfidenceSignal,
    EvidenceBundle,
    EvidenceSource,
    VerificationStatus,
)
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("confidence_calculator")


class ConfidenceCalculator:
    """Calculates confidence using multiple weighted signals.

    Signals:
    1. Relevance score (from reranking)
    2. Source reliability (from SourceReliabilityScorer)
    3. Provenance validation (verified vs unverified)
    4. Corroboration (how many sources agree)
    5. Recency (how recent is the evidence)
    """

    DEFAULT_WEIGHTS = {
        "relevance": 0.25,
        "source_reliability": 0.20,
        "provenance_validation": 0.15,
        "graph_edge_verification": 0.15,
        "corroboration": 0.15,
        "recency": 0.10,
    }

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self.weights = weights or dict(self.DEFAULT_WEIGHTS)

    def calculate_bundle_confidence(
        self,
        bundle: EvidenceBundle,
        source_reliabilities: dict[str, float] | None = None,
    ) -> tuple[float, list[ConfidenceSignal]]:
        """Calculate overall bundle confidence and individual signals."""
        if not bundle.verified_evidence:
            return 0.0, []

        source_reliabilities = source_reliabilities or {}
        signals: list[ConfidenceSignal] = []

        # Signal 1: Average relevance
        avg_relevance = sum(
            s.relevance_score for s in bundle.verified_evidence
        ) / len(bundle.verified_evidence)
        signals.append(ConfidenceSignal(
            signal_name="relevance",
            signal_value=avg_relevance,
            weight=self.weights["relevance"],
            reasoning=f"Average relevance across {len(bundle.verified_evidence)} sources",
        ))

        # Signal 2: Source reliability
        avg_reliability = self._avg_source_reliability(
            bundle.verified_evidence, source_reliabilities
        )
        signals.append(ConfidenceSignal(
            signal_name="source_reliability",
            signal_value=avg_reliability,
            weight=self.weights["source_reliability"],
            reasoning="Average reliability of evidence source types",
        ))

        # Signal 3: Provenance validation
        provenance_score = self._provenance_score(bundle.verified_evidence)
        signals.append(ConfidenceSignal(
            signal_name="provenance_validation",
            signal_value=provenance_score,
            weight=self.weights["provenance_validation"],
            reasoning="Fraction of evidence with validated provenance",
        ))

        # Signal 4: Graph-edge verification
        graph_edge_score = self._graph_edge_verification_score(bundle)
        signals.append(ConfidenceSignal(
            signal_name="graph_edge_verification",
            signal_value=graph_edge_score,
            weight=self.weights["graph_edge_verification"],
            reasoning="Verification that graph traversal edges are grounded in evidence",
        ))

        # Signal 5: Corroboration
        corroboration_score = self._corroboration_score(bundle.verified_evidence)
        signals.append(ConfidenceSignal(
            signal_name="corroboration",
            signal_value=corroboration_score,
            weight=self.weights["corroboration"],
            reasoning="Degree of multi-source corroboration",
        ))

        # Signal 6: Recency
        recency_score = self._recency_score(bundle)
        signals.append(ConfidenceSignal(
            signal_name="recency",
            signal_value=recency_score,
            weight=self.weights["recency"],
            reasoning="Recency of evidence relative to query time",
        ))

        # Weighted combination
        total_confidence = sum(
            sig.signal_value * sig.weight for sig in signals
        )
        total_confidence = max(0.0, min(1.0, total_confidence))

        return total_confidence, signals

    def calculate_source_confidence(
        self, source: EvidenceSource
    ) -> float:
        """Calculate confidence for a single evidence source."""
        signals = [
            source.relevance_score * 0.4,
            source.confidence_score * 0.4,
            (1.0 if source.verification_status == VerificationStatus.PROVENANCE_VALIDATED else 0.3) * 0.2,
        ]
        return max(0.0, min(1.0, sum(signals)))

    def _avg_source_reliability(
        self,
        evidence: list[EvidenceSource],
        reliabilities: dict[str, float],
    ) -> float:
        if not evidence:
            return 0.0
        total = 0.0
        for src in evidence:
            src_type = src.metadata.get("type", "unknown")
            total += reliabilities.get(src_type, 0.5)
        return total / len(evidence)

    @staticmethod
    def _provenance_score(evidence: list[EvidenceSource]) -> float:
        if not evidence:
            return 0.0
        validated = sum(
            1 for s in evidence
            if s.verification_status in (
                VerificationStatus.PROVENANCE_VALIDATED,
                VerificationStatus.HUMAN_REVIEWED,
            )
        )
        return validated / len(evidence)

    @staticmethod
    def _corroboration_score(evidence: list[EvidenceSource]) -> float:
        if not evidence:
            return 0.0
        # Count unique documents contributing evidence
        doc_ids = {s.provenance.document_id for s in evidence}
        # More unique sources = higher corroboration, capped at 1.0
        return min(1.0, len(doc_ids) / max(3, len(doc_ids)))

    @staticmethod
    def _graph_edge_verification_score(bundle: EvidenceBundle) -> float:
        """Score how well graph traversal edges are grounded in evidence.

        Checks whether grounded relationships have corresponding verified
        evidence sources. High score means graph edges are backed by
        real evidence rather than just graph structure.
        """
        grounded_rels = getattr(bundle, "grounded_relationships", [])
        if not grounded_rels:
            # No graph relationships -- neutral score (not a penalty)
            # but no bonus either
            return 0.5

        verified_ids = {
            s.provenance.evidence_region_id
            for s in bundle.verified_evidence
        }

        grounded_count = 0
        for rel in grounded_rels:
            # A relationship is "grounded" if it has at least one
            # evidence source that appears in verified evidence
            evidence_ids = getattr(rel, "evidence_ids", [])
            if evidence_ids and any(eid in verified_ids for eid in evidence_ids):
                grounded_count += 1
            elif not evidence_ids:
                # Relationship without evidence tracking -- partial credit
                grounded_count += 0.3

        return grounded_count / len(grounded_rels)

    @staticmethod
    def _recency_score(bundle: EvidenceBundle) -> float:
        """Score based on whether evidence is from recent documents."""
        # Default to moderate score if no temporal info
        if not bundle.verified_evidence:
            return 0.0
        # Evidence with latest_version_only flag or recent dates scores higher
        latest_count = sum(
            1 for s in bundle.verified_evidence
            if s.metadata.get("is_latest_version", True)
        )
        return latest_count / len(bundle.verified_evidence)
