"""Source Reliability Scorer.

Assigns trust/reliability scores to evidence sources based on their
type, provenance, and institutional authority.
"""

from __future__ import annotations

from mnemos.agentic.schemas.base import (
    EvidenceBundle,
    EvidenceSource,
    SourceReliability,
    VerificationStatus,
)
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("source_reliability")

# Base reliability scores per source type
# Higher = more trustworthy
SOURCE_TYPE_SCORES: dict[str, float] = {
    "knowledge_card": 0.95,
    "maintenance_record": 0.90,
    "compliance_document": 0.90,
    "technical_manual": 0.85,
    "inspection_report": 0.85,
    "incident_report": 0.80,
    "graph_traversal": 0.75,
    "vector": 0.65,
    "lexical": 0.60,
    "metadata": 0.55,
    "unknown": 0.50,
}


class SourceReliabilityScorer:
    """Scores evidence source reliability.

    Factors:
    1. Base type score (e.g. compliance docs are more reliable)
    2. Provenance validation bonus
    3. Document version currency
    4. Multiple-source corroboration
    """

    def score_bundle(self, bundle: EvidenceBundle) -> dict[str, float]:
        """Score reliability for all source types in the bundle."""
        type_counts: dict[str, int] = {}
        for src in bundle.verified_evidence:
            src_type = src.metadata.get("type", "unknown")
            type_counts[src_type] = type_counts.get(src_type, 0) + 1

        reliabilities: dict[str, float] = {}
        for src_type, count in type_counts.items():
            reliabilities[src_type] = self.score_type(src_type, count)

        return reliabilities

    def score_type(self, source_type: str, corroboration_count: int = 1) -> float:
        """Calculate reliability for a source type."""
        base = SOURCE_TYPE_SCORES.get(source_type, 0.50)

        # Corroboration bonus: +0.05 per additional corroborating source, max +0.15
        corroboration_bonus = min(0.15, (corroboration_count - 1) * 0.05)

        return min(1.0, base + corroboration_bonus)

    def score_source(self, source: EvidenceSource) -> SourceReliability:
        """Score a single evidence source."""
        src_type = source.metadata.get("type", "unknown")
        base = SOURCE_TYPE_SCORES.get(src_type, 0.50)

        # Validation bonus
        validation_bonus = 0.0
        if source.verification_status == VerificationStatus.PROVENANCE_VALIDATED:
            validation_bonus = 0.10
        elif source.verification_status == VerificationStatus.HUMAN_REVIEWED:
            validation_bonus = 0.15

        score = min(1.0, base + validation_bonus)

        return SourceReliability(
            source_type=src_type,
            reliability_score=score,
            reasoning=f"Base={base:.2f}, validation_bonus={validation_bonus:.2f}",
        )

    def score_evidence_sources(self, sources: list[EvidenceSource]) -> list[SourceReliability]:
        """Score all evidence sources."""
        return [self.score_source(s) for s in sources]
