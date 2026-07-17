"""Retrieval Reflection Agent.

Evaluates the evidence collected so far and determines the next action.
This is the decision hub of the retrieval intelligence layer.

Exit paths:
- SUFFICIENT: Evidence meets all quality thresholds
- RETRIEVE_AGAIN: Evidence count too low, try same strategies
- EXPAND_GRAPH: Graph traversal insufficient, try additional graph types or multi-hop
- CHANGE_STRATEGY: Current strategies are ineffective, suggest different ones
- ASK_CLARIFICATION: Query is too ambiguous, ask user for clarification
- ABSTAIN: Cannot find sufficient evidence even after retries
"""

from __future__ import annotations

from typing import Any

from mnemos.agentic.agents.retrieval._base import _BaseRetrievalAgent
from mnemos.agentic.runtime.types import (
    AgentCapability,
    AgentRole,
    InvestigationPhase,
    ReplanRequest,
)
from mnemos.agentic.schemas.base import (
    EvidenceBundle,
    ReflectionDecision,
    RetrievalPlan,
    RetrievalStrategy,
)
from mnemos.agentic.schemas.state import AgentState
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("agents.retrieval_reflection")

# Maximum retries before abstaining
MAX_RETRIEVAL_RETRIES = 3


class RetrievalReflectionAgent(_BaseRetrievalAgent):
    """Evaluates evidence sufficiency and decides the next retrieval action.

    Decision logic:
    1. If evidence meets all thresholds -> SUFFICIENT
    2. If evidence count is low but strategies worked -> RETRIEVE_AGAIN
    3. If graph data is sparse -> EXPAND_GRAPH
    4. If current strategies produced nothing useful -> CHANGE_STRATEGY
    5. If query is too vague -> ASK_CLARIFICATION
    6. If max retries exceeded -> ABSTAIN

    Reads from state:
    - ``context["evidence_bundle"]`` (verified ``EvidenceBundle``)
    - ``context["retrieval_plan"]`` (the plan that produced the evidence)
    - ``context["retrieval_retries"]`` (number of previous retry attempts)
    - ``evidence`` list

    Writes to state:
    - ``context["retrieval_sufficient"]`` (bool)
    - ``context["retrieval_decision"]`` (``ReflectionDecision``)
    - ``context["retrieval_gaps"]`` (list of gap descriptions)
    - ``context["retrieval_assessment"]`` (detailed assessment)
    - ``replan_requests`` (if action needed)
    """

    name = "retrieval_reflection"
    role = AgentRole.VERIFICATION
    description = (
        "Evaluates retrieval evidence and decides next action: "
        "sufficient, retry, expand graph, change strategy, "
        "ask clarification, or abstain."
    )
    timeout_seconds = 30.0

    def _capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability(
                name="retrieval_reflection",
                description=(
                    "Assesses evidence quality, identifies gaps, "
                    "and recommends next retrieval action."
                ),
                input_types=["evidence_bundle", "retrieval_plan"],
                output_types=["retrieval_assessment", "replan_request"],
                dependencies=["evidence_verification"],
            ),
        ]

    @property
    def required_dependencies(self) -> list[str]:
        return ["evidence_verification"]

    async def execute(self, state: AgentState) -> AgentState:
        ctx = dict(state.get("context", {}))
        bundle: EvidenceBundle | None = ctx.get("evidence_bundle")
        plan: RetrievalPlan | None = ctx.get("retrieval_plan")
        retries = ctx.get("retrieval_retries", 0)

        if bundle is None or plan is None:
            ctx["retrieval_sufficient"] = False
            ctx["retrieval_decision"] = ReflectionDecision.ABSTAIN
            ctx["retrieval_gaps"] = ["No evidence bundle or plan available"]
            state["context"] = ctx
            return state

        verified = bundle.verified_evidence
        raw_count = len(bundle.raw_vector_data) + len(bundle.raw_graph_data)

        # ---- Assess evidence quality -----------------------------------
        gaps = self._identify_gaps(bundle, plan, verified, raw_count)
        assessment = self._build_assessment(bundle, plan, verified, raw_count, gaps)

        # ---- Make decision ---------------------------------------------
        decision = self._make_decision(
            gaps=gaps,
            bundle=bundle,
            plan=plan,
            retries=retries,
            assessment=assessment,
        )

        # ---- Build replan request if needed ----------------------------
        sufficient = decision == ReflectionDecision.SUFFICIENT

        if not sufficient:
            replan = self._build_replan(plan, gaps, ctx, decision)
            replan_requests = list(state.get("replan_requests", []))
            replan_requests.append(replan)
            state["replan_requests"] = replan_requests

            # Increment retry counter
            ctx["retrieval_retries"] = retries + 1

        # ---- Update state ----------------------------------------------
        ctx["retrieval_sufficient"] = sufficient
        ctx["retrieval_decision"] = decision.value
        ctx["retrieval_gaps"] = gaps
        ctx["retrieval_assessment"] = assessment
        state["context"] = ctx

        logger.info(
            f"Retrieval reflection: decision={decision.value}, "
            f"verified={len(verified)}, avg_conf={assessment['avg_confidence']:.2f}, "
            f"gaps={len(gaps)}, retries={retries}"
        )

        return state

    # ------------------------------------------------------------------
    # Gap identification
    # ------------------------------------------------------------------

    def _identify_gaps(
        self,
        bundle: EvidenceBundle,
        plan: RetrievalPlan,
        verified: list,
        raw_count: int,
    ) -> list[str]:
        """Identify all gaps in the evidence."""
        gaps: list[str] = []

        # Count check
        if len(verified) < plan.min_evidence_count:
            gaps.append(
                f"Insufficient verified evidence: {len(verified)}/{plan.min_evidence_count} required"
            )

        # Confidence check
        avg_confidence = (
            sum(s.confidence_score for s in verified) / len(verified)
            if verified
            else 0.0
        )
        if avg_confidence < plan.min_average_confidence:
            gaps.append(
                f"Average confidence too low: {avg_confidence:.2f}/{plan.min_average_confidence}"
            )

        # Empty results
        if raw_count == 0:
            gaps.append("No raw candidates retrieved by any strategy")

        # Entity resolution failure
        if not bundle.resolved_entities and plan.target_entities:
            gaps.append(
                f"Entity resolution failed for {len(plan.target_entities)} mentions"
            )

        # All strategies empty
        if plan.strategies and not bundle.raw_vector_data and not bundle.raw_graph_data:
            gaps.append("All retrieval strategies returned empty results")

        # Source diversity
        sources_used: set[str] = set()
        for v in bundle.raw_vector_data:
            sources_used.add(v.get("metadata", {}).get("type", "vector"))
        for _eid in bundle.raw_graph_data:
            sources_used.add("graph")
        if len(plan.strategies) > 2 and len(sources_used) < 2:
            gaps.append(
                f"Limited source diversity: {len(sources_used)} source types from "
                f"{len(plan.strategies)} strategies"
            )

        # Graph-specific gaps
        if RetrievalStrategy.GRAPH_TRAVERSAL in plan.strategies:
            if not bundle.raw_graph_data:
                gaps.append("No graph traversal results returned")
            elif all(
                not data.get("nodes") for data in bundle.raw_graph_data.values()
            ):
                gaps.append("Graph traversal returned empty nodes")

        # Contradiction check
        if bundle.contradictions:
            high_severity = [
                c for c in bundle.contradictions if c.severity == "high"
            ]
            if high_severity:
                gaps.append(
                    f"{len(high_severity)} high-severity contradictions detected"
                )

        # Missing evidence
        if bundle.missing_evidence:
            high_priority_missing = [
                m for m in bundle.missing_evidence if m.priority == "high"
            ]
            if high_priority_missing:
                gaps.append(
                    f"{len(high_priority_missing)} high-priority missing evidence types"
                )

        return gaps

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def _build_assessment(
        self,
        bundle: EvidenceBundle,
        plan: RetrievalPlan,
        verified: list,
        raw_count: int,
        gaps: list[str],
    ) -> dict[str, Any]:
        """Build detailed assessment dict."""
        avg_confidence = (
            sum(s.confidence_score for s in verified) / len(verified)
            if verified
            else 0.0
        )
        avg_relevance = (
            sum(s.relevance_score for s in verified) / len(verified)
            if verified
            else 0.0
        )

        sources_used: set[str] = set()
        for v in bundle.raw_vector_data:
            sources_used.add(v.get("metadata", {}).get("type", "vector"))
        for _eid in bundle.raw_graph_data:
            sources_used.add("graph")

        return {
            "verified_count": len(verified),
            "raw_candidate_count": raw_count,
            "avg_confidence": round(avg_confidence, 3),
            "avg_relevance": round(avg_relevance, 3),
            "source_diversity": len(sources_used),
            "contradiction_count": len(bundle.contradictions),
            "citation_count": len(bundle.citations),
            "missing_evidence_count": len(bundle.missing_evidence),
            "gaps": gaps,
            "sufficient": len(gaps) == 0,
        }

    # ------------------------------------------------------------------
    # Decision making
    # ------------------------------------------------------------------

    def _make_decision(
        self,
        gaps: list[str],
        bundle: EvidenceBundle,
        plan: RetrievalPlan,
        retries: int,
        assessment: dict[str, Any],
    ) -> ReflectionDecision:
        """Decide the next action based on evidence quality."""

        # No gaps -> sufficient
        if not gaps:
            return ReflectionDecision.SUFFICIENT

        # Max retries exceeded -> abstain
        if retries >= MAX_RETRIEVAL_RETRIES:
            return ReflectionDecision.ABSTAIN

        # Query too vague -> ask clarification
        if self._is_query_ambiguous(bundle, plan):
            return ReflectionDecision.ASK_CLARIFICATION

        # Graph data is sparse but graph traversal was requested
        if self._needs_graph_expansion(gaps, bundle, plan):
            return ReflectionDecision.EXPAND_GRAPH

        # Current strategies produced nothing useful
        if self._needs_strategy_change(gaps, bundle, plan):
            return ReflectionDecision.CHANGE_STRATEGY

        # Default: try retrieving again with same strategies
        return ReflectionDecision.RETRIEVE_AGAIN

    def _is_query_ambiguous(
        self, bundle: EvidenceBundle, plan: RetrievalPlan
    ) -> bool:
        """Check if the query is too ambiguous to retrieve meaningfully."""
        # No entities extracted and no vector results -> query might be too vague
        no_entities = not bundle.resolved_entities and plan.target_entities
        no_vector = not bundle.raw_vector_data
        no_graph = not bundle.raw_graph_data
        return no_entities and no_vector and no_graph

    def _needs_graph_expansion(
        self,
        gaps: list[str],
        bundle: EvidenceBundle,
        plan: RetrievalPlan,
    ) -> bool:
        """Check if graph expansion would help."""
        has_graph_gap = any("graph" in g.lower() for g in gaps)
        graph_requested = RetrievalStrategy.GRAPH_TRAVERSAL in plan.strategies
        sparse_graph = (
            bundle.raw_graph_data
            and all(
                len(data.get("nodes", [])) < 3
                for data in bundle.raw_graph_data.values()
            )
        )
        return (has_graph_gap or sparse_graph) and graph_requested

    def _needs_strategy_change(
        self,
        gaps: list[str],
        bundle: EvidenceBundle,
        plan: RetrievalPlan,
    ) -> bool:
        """Check if different strategies would help."""
        # All strategies returned empty
        if any("empty results" in g for g in gaps):
            return True

        # Very low source diversity
        if any("source diversity" in g for g in gaps):
            return True

        # Entity resolution failed
        if any("Entity resolution failed" in g for g in gaps):
            return True

        return False

    # ------------------------------------------------------------------
    # Replan construction
    # ------------------------------------------------------------------

    def _build_replan(
        self,
        original_plan: RetrievalPlan,
        gaps: list[str],
        ctx: dict[str, Any],
        decision: ReflectionDecision,
    ) -> ReplanRequest:
        """Construct a replanning request based on the decision."""
        suggested_agents: list[str] = []
        phase = InvestigationPhase.EVIDENCE_GATHERING

        if decision == ReflectionDecision.RETRIEVE_AGAIN:
            suggested_agents.append("evidence_retrieval")

        elif decision == ReflectionDecision.EXPAND_GRAPH:
            suggested_agents.append("evidence_retrieval")
            # Planner should add MULTI_HOP and specific graph types
            suggested_agents.append("retrieval_planner")

        elif decision == ReflectionDecision.CHANGE_STRATEGY:
            if any("Entity resolution failed" in g for g in gaps):
                suggested_agents.append("query_router")
            suggested_agents.append("retrieval_planner")
            suggested_agents.append("evidence_retrieval")

        elif decision == ReflectionDecision.ASK_CLARIFICATION:
            phase = InvestigationPhase.INITIALIZATION

        elif decision == ReflectionDecision.ABSTAIN:
            phase = InvestigationPhase.INITIALIZATION

        return ReplanRequest(
            reason=f"[{decision.value}] {'; '.join(gaps)}",
            suggested_agents=suggested_agents,
            evidence_gaps=gaps,
            phase=phase,
        )
