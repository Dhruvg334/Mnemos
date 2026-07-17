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
        "relevance": 0.30,
        "source_reliability": 0.20,
        "provenance_validation": 0.20,
        "corroboration": 0.20,
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

        # Signal 4: Corroboration
        corroboration_score = self._corroboration_score(bundle.verified_evidence)
        signals.append(ConfidenceSignal(
            signal_name="corroboration",
            signal_value=corroboration_score,
            weight=self.weights["corroboration"],
            reasoning="Degree of multi-source corroboration",
        ))

        # Signal 5: Recency
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
