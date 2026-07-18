"""Lessons Learned Agent.

Compares current situation with historical incidents:
- Historical incident comparison
- Corrective action effectiveness
- Asset similarity analysis
- Recurring failure pattern detection
- Proactive recommendations from patterns
"""

from __future__ import annotations

import uuid
from typing import Any

from mnemos.agentic.agents.reasoning._base import _BaseReasoningAgent
from mnemos.agentic.runtime.types import AgentCapability, AgentRole
from mnemos.agentic.schemas.base import (
    Citation,
    ClaimSupportStatus,
    ConfidenceSignal,
    EvidenceSource,
    GroundedClaim,
    HistoricalComparison,
    MissingEvidence,
    ProactiveRecommendation,
    ReasoningDecision,
    ReasoningOutput,
    RecommendedAction,
)
from mnemos.agentic.schemas.state import AgentState


class LessonsLearnedAgent(_BaseReasoningAgent):
    """Compares current situation with historical incidents and generates
    proactive recommendations.

    Pipeline:
    1. Extract historical incident data from evidence
    2. Compare current situation with historical cases
    3. Evaluate corrective action effectiveness
    4. Analyse asset similarity
    5. Detect recurring failure patterns
    6. Generate proactive recommendations
    """

    name = "lessons_learned_agent"
    role = AgentRole.ANALYSIS
    description = (
        "Compares current situation with historical incidents, analyses "
        "corrective actions and recurring patterns, and generates "
        "proactive recommendations."
    )
    timeout_seconds = 60.0

    def _capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability(
                name="lessons_learned",
                description=(
                    "Historical comparison, pattern detection, and "
                    "proactive recommendations from verified evidence."
                ),
                input_types=["evidence_bundle", "rca_output"],
                output_types=["reasoning_output", "historical_comparisons"],
                dependencies=["evidence_verification"],
            ),
        ]

    @property
    def required_dependencies(self) -> list[str]:
        return ["evidence_verification"]

    async def execute(self, state: AgentState) -> AgentState:
        bundle = self._validate_evidence_exists(state)
        if bundle is None:
            return state

        verified = bundle.verified_evidence
        if not verified:
            output = ReasoningOutput(
                agent_name=self.name,
                reasoning_decision=ReasoningDecision.ABSTAIN,
                confidence_score=0.0,
                reasoning_summary="No verified evidence for lessons learned analysis",
                missing_evidence=[
                    MissingEvidence(
                        evidence_type="historical_evidence",
                        description="No historical evidence available for comparison",
                        suggested_action="Retrieve historical incident reports and corrective actions",
                        priority="high",
                    )
                ],
            )
            self._store_reasoning_output(state, output)
            return state

        historical_incidents = self._extract_historical_incidents(verified)
        comparisons = self._compare_situations(historical_incidents, verified, state)
        action_effectiveness = self._evaluate_actions(comparisons)
        asset_similarity = self._analyse_asset_similarity(verified, state)
        patterns = self._detect_patterns(comparisons, verified)
        recommendations = self._generate_recommendations(
            patterns, comparisons, action_effectiveness
        )
        claims = self._build_claims(comparisons, recommendations, verified)
        citations = self._build_citations(verified)
        confidence = self._calculate_confidence(comparisons, verified)
        missing = self._identify_missing(comparisons, verified)
        next_actions = self._build_actions(recommendations, patterns)

        output = ReasoningOutput(
            agent_name=self.name,
            reasoning_decision=self._decide(comparisons, confidence),
            claims=claims,
            citations=citations,
            confidence_score=confidence,
            missing_evidence=missing,
            confidence_signals=[
                ConfidenceSignal(
                    signal_name="comparison_count",
                    signal_value=min(len(comparisons) / 3.0, 1.0),
                    weight=1.0,
                    reasoning=f"{len(comparisons)} historical comparisons made",
                ),
                ConfidenceSignal(
                    signal_name="pattern_count",
                    signal_value=min(len(patterns) / 3.0, 1.0),
                    weight=1.5,
                    reasoning=f"{len(patterns)} recurring patterns detected",
                ),
            ],
            next_actions=next_actions,
            next_recommended_agents=(["rca_agent"] if patterns else []),
            reasoning_summary=self._build_summary(
                comparisons, patterns, recommendations, confidence
            ),
            metadata={
                "historical_comparisons": [c.model_dump() for c in comparisons],
                "action_effectiveness": action_effectiveness,
                "asset_similarity": asset_similarity,
                "patterns": patterns,
                "proactive_recommendations": [r.model_dump() for r in recommendations],
            },
        )

        self._store_reasoning_output(state, output)

        for claim in claims:
            state.setdefault("claims", [])
            state["claims"].append(claim)

        self.logger.info(
            f"Lessons learned: {len(comparisons)} comparisons, "
            f"{len(patterns)} patterns, "
            f"{len(recommendations)} recommendations, "
            f"confidence={confidence:.2f}"
        )
        return state

    # ------------------------------------------------------------------
    # Historical incident extraction
    # ------------------------------------------------------------------

    def _extract_historical_incidents(self, evidence: list[EvidenceSource]) -> list[dict[str, Any]]:
        """Extract historical incident information from evidence."""
        incidents: list[dict[str, Any]] = []
        seen: set[str] = set()

        for source in evidence:
            text = source.text_excerpt.strip()
            text_key = text.lower()[:100]
            if text_key in seen:
                continue
            seen.add(text_key)

            metadata = source.metadata
            incident_id = metadata.get("incident_id") or metadata.get("rca_id")
            if not incident_id:
                incident_id = f"hist_{uuid.uuid4().hex[:8]}"

            incidents.append(
                {
                    "id": incident_id,
                    "title": text[:200],
                    "asset_id": metadata.get("asset_id", ""),
                    "timestamp": metadata.get("timestamp", ""),
                    "severity": metadata.get("severity", "medium"),
                    "evidence_source": source,
                    "status": metadata.get("status", "unknown"),
                }
            )

        return incidents

    # ------------------------------------------------------------------
    # Situation comparison
    # ------------------------------------------------------------------

    def _compare_situations(
        self,
        historical_incidents: list[dict[str, Any]],
        current_evidence: list[EvidenceSource],
        state: AgentState,
    ) -> list[HistoricalComparison]:
        """Compare current situation with each historical incident."""
        comparisons: list[HistoricalComparison] = []
        current_text = " ".join(s.text_excerpt.lower() for s in current_evidence)

        for incident in historical_incidents:
            historical_text = incident["evidence_source"].text_excerpt.lower()
            matching, differing = self._compare_texts(current_text, historical_text)
            similarity = len(matching) / max(len(matching) + len(differing), 1)

            if similarity < 0.1:
                continue

            comparisons.append(
                HistoricalComparison(
                    comparison_id=f"comp_{uuid.uuid4().hex[:8]}",
                    historical_case_id=incident["id"],
                    historical_title=incident["title"][:120],
                    similarity_score=round(similarity, 3),
                    matching_factors=matching[:10],
                    differing_factors=differing[:10],
                    applicable_actions=[f"Review corrective actions from case {incident['id']}"],
                    reasoning=(
                        f"Historical case shares {len(matching)} factors "
                        f"with current situation (similarity={similarity:.2f})"
                    ),
                )
            )

        comparisons.sort(key=lambda c: c.similarity_score, reverse=True)
        return comparisons[:5]

    def _compare_texts(self, text_a: str, text_b: str) -> tuple[list[str], list[str]]:
        """Compare two texts and extract matching/differing factors."""
        words_a = set(text_a.split())
        words_b = set(text_b.split())

        significant_a = {w for w in words_a if len(w) > 4}
        significant_b = {w for w in words_b if len(w) > 4}

        matching = list(significant_a & significant_b)
        differing = list(significant_a - significant_b)

        return matching, differing

    # ------------------------------------------------------------------
    # Corrective action evaluation
    # ------------------------------------------------------------------

    def _evaluate_actions(self, comparisons: list[HistoricalComparison]) -> dict[str, Any]:
        """Evaluate effectiveness of historical corrective actions."""
        total_applicable = sum(len(c.applicable_actions) for c in comparisons)
        high_similarity = [c for c in comparisons if c.similarity_score >= 0.6]

        return {
            "total_applicable_actions": total_applicable,
            "high_similarity_cases": len(high_similarity),
            "recommendation": (
                "Review and apply historical corrective actions"
                if high_similarity
                else "Limited applicability of historical actions"
            ),
        }

    # ------------------------------------------------------------------
    # Asset similarity
    # ------------------------------------------------------------------

    def _analyse_asset_similarity(
        self,
        evidence: list[EvidenceSource],
        state: AgentState,
    ) -> dict[str, Any]:
        """Analyse similarity of current assets with historical cases."""
        asset_ids = set()
        for source in evidence:
            aid = source.metadata.get("asset_id")
            if aid:
                asset_ids.add(aid)

        ctx = state.get("context", {})
        resolved = ctx.get("resolved_entities", [])
        for entity in resolved:
            if isinstance(entity, dict) and entity.get("entity_id"):
                asset_ids.add(entity["entity_id"])

        return {
            "unique_assets": list(asset_ids),
            "asset_count": len(asset_ids),
        }

    # ------------------------------------------------------------------
    # Pattern detection
    # ------------------------------------------------------------------

    def _detect_patterns(
        self,
        comparisons: list[HistoricalComparison],
        evidence: list[EvidenceSource],
    ) -> list[dict[str, Any]]:
        """Detect recurring patterns across historical comparisons."""
        patterns: list[dict[str, Any]] = []
        factor_frequency: dict[str, int] = {}

        for comp in comparisons:
            for factor in comp.matching_factors:
                factor_frequency[factor] = factor_frequency.get(factor, 0) + 1

        for factor, count in factor_frequency.items():
            if count >= 2:
                patterns.append(
                    {
                        "pattern_id": f"pat_{uuid.uuid4().hex[:8]}",
                        "description": f"Recurring factor: '{factor}' appears in {count} historical cases",
                        "frequency": count,
                        "factor": factor,
                        "severity": "high" if count >= 3 else "medium",
                    }
                )

        if len(comparisons) >= 3:
            high_sim = [c for c in comparisons if c.similarity_score >= 0.5]
            if len(high_sim) >= 2:
                patterns.append(
                    {
                        "pattern_id": f"pat_{uuid.uuid4().hex[:8]}",
                        "description": (
                            f"{len(high_sim)} historical cases show high similarity "
                            f"to current situation — possible recurring issue"
                        ),
                        "frequency": len(high_sim),
                        "factor": "situational_similarity",
                        "severity": "high",
                    }
                )

        return patterns

    # ------------------------------------------------------------------
    # Proactive recommendations
    # ------------------------------------------------------------------

    def _generate_recommendations(
        self,
        patterns: list[dict[str, Any]],
        comparisons: list[HistoricalComparison],
        action_effectiveness: dict[str, Any],
    ) -> list[ProactiveRecommendation]:
        """Generate proactive recommendations from patterns."""
        recs: list[ProactiveRecommendation] = []

        for pattern in patterns:
            recs.append(
                ProactiveRecommendation(
                    recommendation_id=f"rec_{uuid.uuid4().hex[:8]}",
                    title=f"Address recurring pattern: {pattern['factor'][:60]}",
                    description=pattern["description"],
                    category="preventive" if pattern["severity"] == "high" else "predictive",
                    priority=pattern["severity"],
                    linked_pattern_ids=[pattern["pattern_id"]],
                    reasoning=f"Pattern detected in {pattern['frequency']} historical cases",
                )
            )

        if action_effectiveness.get("high_similarity_cases", 0) > 0:
            recs.append(
                ProactiveRecommendation(
                    recommendation_id=f"rec_{uuid.uuid4().hex[:8]}",
                    title="Apply proven corrective actions from similar historical cases",
                    description=(
                        f"{action_effectiveness['high_similarity_cases']} high-similarity "
                        "historical cases found with applicable corrective actions"
                    ),
                    category="corrective",
                    priority="high",
                    reasoning="Historical corrective actions have proven effective in similar situations",
                )
            )

        if comparisons and not patterns:
            recs.append(
                ProactiveRecommendation(
                    recommendation_id=f"rec_{uuid.uuid4().hex[:8]}",
                    title="Monitor situation for pattern emergence",
                    description=(
                        "Historical cases found but no clear recurring patterns yet. "
                        "Continued monitoring recommended."
                    ),
                    category="predictive",
                    priority="low",
                    reasoning="Partial historical matches without clear patterns",
                )
            )

        return recs

    # ------------------------------------------------------------------
    # Claims
    # ------------------------------------------------------------------

    def _build_claims(
        self,
        comparisons: list[HistoricalComparison],
        recommendations: list[ProactiveRecommendation],
        evidence: list[EvidenceSource],
    ) -> list[GroundedClaim]:
        claims: list[GroundedClaim] = []

        if comparisons:
            best = comparisons[0]
            claims.append(
                GroundedClaim(
                    claim_id=f"claim_{uuid.uuid4().hex[:8]}",
                    text=(
                        f"Current situation shows {best.similarity_score:.0%} similarity "
                        f"with historical case: {best.historical_title[:100]}"
                    ),
                    status=(
                        ClaimSupportStatus.SUPPORTED
                        if best.similarity_score >= 0.6
                        else ClaimSupportStatus.PARTIALLY_SUPPORTED
                    ),
                    reasoning=best.reasoning,
                )
            )

        high_sim = [c for c in comparisons if c.similarity_score >= 0.6]
        if len(high_sim) >= 2:
            claims.append(
                GroundedClaim(
                    claim_id=f"claim_{uuid.uuid4().hex[:8]}",
                    text=f"Multiple ({len(high_sim)}) historical cases show high similarity — possible recurring issue",
                    status=ClaimSupportStatus.PARTIALLY_SUPPORTED,
                    reasoning="Multiple similar historical cases suggest systemic pattern",
                )
            )

        if recommendations:
            claims.append(
                GroundedClaim(
                    claim_id=f"claim_{uuid.uuid4().hex[:8]}",
                    text=f"{len(recommendations)} proactive recommendations generated from historical analysis",
                    status=ClaimSupportStatus.SUPPORTED,
                    reasoning="Recommendations grounded in verified historical patterns",
                )
            )

        return claims

    # ------------------------------------------------------------------
    # Citations
    # ------------------------------------------------------------------

    def _build_citations(self, evidence: list[EvidenceSource]) -> list[Citation]:
        citations: list[Citation] = []
        for source in evidence:
            p = source.provenance
            citations.append(
                Citation(
                    citation_id=f"cit_{uuid.uuid4().hex[:8]}",
                    evidence_region_id=p.evidence_region_id,
                    document_id=p.document_id,
                    document_version=p.document_version,
                    chunk_id=p.chunk_id,
                    page_number=p.page_number,
                    locator=p.locator,
                    text_excerpt=source.text_excerpt,
                    relevance_score=source.relevance_score,
                    confidence_score=source.confidence_score,
                )
            )
        return citations

    # ------------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------------

    def _calculate_confidence(
        self,
        comparisons: list[HistoricalComparison],
        evidence: list[EvidenceSource],
    ) -> float:
        if not comparisons:
            return 0.2

        best_sim = max(c.similarity_score for c in comparisons)
        avg_sim = sum(c.similarity_score for c in comparisons) / len(comparisons)
        evidence_quality = (
            sum(s.confidence_score for s in evidence) / len(evidence) if evidence else 0.0
        )

        confidence = 0.4 * best_sim + 0.3 * avg_sim + 0.3 * evidence_quality
        return round(min(confidence, 1.0), 3)

    # ------------------------------------------------------------------
    # Missing evidence
    # ------------------------------------------------------------------

    def _identify_missing(
        self,
        comparisons: list[HistoricalComparison],
        evidence: list[EvidenceSource],
    ) -> list[MissingEvidence]:
        missing: list[MissingEvidence] = []

        if not comparisons:
            missing.append(
                MissingEvidence(
                    evidence_type="historical_incidents",
                    description="No historical incidents found for comparison",
                    suggested_action="Retrieve historical incident reports for similar assets",
                    priority="high",
                )
            )

        source_types = {s.metadata.get("type", "unknown") for s in evidence}
        if "corrective_action" not in source_types:
            missing.append(
                MissingEvidence(
                    evidence_type="corrective_actions",
                    description="No corrective action records found",
                    suggested_action="Retrieve corrective action history from maintenance system",
                    priority="medium",
                )
            )

        if "maintenance_log" not in source_types:
            missing.append(
                MissingEvidence(
                    evidence_type="maintenance_history",
                    description="No maintenance history for asset similarity analysis",
                    suggested_action="Retrieve maintenance records for asset comparison",
                    priority="medium",
                )
            )

        return missing

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _build_actions(
        self,
        recommendations: list[ProactiveRecommendation],
        patterns: list[dict[str, Any]],
    ) -> list[RecommendedAction]:
        actions: list[RecommendedAction] = []

        for rec in recommendations[:3]:
            actions.append(
                RecommendedAction(
                    action_id=f"act_{uuid.uuid4().hex[:8]}",
                    type="MONITOR" if rec.category == "predictive" else "INSPECTION",
                    description=f"{rec.title}: {rec.description[:100]}",
                    priority=rec.priority,
                    reasoning=rec.reasoning,
                )
            )

        if patterns:
            actions.append(
                RecommendedAction(
                    action_id=f"act_{uuid.uuid4().hex[:8]}",
                    type="TRAINING",
                    description=(f"Review {len(patterns)} recurring patterns with operations team"),
                    priority="high",
                    reasoning="Recurring patterns suggest systemic issues requiring team awareness",
                )
            )

        return actions

    # ------------------------------------------------------------------
    # Decision
    # ------------------------------------------------------------------

    def _decide(
        self, comparisons: list[HistoricalComparison], confidence: float
    ) -> ReasoningDecision:
        if not comparisons:
            return ReasoningDecision.ABSTAIN
        if confidence >= 0.5:
            return ReasoningDecision.SUFFICIENT
        return ReasoningDecision.REQUEST_EVIDENCE

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _build_summary(
        self,
        comparisons: list[HistoricalComparison],
        patterns: list[dict[str, Any]],
        recommendations: list[ProactiveRecommendation],
        confidence: float,
    ) -> str:
        parts = [
            f"Compared with {len(comparisons)} historical incidents.",
        ]
        if comparisons:
            best = comparisons[0]
            parts.append(
                f"Best match: {best.historical_title[:80]} (similarity={best.similarity_score:.2f})"
            )
        parts.append(f"Detected {len(patterns)} recurring patterns.")
        parts.append(f"Generated {len(recommendations)} proactive recommendations.")
        parts.append(f"Confidence: {confidence:.2f}.")
        return " ".join(parts)
