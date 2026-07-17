"""Contradiction Detector.

Detects contradictions between evidence sources by analysing
semantic conflicts, temporal inconsistencies, and factual disagreements.
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel

from mnemos.agentic.schemas.base import (
    Contradiction,
    EvidenceBundle,
    EvidenceSource,
)
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("contradiction_detector")


class ContradictionCandidate(BaseModel):
    """A detected contradiction between evidence sources."""
    source_a_idx: int
    source_b_idx: int
    summary: str
    description: str
    severity: str = "high"
    contradiction_type: str = "semantic"


class ContradictionDetector:
    """Detects contradictions between evidence sources.

    Detection methods:
    1. Negation detection (one source negates another)
    2. Numeric conflict (different values for same metric)
    3. Temporal inconsistency (outdated vs current info)
    4. Entity conflict (different claims about same entity)
    """

    async def detect(
        self, bundle: EvidenceBundle
    ) -> list[Contradiction]:
        """Detect contradictions across all verified evidence."""
        evidence = bundle.verified_evidence
        if len(evidence) < 2:
            return []

        candidates: list[ContradictionCandidate] = []

        # Pairwise comparison
        for i in range(len(evidence)):
            for j in range(i + 1, len(evidence)):
                candidate = self._check_pair(evidence[i], evidence[j], i, j)
                if candidate:
                    candidates.append(candidate)

        # Deduplicate and convert
        contradictions = self._deduplicate(candidates, evidence)
        logger.info(f"Detected {len(contradictions)} contradictions from {len(evidence)} sources")
        return contradictions

    def _check_pair(
        self,
        src_a: EvidenceSource,
        src_b: EvidenceSource,
        idx_a: int,
        idx_b: int,
    ) -> ContradictionCandidate | None:
        """Check two evidence sources for contradictions."""
        text_a = src_a.text_excerpt.lower()
        text_b = src_b.text_excerpt.lower()

        # Method 1: Negation detection
        negation_result = self._detect_negation(text_a, text_b)
        if negation_result:
            return ContradictionCandidate(
                source_a_idx=idx_a,
                source_b_idx=idx_b,
                summary=negation_result,
                description=f"Negation conflict between sources {idx_a} and {idx_b}",
                severity="high",
                contradiction_type="negation",
            )

        # Method 2: Numeric conflict
        numeric_result = self._detect_numeric_conflict(text_a, text_b)
        if numeric_result:
            return ContradictionCandidate(
                source_a_idx=idx_a,
                source_b_idx=idx_b,
                summary=numeric_result,
                description=f"Numeric conflict between sources {idx_a} and {idx_b}",
                severity="medium",
                contradiction_type="numeric",
            )

        # Method 3: Temporal inconsistency
        temporal_result = self._detect_temporal_conflict(src_a, src_b)
        if temporal_result:
            return ContradictionCandidate(
                source_a_idx=idx_a,
                source_b_idx=idx_b,
                summary=temporal_result,
                description=f"Temporal inconsistency between sources {idx_a} and {idx_b}",
                severity="low",
                contradiction_type="temporal",
            )

        return None

    @staticmethod
    def _detect_negation(text_a: str, text_b: str) -> str | None:
        """Detect negation patterns between two texts."""
        negation_words = {"not", "no", "never", "none", "cannot", "does not", "is not"}

        sentences_a = text_a.split(".")
        sentences_b = text_b.split(".")

        for sa in sentences_a:
            sa_words = set(sa.lower().split())
            has_neg_a = bool(sa_words & negation_words)

            for sb in sentences_b:
                sb_words = set(sb.lower().split())
                has_neg_b = bool(sb_words & negation_words)

                if has_neg_a != has_neg_b:
                    # Check if sentences are about similar topics
                    common = sa_words & sb_words - {"the", "a", "an", "is", "are", "was"}
                    if len(common) >= 3:
                        return f"Negation conflict: '{sa.strip()[:80]}' vs '{sb.strip()[:80]}'"

        return None

    @staticmethod
    def _detect_numeric_conflict(text_a: str, text_b: str) -> str | None:
        """Detect conflicting numeric values in similar contexts."""
        import re

        pattern = r'(\d+(?:\.\d+)?)\s*(bar|psi|°[CcFf]|°[Kk]|rpm|mm|cm|m|kg|ton|MW|kW|kPa|MPa|°C|°F)'
        nums_a = re.findall(pattern, text_a)
        nums_b = re.findall(pattern, text_b)

        # Check if same unit but different values
        units_a = {unit: float(val) for val, unit in nums_a}
        units_b = {unit: float(val) for val, unit in nums_b}

        for unit in units_a:
            if unit in units_b:
                if abs(units_a[unit] - units_b[unit]) > 0.01 * max(units_a[unit], units_b[unit]):
                    return (
                        f"Numeric conflict on {unit}: "
                        f"{units_a[unit]} vs {units_b[unit]}"
                    )

        return None

    @staticmethod
    def _detect_temporal_conflict(
        src_a: EvidenceSource, src_b: EvidenceSource
    ) -> str | None:
        """Detect temporal inconsistency between sources."""
        ver_a = src_a.provenance.document_version
        ver_b = src_b.provenance.document_version

        # If versions differ significantly, the older one may be superseded
        if abs(ver_a - ver_b) >= 2:
            older = min(ver_a, ver_b)
            return (
                f"Temporal inconsistency: document versions {ver_a} and {ver_b} "
                f"(version {older} may be superseded)"
            )

        return None

    @staticmethod
    def _deduplicate(
        candidates: list[ContradictionCandidate],
        evidence: list[EvidenceSource],
    ) -> list[Contradiction]:
        """Deduplicate and convert candidates to Contradiction objects."""
        seen_pairs: set[tuple[int, int]] = set()
        contradictions: list[Contradiction] = []

        for cand in candidates:
            pair = (min(cand.source_a_idx, cand.source_b_idx),
                    max(cand.source_a_idx, cand.source_b_idx))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            pair_key = f"{pair[0]}_{pair[1]}"
            hash_val = hashlib.md5(pair_key.encode()).hexdigest()[:8]

            contradictions.append(Contradiction(
                contradiction_id=f"contr_{hash_val}",
                summary=cand.summary,
                description=cand.description,
                involved_evidence_ids=[str(cand.source_a_idx), str(cand.source_b_idx)],
                severity=cand.severity,
            ))

        return contradictions
