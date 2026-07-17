"""Reflection Agent for the multi-agent runtime.

The reflection agent analyses the current state of an investigation
and produces recommendations about quality, gaps, and next steps.
It is invoked by the supervisor when no direct agents are available
or when the supervisor needs a second opinion on evidence quality.

Contains no business logic -- only the structural framework for
reflection and gap analysis.
"""

from __future__ import annotations

from typing import Any

from mnemos.agentic.runtime.types import (
    AgentInvocationMetadata,
    AgentRole,
    AgentStatus,
    ReflectionOutput,
)
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("runtime.reflection")


class ReflectionAgent:
    """Analyses investigation state and recommends next steps.

    The reflection agent is a special agent invoked by the supervisor.
    It does not retrieve or analyse evidence itself; it only examines
    what other agents have produced and identifies gaps, contradictions,
    and quality issues.
    """

    def __init__(
        self,
        evidence_completeness_threshold: float = 0.6,
        min_evidence_count: int = 3,
    ) -> None:
        self.evidence_completeness_threshold = evidence_completeness_threshold
        self.min_evidence_count = min_evidence_count

    async def reflect(self, state: dict[str, Any]) -> ReflectionOutput:
        """Produce a reflection on the current investigation state."""
        metadata = self._start_metadata()

        try:
            evidence = state.get("evidence", [])
            claims = state.get("claims", [])
            agent_outputs = state.get("agent_outputs", {})
            completed_agents = state.get("completed_agents", [])
            errors = state.get("errors", [])

            # ---- Evidence completeness -----------------------------------
            evidence_completeness = self._assess_evidence_completeness(
                evidence, claims, agent_outputs
            )

            # ---- Identify gaps -------------------------------------------
            gaps = self._identify_gaps(
                evidence, claims, completed_agents, agent_outputs
            )

            # ---- Identify contradictions ---------------------------------
            contradictions = self._identify_contradictions(claims)

            # ---- Quality assessment --------------------------------------
            overall_quality = self._assess_quality(
                evidence_completeness, claims, errors, agent_outputs
            )

            # ---- Recommend next agents -----------------------------------
            next_agents = self._recommend_next_agents(
                gaps, completed_agents, agent_outputs
            )

            # ---- Should continue or abstain ------------------------------
            should_continue = self._should_continue(
                overall_quality, gaps, completed_agents
            )
            should_abstain = self._should_abstain(
                overall_quality, gaps, errors
            )

            abstention_reason = None
            if should_abstain:
                abstention_reason = (
                    "Investigation has insufficient evidence and no viable "
                    "paths to collect more."
                )

            output = ReflectionOutput(
                overall_quality=overall_quality,
                evidence_completeness=evidence_completeness,
                identified_gaps=gaps,
                contradictions=contradictions,
                suggested_next_agents=next_agents,
                should_continue=should_continue,
                should_abstain=should_abstain,
                abstention_reason=abstention_reason,
                reasoning=self._build_reasoning(
                    overall_quality, evidence_completeness, gaps, contradictions
                ),
            )

            metadata.status = AgentStatus.COMPLETED
            metadata.confidence = overall_quality
            metadata.reasoning_summary = output.reasoning

            logger.info(
                f"Reflection complete: quality={overall_quality:.2f}, "
                f"gaps={len(gaps)}, next_agents={next_agents}"
            )
            return output

        except Exception as exc:
            metadata.status = AgentStatus.FAILED
            metadata.error = str(exc)
            logger.error(f"Reflection failed: {exc}", exc_info=True)
            return ReflectionOutput(
                should_continue=True,
                reasoning=f"Reflection failed: {exc}",
            )

    # ------------------------------------------------------------------
    # Assessment methods
    # ------------------------------------------------------------------

    def _assess_evidence_completeness(
        self,
        evidence: list[Any],
        claims: list[Any],
        agent_outputs: dict[str, Any],
    ) -> float:
        score = 0.0
        max_score = 1.0

        # Evidence count contribution (up to 0.3)
        evidence_factor = min(len(evidence) / max(self.min_evidence_count, 1), 1.0)
        score += evidence_factor * 0.3

        # Claims contribution (up to 0.3)
        claims_factor = min(len(claims) / max(self.min_evidence_count, 1), 1.0)
        score += claims_factor * 0.3

        # Agent output coverage (up to 0.4)
        if agent_outputs:
            agent_factor = min(len(agent_outputs) / 3, 1.0)
            score += agent_factor * 0.4

        return min(score, max_score)

    def _identify_gaps(
        self,
        evidence: list[Any],
        claims: list[Any],
        completed_agents: list[str],
        agent_outputs: dict[str, Any],
    ) -> list[str]:
        gaps: list[str] = []

        if not evidence:
            gaps.append("No evidence collected yet")
        elif len(evidence) < self.min_evidence_count:
            gaps.append(
                f"Insufficient evidence: {len(evidence)}/{self.min_evidence_count} minimum"
            )

        if not claims:
            gaps.append("No claims have been produced")

        if not completed_agents:
            gaps.append("No agents have completed execution")

        if "retrieval_agent" not in completed_agents:
            gaps.append("Evidence retrieval agent has not run")
        if "verification_agent" not in completed_agents:
            gaps.append("Evidence verification agent has not run")

        return gaps

    def _identify_contradictions(self, claims: list[Any]) -> list[str]:
        contradictions: list[str] = []
        seen_texts: dict[str, str] = {}

        for claim in claims:
            text = claim.get("text", "") if isinstance(claim, dict) else getattr(claim, "text", "")
            status = claim.get("status", "") if isinstance(claim, dict) else getattr(claim, "status", "")

            if status in ("refuted", "conflicting"):
                contradictions.append(f"Refuted claim: {text[:100]}")
            elif text in seen_texts:
                contradictions.append(f"Duplicate claim: {text[:100]}")
            else:
                seen_texts[text] = status

        return contradictions

    def _assess_quality(
        self,
        evidence_completeness: float,
        claims: list[Any],
        errors: list[str],
        agent_outputs: dict[str, Any],
    ) -> float:
        quality = evidence_completeness * 0.5

        # Claim grounding
        grounded = sum(
            1 for c in claims
            if (c.get("status") if isinstance(c, dict) else getattr(c, "status", "")) == "supported"
        )
        if claims:
            quality += (grounded / len(claims)) * 0.3

        # Error penalty
        if errors:
            error_penalty = min(len(errors) * 0.05, 0.3)
            quality -= error_penalty

        # Agent output confidence
        confidences = []
        for output in agent_outputs.values():
            if isinstance(output, dict) and "confidence" in output:
                confidences.append(output["confidence"])
        if confidences:
            quality += (sum(confidences) / len(confidences)) * 0.2

        return max(0.0, min(quality, 1.0))

    def _recommend_next_agents(
        self,
        gaps: list[str],
        completed_agents: list[str],
        agent_outputs: dict[str, Any],
    ) -> list[str]:
        recommendations: list[str] = []

        if "retrieval_agent" not in completed_agents:
            recommendations.append("retrieval_agent")
        if "verification_agent" not in completed_agents:
            recommendations.append("verification_agent")
        if "analysis_agent" not in completed_agents and "retrieval_agent" in completed_agents:
            recommendations.append("analysis_agent")

        if len(completed_agents) >= 3 and not recommendations:
            recommendations.append("composition_agent")

        return recommendations[:3]

    def _should_continue(
        self,
        quality: float,
        gaps: list[str],
        completed_agents: list[str],
    ) -> bool:
        if quality >= 0.8 and len(gaps) <= 1:
            return False
        if len(completed_agents) >= 5 and quality >= 0.5:
            return False
        return True

    def _should_abstain(
        self,
        quality: float,
        gaps: list[str],
        errors: list[str],
    ) -> bool:
        if quality < 0.1 and len(errors) > 3:
            return True
        if len(gaps) > 5 and quality < 0.2:
            return True
        return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _start_metadata(self) -> AgentInvocationMetadata:
        return AgentInvocationMetadata(
            agent_name="reflection_agent",
            agent_role=AgentRole.REFLECTION,
            status=AgentStatus.RUNNING,
        )

    def _build_reasoning(
        self,
        quality: float,
        completeness: float,
        gaps: list[str],
        contradictions: list[str],
    ) -> str:
        parts = [
            f"Overall quality: {quality:.2f}",
            f"Evidence completeness: {completeness:.2f}",
        ]
        if gaps:
            parts.append(f"Gaps identified: {len(gaps)}")
        if contradictions:
            parts.append(f"Contradictions found: {len(contradictions)}")
        return "; ".join(parts)
