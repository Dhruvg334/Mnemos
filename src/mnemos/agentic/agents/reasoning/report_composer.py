"""Report Composer Agent.

Final-stage agent that synthesizes outputs from all reasoning agents
into a single coherent ``FinalReport``. Gathers claims, citations,
contradictions, and recommendations from every reasoning stage,
deduplicates and prioritizes them, computes overall confidence, and
produces a structured report with summary and confidence statement.

This is the last agent in the pipeline before human approval and
final response delivery.
"""

from __future__ import annotations

import uuid

from mnemos.agentic.agents.reasoning._base import _BaseReasoningAgent
from mnemos.agentic.runtime.types import AgentCapability, AgentRole
from mnemos.agentic.schemas.base import (
    Citation,
    ClaimSupportStatus,
    Contradiction,
    GroundedClaim,
    ReasoningDecision,
    ReasoningOutput,
    RecommendedAction,
)
from mnemos.agentic.schemas.specialized import FinalReport
from mnemos.agentic.schemas.state import AgentState


# Priority ordering used when sorting recommended actions.
_PRIORITY_ORDER: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}


class ReportComposerAgent(_BaseReasoningAgent):
    """Final report composition agent.

    Synthesizes outputs from all reasoning agents into a single
    coherent investigation report. This is the last agent in the
    pipeline before human approval and final response.

    Pipeline:
    1. Gather all reasoning outputs from the shared context.
    2. Merge and deduplicate claims, citations, contradictions, and actions.
    3. Compute overall confidence from weighted agent confidences.
    4. Build a human-readable summary and confidence statement.
    5. Store the ``FinalReport`` and the final ``ReasoningOutput`` in context.
    """

    name = "report_composer"
    role = AgentRole.COMPOSITION
    description = (
        "Synthesizes all agent outputs into a final investigation report "
        "with grounded claims, citations, contradictions, recommended "
        "actions, and an overall confidence assessment."
    )
    timeout_seconds = 120.0

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def _capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability(
                name="report_composition",
                description=(
                    "Gathers reasoning outputs from all analysis agents, "
                    "deduplicates claims and citations, merges contradictions "
                    "and actions, and produces a structured FinalReport."
                ),
                input_types=["reasoning_outputs", "context"],
                output_types=["final_report", "reasoning_output"],
                dependencies=[],
            ),
        ]

    @property
    def required_dependencies(self) -> list[str]:
        return []

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, state: AgentState) -> AgentState:
        outputs = self._gather_reasoning_outputs(state)

        if not outputs:
            report = self._build_empty_report(state)
            self._store_final(state, report, [])
            self.logger.info("Report composition: no reasoning outputs found; empty report emitted.")
            return state

        report = self._synthesize_report(outputs, state)
        self._store_final(state, report, outputs)

        self.logger.info(
            f"Report composed: {len(report.grounded_claims)} claims, "
            f"{len(report.recommended_actions)} actions, "
            f"{len(report.contradictions)} contradictions, "
            f"confidence={report.confidence_statement}"
        )
        return state

    # ------------------------------------------------------------------
    # Gathering
    # ------------------------------------------------------------------

    def _gather_reasoning_outputs(self, state: AgentState) -> list[ReasoningOutput]:
        """Extract all reasoning outputs from state context.

        Reads from ``context["reasoning_outputs"]`` and falls back to the
        base-class helper. Returns an empty list when nothing is available.
        """
        ctx = state.get("context", {})
        outputs: list[ReasoningOutput] = ctx.get("reasoning_outputs", [])
        if outputs:
            return outputs
        return self._get_previous_reasoning(state)

    def _gather_approval_decisions(self, state: AgentState) -> list[dict[str, Any]]:
        """Collect human approval decisions from the audit log.

        Returns a list of dicts with gate_type, decision, reviewer,
        comments, and timestamp for every approval event.
        """
        ctx = state.get("context", {})
        decisions: list[dict[str, Any]] = []

        # Check state for approval result
        approval_result = state.get("approval_result")
        if approval_result and isinstance(approval_result, dict):
            decisions.append({
                "gate_type": approval_result.get("gate_type", "unknown"),
                "decision": approval_result.get("decision", "unknown"),
                "reviewer": approval_result.get("reviewer", "unknown"),
                "comments": approval_result.get("comments", ""),
                "timestamp": str(approval_result.get("timestamp", "")),
            })

        # Check pending approval request
        pending = state.get("pending_approval_request")
        if pending and isinstance(pending, dict):
            decisions.append({
                "gate_type": pending.get("gate_type", "unknown"),
                "decision": "pending",
                "reviewer": pending.get("reviewer", ""),
                "comments": pending.get("summary", ""),
                "timestamp": "",
            })

        # Check approval_required flag
        if state.get("approval_required") and not decisions:
            gate_type = ctx.get("approval_gate_type", "unknown")
            decisions.append({
                "gate_type": gate_type,
                "decision": "pending",
                "reviewer": "",
                "comments": "Approval required but not yet processed",
                "timestamp": "",
            })

        return decisions

    def _gather_document_versions(
        self,
        citations: list[Citation],
    ) -> list[dict[str, Any]]:
        """Extract document version information from citations.

        Groups citations by document_id and reports the version,
        whether it's the latest, and how many citations reference it.
        """
        doc_versions: dict[str, dict[str, Any]] = {}
        for citation in citations:
            doc_id = citation.document_id
            if not doc_id:
                continue
            if doc_id not in doc_versions:
                doc_versions[doc_id] = {
                    "document_id": doc_id,
                    "version": citation.document_version,
                    "is_latest_version": getattr(
                        citation, "is_latest_version", True
                    ),
                    "citation_count": 0,
                    "titles": set(),
                }
            entry = doc_versions[doc_id]
            entry["citation_count"] += 1
            if citation.text_excerpt:
                # Use first 80 chars as a title hint
                entry["titles"].add(citation.text_excerpt[:80])

        # Convert sets to lists for JSON serialization
        result: list[dict[str, Any]] = []
        for doc_id, info in doc_versions.items():
            info["titles"] = list(info["titles"])
            result.append(info)
        return result

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    def _synthesize_report(
        self,
        reasoning_outputs: list[ReasoningOutput],
        state: AgentState,
    ) -> FinalReport:
        """Synthesize all reasoning outputs into a ``FinalReport."""
        query = state.get("query", "Investigation Report")
        title = self._build_title(query)

        merged_claims = self._merge_claims(reasoning_outputs)
        merged_citations = self._merge_citations(reasoning_outputs)
        merged_contradictions = self._merge_contradictions(reasoning_outputs)
        merged_actions = self._merge_recommendations(reasoning_outputs)
        missing_evidence = self._collect_missing_evidence(reasoning_outputs)

        confidence = self._compute_overall_confidence(reasoning_outputs, state)
        summary = self._build_summary_from_outputs(reasoning_outputs, merged_claims)
        confidence_statement = self._build_confidence_statement(confidence)
        disclaimer = self._build_disclaimer(confidence)

        # Gather approval decisions from audit log
        approval_decisions = self._gather_approval_decisions(state)

        # Gather document version information from citations
        document_versions = self._gather_document_versions(merged_citations)

        sections: dict[str, object] = {}
        for output in reasoning_outputs:
            agent_name = output.agent_name
            sections[agent_name] = {
                "summary": output.reasoning_summary,
                "decision": output.reasoning_decision,
                "confidence": output.confidence_score,
                "claims_count": len(output.claims),
                "citations_count": len(output.citations),
                "metadata": output.metadata,
            }

        return FinalReport(
            title=title,
            summary=summary,
            sections=sections,
            grounded_claims=merged_claims,
            recommended_actions=merged_actions,
            contradictions=merged_contradictions,
            missing_evidence=missing_evidence,
            confidence_statement=confidence_statement,
            disclaimer=disclaimer,
            approval_decisions=approval_decisions,
            document_versions=document_versions,
        )

    # ------------------------------------------------------------------
    # Merge: claims
    # ------------------------------------------------------------------

    def _merge_claims(
        self,
        outputs: list[ReasoningOutput],
    ) -> list[GroundedClaim]:
        """Merge claims from all reasoning agents, deduplicating.

        Deduplication key: ``claim_id``.  When duplicate IDs appear the
        claim with the strongest support status wins (SUPPORTED >
        PARTIALLY_SUPPORTED > UNCERTAIN > REFUTED > NO_EVIDENCE).
        """
        _status_rank: dict[str, int] = {
            ClaimSupportStatus.SUPPORTED: 0,
            ClaimSupportStatus.PARTIALLY_SUPPORTED: 1,
            ClaimSupportStatus.UNCERTAIN: 2,
            ClaimSupportStatus.REFUTED: 3,
            ClaimSupportStatus.NO_EVIDENCE: 4,
        }

        best_by_id: dict[str, GroundedClaim] = {}
        for output in outputs:
            for claim in output.claims:
                existing = best_by_id.get(claim.claim_id)
                if existing is None:
                    best_by_id[claim.claim_id] = claim
                else:
                    existing_rank = _status_rank.get(existing.status, 5)
                    new_rank = _status_rank.get(claim.status, 5)
                    if new_rank < existing_rank:
                        best_by_id[claim.claim_id] = claim

        return list(best_by_id.values())

    # ------------------------------------------------------------------
    # Merge: citations
    # ------------------------------------------------------------------

    def _merge_citations(
        self,
        outputs: list[ReasoningOutput],
    ) -> list[Citation]:
        """Merge citations from all agents, deduplicating by citation_id."""
        seen: dict[str, Citation] = {}
        for output in outputs:
            for citation in output.citations:
                if citation.citation_id not in seen:
                    seen[citation.citation_id] = citation
        return list(seen.values())

    # ------------------------------------------------------------------
    # Merge: contradictions
    # ------------------------------------------------------------------

    def _merge_contradictions(
        self,
        outputs: list[ReasoningOutput],
    ) -> list[Contradiction]:
        """Merge contradictions from all agents, keeping unique entries."""
        seen: dict[str, Contradiction] = {}
        for output in outputs:
            for contradiction in output.contradictions:
                if contradiction.contradiction_id not in seen:
                    seen[contradiction.contradiction_id] = contradiction
        return list(seen.values())

    # ------------------------------------------------------------------
    # Merge: recommendations
    # ------------------------------------------------------------------

    def _merge_recommendations(
        self,
        outputs: list[ReasoningOutput],
    ) -> list[RecommendedAction]:
        """Merge and prioritize recommended actions.

        Actions are deduplicated by description text (after stripping)
        and sorted by priority: critical > high > medium > low.
        """
        seen_descriptions: dict[str, RecommendedAction] = {}
        all_actions: list[RecommendedAction] = []

        for output in outputs:
            for action in output.next_actions:
                key = action.description.strip().lower()
                if key not in seen_descriptions:
                    seen_descriptions[key] = action
                    all_actions.append(action)

        all_actions.sort(key=lambda a: _PRIORITY_ORDER.get(a.priority, 99))
        return all_actions

    # ------------------------------------------------------------------
    # Missing evidence
    # ------------------------------------------------------------------

    def _collect_missing_evidence(
        self,
        outputs: list[ReasoningOutput],
    ) -> list[str]:
        """Collect all missing-evidence descriptions from every output."""
        descriptions: list[str] = []
        seen: set[str] = set()
        for output in outputs:
            for missing in output.missing_evidence:
                desc = missing.description.strip()
                if desc and desc not in seen:
                    seen.add(desc)
                    descriptions.append(desc)
        return descriptions

    # ------------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------------

    def _compute_overall_confidence(
        self,
        outputs: list[ReasoningOutput],
        state: AgentState,
    ) -> float:
        """Compute weighted average confidence across all agents.

        Each reasoning agent contributes equally.  If an evidence bundle
        with its own confidence signals exists, the bundle score is
        blended in with a small weight to anchor the overall assessment.
        """
        if not outputs:
            return 0.0

        agent_scores = [o.confidence_score for o in outputs]
        agent_avg = sum(agent_scores) / len(agent_scores)

        ctx = state.get("context", {})
        bundle = ctx.get("evidence_bundle")
        bundle_confidence: float | None = None
        if bundle is not None:
            signals = getattr(bundle, "confidence_signals", [])
            if signals:
                total_weight = sum(s.weight for s in signals)
                if total_weight > 0:
                    bundle_confidence = sum(
                        s.signal_value * s.weight for s in signals
                    ) / total_weight

        if bundle_confidence is not None:
            overall = 0.85 * agent_avg + 0.15 * bundle_confidence
        else:
            overall = agent_avg

        return round(min(max(overall, 0.0), 1.0), 3)

    # ------------------------------------------------------------------
    # Title
    # ------------------------------------------------------------------

    def _build_title(self, query: str) -> str:
        """Derive a report title from the original query."""
        cleaned = query.strip()
        if not cleaned:
            return "Investigation Report"
        if len(cleaned) > 120:
            cleaned = cleaned[:117] + "..."
        return f"Investigation Report: {cleaned}"

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _build_summary_from_outputs(
        self,
        outputs: list[ReasoningOutput],
        claims: list[GroundedClaim],
    ) -> str:
        """Build a human-readable summary listing key findings per section."""
        parts: list[str] = []

        parts.append(
            f"This report synthesizes findings from {len(outputs)} reasoning "
            f"agent(s) and presents {len(claims)} grounded claim(s)."
        )

        for output in outputs:
            agent_label = output.agent_name.replace("_", " ").title()
            parts.append(
                f"\n**{agent_label}** ({output.reasoning_decision}): "
                f"{output.reasoning_summary}"
            )

        supported = sum(
            1 for c in claims if c.status == ClaimSupportStatus.SUPPORTED
        )
        refuted = sum(
            1 for c in claims if c.status == ClaimSupportStatus.REFUTED
        )
        uncertain = sum(
            1 for c in claims if c.status == ClaimSupportStatus.UNCERTAIN
        )
        parts.append(
            f"\nOverall: {supported} supported, {refuted} refuted, "
            f"{uncertain} uncertain claim(s)."
        )

        return " ".join(parts)

    # ------------------------------------------------------------------
    # Confidence statement
    # ------------------------------------------------------------------

    def _build_confidence_statement(self, confidence: float) -> str:
        """Map numeric confidence to a verbal statement."""
        if confidence > 0.9:
            level = "Very High"
        elif confidence > 0.75:
            level = "High"
        elif confidence > 0.5:
            level = "Medium"
        elif confidence > 0.3:
            level = "Low"
        else:
            level = "Very Low"
        return f"{level} confidence ({confidence:.0%})"

    # ------------------------------------------------------------------
    # Disclaimer
    # ------------------------------------------------------------------

    def _build_disclaimer(self, confidence: float) -> str:
        """Generate a disclaimer noting the report requires human validation."""
        base = (
            "This report was automatically generated from verified evidence "
            "and reasoning agent outputs. All findings require human "
            "validation before acting on recommendations."
        )
        if confidence < 0.5:
            return (
                f"{base} WARNING: Overall confidence is low "
                f"({confidence:.0%}); additional evidence or expert review "
                f"is strongly recommended."
            )
        return base

    # ------------------------------------------------------------------
    # Empty report
    # ------------------------------------------------------------------

    def _build_empty_report(self, state: AgentState) -> FinalReport:
        """Build a minimal report when no reasoning outputs exist."""
        query = state.get("query", "Investigation Report")
        title = self._build_title(query)
        return FinalReport(
            title=title,
            summary=(
                "No reasoning agent outputs were available for composition. "
                "The investigation may not have progressed beyond evidence "
                "retrieval."
            ),
            sections={},
            grounded_claims=[],
            recommended_actions=[],
            contradictions=[],
            missing_evidence=[],
            confidence_statement=self._build_confidence_statement(0.0),
            disclaimer=self._build_disclaimer(0.0),
        )

    # ------------------------------------------------------------------
    # State storage
    # ------------------------------------------------------------------

    def _store_final(
        self,
        state: AgentState,
        report: FinalReport,
        outputs: list[ReasoningOutput],
    ) -> AgentState:
        """Persist the final report and reasoning output in state context."""
        ctx = dict(state.get("context", {}))
        ctx["final_report"] = report
        ctx["reasoning_outputs"] = outputs

        output = ReasoningOutput(
            agent_name=self.name,
            reasoning_decision=ReasoningDecision.SUFFICIENT,
            claims=report.grounded_claims,
            citations=self._merge_citations(outputs),
            confidence_score=(
                report.grounded_claims[0].sources[0].confidence_score
                if report.grounded_claims and report.grounded_claims[0].sources
                else 0.0
            ),
            missing_evidence=[],
            contradictions=report.contradictions,
            next_actions=report.recommended_actions,
            next_recommended_agents=[],
            reasoning_summary=report.summary,
            metadata={
                "report_title": report.title,
                "total_claims": len(report.grounded_claims),
                "total_actions": len(report.recommended_actions),
                "total_contradictions": len(report.contradictions),
                "total_missing": len(report.missing_evidence),
                "confidence_statement": report.confidence_statement,
            },
        )
        ctx["reasoning_output"] = output
        state["context"] = ctx
        return state
