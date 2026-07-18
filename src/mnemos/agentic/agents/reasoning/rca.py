"""RCA (Root Cause Analysis) Agent.

Performs structured root cause analysis from verified evidence:
- Timeline generation from temporal evidence
- Hypothesis generation and comparison
- Evidence ranking by relevance to each hypothesis
- Missing diagnostic identification
- Similar failure reasoning from historical data
- Test recommendations to validate hypotheses
- No definitive conclusions unless evidence supports it
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
    EvidenceRanking,
    EvidenceSource,
    GroundedClaim,
    Hypothesis,
    MissingEvidence,
    ReasoningDecision,
    ReasoningOutput,
    RecommendedAction,
    TestRecommendation,
    TimelineEvent,
)
from mnemos.agentic.schemas.state import AgentState


class RCAAgent(_BaseReasoningAgent):
    """Performs structured root cause analysis from verified evidence.

    RCA pipeline:
    1. Build timeline from temporal evidence
    2. Extract facts (symptoms, conditions, actions)
    3. Generate causal hypotheses
    4. Compare hypotheses against evidence
    5. Rank evidence by relevance to leading hypothesis
    6. Identify missing diagnostics
    7. Recommend tests to validate/refute hypotheses
    8. Check for similar historical failures

    Never makes definitive conclusions unless evidence supports it.
    """

    name = "rca_agent"
    role = AgentRole.ANALYSIS
    description = (
        "Performs structured root cause analysis: timeline, hypothesis "
        "generation, evidence ranking, missing diagnostics, and test "
        "recommendations. Never concludes without evidence."
    )
    timeout_seconds = 90.0

    def _capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability(
                name="root_cause_analysis",
                description=(
                    "Generates timeline, hypotheses, evidence rankings, "
                    "and test recommendations from verified evidence."
                ),
                input_types=["evidence_bundle", "asset_intelligence"],
                output_types=["reasoning_output", "rca_hypotheses", "rca_timeline"],
                dependencies=["evidence_verification", "asset_intelligence"],
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
                reasoning_summary="No verified evidence for RCA",
                missing_evidence=[
                    MissingEvidence(
                        evidence_type="rca_evidence",
                        description="No verified evidence available for root cause analysis",
                        suggested_action="Retrieve incident reports, maintenance logs, and sensor data",
                        priority="high",
                    )
                ],
            )
            self._store_reasoning_output(state, output)
            return state

        timeline = self._build_timeline(verified)
        facts = self._extract_facts(verified)
        hypotheses = self._generate_hypotheses(verified, facts, timeline)
        hypotheses = self._compare_hypotheses(hypotheses, verified)
        rankings = self._rank_evidence(verified, hypotheses)
        missing_diags = self._identify_missing_diagnostics(verified, hypotheses)
        test_recs = self._recommend_tests(hypotheses, missing_diags)
        similar = self._check_similar_failures(state)
        claims = self._build_claims(hypotheses, verified)
        citations = self._build_citations(verified)
        confidence = self._calculate_confidence(hypotheses, verified)
        next_actions = self._build_actions(hypotheses, test_recs)

        output = ReasoningOutput(
            agent_name=self.name,
            reasoning_decision=self._decide(hypotheses, confidence),
            claims=claims,
            citations=citations,
            confidence_score=confidence,
            missing_evidence=missing_diags,
            confidence_signals=[
                ConfidenceSignal(
                    signal_name="hypothesis_count",
                    signal_value=min(len(hypotheses) / 5.0, 1.0),
                    weight=1.0,
                    reasoning=f"{len(hypotheses)} hypotheses generated",
                ),
                ConfidenceSignal(
                    signal_name="best_hypothesis_confidence",
                    signal_value=max((h.confidence_score for h in hypotheses), default=0.0),
                    weight=2.0,
                    reasoning="Confidence of the strongest hypothesis",
                ),
                ConfidenceSignal(
                    signal_name="timeline_events",
                    signal_value=min(len(timeline) / 10.0, 1.0),
                    weight=0.5,
                    reasoning=f"{len(timeline)} timeline events established",
                ),
            ],
            next_actions=next_actions,
            next_recommended_agents=(["lessons_learned_agent"] if similar else []),
            reasoning_summary=self._build_summary(hypotheses, timeline, test_recs, confidence),
            metadata={
                "timeline": [t.model_dump() for t in timeline],
                "hypotheses": [h.model_dump() for h in hypotheses],
                "evidence_rankings": [r.model_dump() for r in rankings],
                "test_recommendations": [t.model_dump() for t in test_recs],
                "similar_failures": similar,
                "extracted_facts": facts,
            },
        )

        self._store_reasoning_output(state, output)

        for claim in claims:
            state.setdefault("claims", [])
            state["claims"].append(claim)

        self.logger.info(
            f"RCA: {len(hypotheses)} hypotheses, "
            f"{len(timeline)} timeline events, "
            f"confidence={confidence:.2f}"
        )
        return state

    # ------------------------------------------------------------------
    # Timeline generation
    # ------------------------------------------------------------------

    def _build_timeline(self, evidence: list[EvidenceSource]) -> list[TimelineEvent]:
        """Build chronological timeline from evidence with temporal data."""
        events: list[TimelineEvent] = []

        for idx, source in enumerate(evidence):
            timestamp = source.metadata.get("timestamp") or source.metadata.get("occurred_at")
            if not timestamp:
                timestamp = f"unknown_{idx}"

            text = source.text_excerpt.strip()
            category = self._categorize_event(text)

            events.append(
                TimelineEvent(
                    event_id=f"tl_{uuid.uuid4().hex[:8]}",
                    timestamp=str(timestamp),
                    description=text,
                    source_evidence_ids=[source.provenance.evidence_region_id],
                    category=category,
                    confidence=source.confidence_score,
                )
            )

        events.sort(key=lambda e: e.timestamp)
        return events

    def _categorize_event(self, text: str) -> str:
        text_lower = text.lower()
        if any(w in text_lower for w in ["alarm", "fault", "fail", "error", "trip", "shutdown"]):
            return "symptom"
        if any(w in text_lower for w in ["repair", "replace", "maintain", "inspect", "service"]):
            return "action"
        if any(w in text_lower for w in ["temperature", "pressure", "flow", "vibration", "speed"]):
            return "condition"
        return "observation"

    # ------------------------------------------------------------------
    # Fact extraction
    # ------------------------------------------------------------------

    def _extract_facts(self, evidence: list[EvidenceSource]) -> list[str]:
        """Extract structured facts from verified evidence."""
        facts: list[str] = []
        seen: set[str] = set()

        for source in evidence:
            text = source.text_excerpt.strip()
            if not text or text.lower() in seen:
                continue
            seen.add(text.lower())
            facts.append(text)

        return facts

    # ------------------------------------------------------------------
    # Hypothesis generation
    # ------------------------------------------------------------------

    def _generate_hypotheses(
        self,
        evidence: list[EvidenceSource],
        facts: list[str],
        timeline: list[TimelineEvent],
    ) -> list[Hypothesis]:
        """Generate causal hypotheses from verified evidence.

        Uses pattern matching and temporal ordering to propose
        causal chains. Each hypothesis is grounded in evidence.
        """
        hypotheses: list[Hypothesis] = []
        symptom_events = [e for e in timeline if e.category == "symptom"]
        condition_events = [e for e in timeline if e.category == "condition"]
        action_events = [e for e in timeline if e.category == "action"]

        for _idx, symptom in enumerate(symptom_events):
            hyp_id = f"hyp_{uuid.uuid4().hex[:8]}"
            supporting = []
            contradicting = []
            causal_chain = []

            for cond in condition_events:
                if cond.timestamp <= symptom.timestamp:
                    supporting.append(
                        cond.source_evidence_ids[0] if cond.source_evidence_ids else ""
                    )
                    causal_chain.append(f"Condition: {cond.description[:80]}")

            for act in action_events:
                if act.timestamp > symptom.timestamp:
                    supporting.append(act.source_evidence_ids[0] if act.source_evidence_ids else "")
                    causal_chain.append(f"Follow-up action: {act.description[:80]}")

            causal_chain.append(f"Symptom: {symptom.description[:80]}")

            support_ratio = len(supporting) / max(len(evidence), 1)

            hypotheses.append(
                Hypothesis(
                    hypothesis_id=hyp_id,
                    text=f"Hypothesis: {symptom.description[:200]} may be caused by preceding conditions",
                    support_status="not_evaluated",
                    confidence_score=round(min(support_ratio * 2, 1.0), 3),
                    supporting_evidence_ids=[s for s in supporting if s],
                    contradicting_evidence_ids=contradicting,
                    reasoning=f"Based on {len(supporting)} supporting evidence items in timeline",
                    causal_chain=causal_chain,
                )
            )

        if not hypotheses and evidence:
            best_source = max(evidence, key=lambda s: s.confidence_score)
            hypotheses.append(
                Hypothesis(
                    hypothesis_id=f"hyp_{uuid.uuid4().hex[:8]}",
                    text=f"General hypothesis based on strongest evidence: {best_source.text_excerpt[:200]}",
                    support_status="not_evaluated",
                    confidence_score=best_source.confidence_score * 0.5,
                    supporting_evidence_ids=[best_source.provenance.evidence_region_id],
                    reasoning="Only general hypothesis possible with available evidence",
                )
            )

        return hypotheses

    # ------------------------------------------------------------------
    # Hypothesis comparison
    # ------------------------------------------------------------------

    def _compare_hypotheses(
        self,
        hypotheses: list[Hypothesis],
        evidence: list[EvidenceSource],
    ) -> list[Hypothesis]:
        """Compare hypotheses against evidence and update support status."""
        evidence_ids = {s.provenance.evidence_region_id for s in evidence}

        for hyp in hypotheses:
            supporting = [eid for eid in hyp.supporting_evidence_ids if eid in evidence_ids]
            contradicting = [eid for eid in hyp.contradicting_evidence_ids if eid in evidence_ids]

            hyp.supporting_evidence_ids = supporting
            hyp.contradicting_evidence_ids = contradicting

            if contradicting:
                hyp.support_status = "partially_supported"
            elif supporting and len(supporting) >= 2:
                hyp.support_status = "supported"
            elif supporting:
                hyp.support_status = "partially_supported"
            else:
                hyp.support_status = "not_evaluated"

        hypotheses.sort(key=lambda h: h.confidence_score, reverse=True)
        return hypotheses

    # ------------------------------------------------------------------
    # Evidence ranking
    # ------------------------------------------------------------------

    def _rank_evidence(
        self,
        evidence: list[EvidenceSource],
        hypotheses: list[Hypothesis],
    ) -> list[EvidenceRanking]:
        """Rank evidence by relevance to the leading hypothesis."""
        rankings: list[EvidenceRanking] = []
        if not hypotheses:
            return rankings

        leading = hypotheses[0]
        supporting_set = set(leading.supporting_evidence_ids)
        contradicting_set = set(leading.contradicting_evidence_ids)

        for idx, source in enumerate(evidence):
            eid = source.provenance.evidence_region_id
            role = "context"
            if eid in supporting_set:
                role = "supporting"
            elif eid in contradicting_set:
                role = "contradicting"
            elif source.relevance_score >= 0.7:
                role = "contributing_factor"

            rankings.append(
                EvidenceRanking(
                    evidence_index=idx,
                    relevance_score=source.relevance_score,
                    role=role,
                    reasoning=f"Ranked for leading hypothesis {leading.hypothesis_id}",
                )
            )

        rankings.sort(key=lambda r: r.relevance_score, reverse=True)
        return rankings

    # ------------------------------------------------------------------
    # Missing diagnostic identification
    # ------------------------------------------------------------------

    def _identify_missing_diagnostics(
        self,
        evidence: list[EvidenceSource],
        hypotheses: list[Hypothesis],
    ) -> list[MissingEvidence]:
        missing: list[MissingEvidence] = []

        source_types = {s.metadata.get("type", "unknown") for s in evidence}

        if "sensor_data" not in source_types:
            missing.append(
                MissingEvidence(
                    evidence_type="sensor_data",
                    description="No real-time sensor data available for analysis",
                    suggested_action="Retrieve recent sensor readings for the target asset",
                    priority="high",
                )
            )

        if "maintenance_log" not in source_types:
            missing.append(
                MissingEvidence(
                    evidence_type="maintenance_log",
                    description="No maintenance log entries available",
                    suggested_action="Retrieve maintenance history for the asset",
                    priority="medium",
                )
            )

        if len(hypotheses) > 1:
            contradicting = [h for h in hypotheses if h.contradicting_evidence_ids]
            if contradicting:
                missing.append(
                    MissingEvidence(
                        evidence_type="disambiguation_evidence",
                        description=(
                            f"{len(contradicting)} hypotheses have contradicting evidence; "
                            "additional data needed to discriminate"
                        ),
                        suggested_action="Perform targeted diagnostic tests",
                        priority="high",
                    )
                )

        if len(evidence) < 3:
            missing.append(
                MissingEvidence(
                    evidence_type="additional_corroboration",
                    description="Insufficient evidence for reliable root cause analysis",
                    suggested_action="Retrieve additional evidence from multiple source types",
                    priority="high",
                )
            )

        return missing

    # ------------------------------------------------------------------
    # Test recommendations
    # ------------------------------------------------------------------

    def _recommend_tests(
        self,
        hypotheses: list[Hypothesis],
        missing: list[MissingEvidence],
    ) -> list[TestRecommendation]:
        recs: list[TestRecommendation] = []

        for hyp in hypotheses[:3]:
            if hyp.support_status in ("not_evaluated", "partially_supported"):
                recs.append(
                    TestRecommendation(
                        test_id=f"test_{uuid.uuid4().hex[:8]}",
                        description=f"Diagnostic test to validate: {hyp.text[:120]}",
                        target_hypothesis_ids=[hyp.hypothesis_id],
                        priority="high" if hyp.confidence_score >= 0.5 else "medium",
                        expected_outcome="Evidence that supports or refutes the hypothesis",
                        reasoning=f"Hypothesis has confidence {hyp.confidence_score:.2f} "
                        f"and status '{hyp.support_status}'",
                    )
                )

        missing_types = {m.evidence_type for m in missing}
        if "sensor_data" in missing_types:
            recs.append(
                TestRecommendation(
                    test_id=f"test_{uuid.uuid4().hex[:8]}",
                    description="Collect real-time sensor data for temporal correlation",
                    target_hypothesis_ids=[],
                    priority="high",
                    expected_outcome="Time-series data to validate causal chain",
                    reasoning="Sensor data missing from evidence bundle",
                )
            )

        return recs

    # ------------------------------------------------------------------
    # Similar failure reasoning
    # ------------------------------------------------------------------

    def _check_similar_failures(self, state: AgentState) -> list[dict[str, Any]]:
        """Check for similar historical failures via previous reasoning outputs."""
        previous = self._get_previous_reasoning(state, "lessons_learned_agent")
        similar: list[dict[str, Any]] = []
        for output in previous:
            comparisons = output.metadata.get("historical_comparisons", [])
            for comp in comparisons:
                if comp.get("similarity_score", 0) >= 0.6:
                    similar.append(comp)
        return similar

    # ------------------------------------------------------------------
    # Claims
    # ------------------------------------------------------------------

    def _build_claims(
        self,
        hypotheses: list[Hypothesis],
        evidence: list[EvidenceSource],
    ) -> list[GroundedClaim]:
        claims: list[GroundedClaim] = []

        for hyp in hypotheses:
            if hyp.support_status == "not_evaluated":
                status = ClaimSupportStatus.UNCERTAIN
            elif hyp.support_status == "supported":
                status = ClaimSupportStatus.SUPPORTED
            elif hyp.support_status == "partially_supported":
                status = ClaimSupportStatus.PARTIALLY_SUPPORTED
            elif hyp.support_status == "refuted":
                status = ClaimSupportStatus.REFUTED
            else:
                status = ClaimSupportStatus.NO_EVIDENCE

            sources = [
                s
                for s in evidence
                if s.provenance.evidence_region_id in hyp.supporting_evidence_ids
            ]

            if not sources and evidence:
                sources = [evidence[0]]

            claims.append(
                GroundedClaim(
                    claim_id=hyp.hypothesis_id,
                    text=hyp.text,
                    status=status,
                    sources=sources[:5],
                    reasoning=hyp.reasoning,
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
        hypotheses: list[Hypothesis],
        evidence: list[EvidenceSource],
    ) -> float:
        if not hypotheses:
            return 0.0

        best_conf = max(h.confidence_score for h in hypotheses)
        evidence_quality = (
            sum(s.confidence_score for s in evidence) / len(evidence) if evidence else 0.0
        )
        has_supported = any(
            h.support_status in ("supported", "partially_supported") for h in hypotheses
        )

        confidence = (
            0.5 * best_conf + 0.3 * evidence_quality + 0.2 * (1.0 if has_supported else 0.2)
        )
        return round(min(confidence, 1.0), 3)

    # ------------------------------------------------------------------
    # Decision
    # ------------------------------------------------------------------

    def _decide(self, hypotheses: list[Hypothesis], confidence: float) -> ReasoningDecision:
        if not hypotheses:
            return ReasoningDecision.ABSTAIN

        best = hypotheses[0]
        if best.support_status == "supported" and confidence >= 0.7:
            return ReasoningDecision.SUFFICIENT
        if confidence < 0.3:
            return ReasoningDecision.REQUEST_EVIDENCE
        if best.support_status == "not_evaluated":
            return ReasoningDecision.REQUEST_EVIDENCE
        return ReasoningDecision.SUFFICIENT

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _build_actions(
        self,
        hypotheses: list[Hypothesis],
        test_recs: list[TestRecommendation],
    ) -> list[RecommendedAction]:
        actions: list[RecommendedAction] = []

        for rec in test_recs[:3]:
            actions.append(
                RecommendedAction(
                    action_id=f"act_{uuid.uuid4().hex[:8]}",
                    type="TEST",
                    description=rec.description,
                    priority=rec.priority,
                    reasoning=rec.reasoning,
                )
            )

        if hypotheses and hypotheses[0].support_status == "partially_supported":
            actions.append(
                RecommendedAction(
                    action_id=f"act_{uuid.uuid4().hex[:8]}",
                    type="INSPECTION",
                    description="Physical inspection to validate leading hypothesis",
                    priority="high",
                    reasoning="Leading hypothesis is only partially supported by available evidence",
                )
            )

        return actions

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _build_summary(
        self,
        hypotheses: list[Hypothesis],
        timeline: list[TimelineEvent],
        test_recs: list[TestRecommendation],
        confidence: float,
    ) -> str:
        parts = [
            f"RCA generated {len(hypotheses)} hypotheses from {len(timeline)} timeline events.",
        ]
        if hypotheses:
            best = hypotheses[0]
            parts.append(f"Leading hypothesis ({best.confidence_score:.2f}): {best.text[:100]}")
            parts.append(f"Support status: {best.support_status}")
        parts.append(f"Recommended {len(test_recs)} diagnostic tests.")
        parts.append(f"Overall confidence: {confidence:.2f}")
        if confidence < 0.5:
            parts.append("Insufficient confidence for definitive conclusion.")
        return " ".join(parts)
