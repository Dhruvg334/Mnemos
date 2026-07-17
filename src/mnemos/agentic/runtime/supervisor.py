"""Supervisor Agent for the multi-agent runtime.

The supervisor is the central orchestrator.  It:
- maintains the global investigation state
- decides which agent executes next
- receives outputs from every agent
- decides whether another agent should run
- requests replanning when evidence is insufficient
- terminates only when sufficient evidence exists or abstention is required

This module contains zero business logic -- only the decision-making
framework for agent dispatch.
"""

from __future__ import annotations

from typing import Any

from mnemos.agentic.runtime.registry import AgentCapabilityRegistry, AgentRegistry
from mnemos.agentic.runtime.types import (
    AgentRole,
    InvestigationPhase,
    SupervisorDecision,
    TerminationReason,
)
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("runtime.supervisor")

# Maximum iterations before forced termination
_DEFAULT_MAX_ITERATIONS = 10
_EVIDENCE_CONFIDENCE_THRESHOLD = 0.7


class SupervisorAgent:
    """Decides which agents to dispatch, in what order, and whether to
    continue, abstain, or terminate the investigation.

    The supervisor never executes agent logic itself.  It only produces
    ``SupervisorDecision`` objects that the workflow runtime consumes
    to dispatch actual agents.
    """

    def __init__(
        self,
        agent_registry: AgentRegistry,
        capability_registry: AgentCapabilityRegistry,
        max_iterations: int = _DEFAULT_MAX_ITERATIONS,
        evidence_confidence_threshold: float = _EVIDENCE_CONFIDENCE_THRESHOLD,
    ) -> None:
        self.agent_registry = agent_registry
        self.capability_registry = capability_registry
        self.max_iterations = max_iterations
        self.evidence_confidence_threshold = evidence_confidence_threshold

    # ------------------------------------------------------------------
    # Core decision
    # ------------------------------------------------------------------

    def decide_next(self, state: dict[str, Any]) -> SupervisorDecision:
        """Analyse the current investigation state and decide the next action.

        This is the heart of the supervisor.  It examines:
        1. Current phase
        2. Which agents have completed
        3. Evidence quality and completeness
        4. Iteration count
        5. Pending approvals
        6. Errors and failures
        """
        phase = InvestigationPhase(state.get("phase", InvestigationPhase.INITIALIZATION))
        iteration = state.get("iteration", 0)
        completed = state.get("completed_agents", [])
        pending = state.get("pending_agents", [])
        errors = state.get("errors", [])
        approval_required = state.get("approval_required", False)
        should_abstain = state.get("should_abstain", False)
        is_complete = state.get("is_complete", False)

        logger.info(
            f"Supervisor deciding: phase={phase}, iteration={iteration}, "
            f"completed={completed}, pending={pending}"
        )

        # ---- Termination checks -----------------------------------------
        if is_complete:
            return self._terminate(
                phase, TerminationReason.SUFFICIENT_EVIDENCE,
                "Investigation marked complete."
            )

        if should_abstain:
            return self._terminate(
                phase, TerminationReason.ABSTENTION,
                state.get("abstention_reason", "Abstention requested.")
            )

        if iteration >= self.max_iterations:
            return self._terminate(
                phase, TerminationReason.MAX_ITERATIONS,
                f"Max iterations ({self.max_iterations}) reached."
            )

        if self._all_agents_failed(errors):
            return self._terminate(
                phase, TerminationReason.ALL_AGENTS_FAILED,
                "All dispatched agents have failed."
            )

        # ---- Approval gate ----------------------------------------------
        if approval_required:
            return SupervisorDecision(
                phase=InvestigationPhase.APPROVAL,
                agents_to_dispatch=[],
                reasoning="Waiting for human approval before continuing.",
                should_continue=True,
            )

        # ---- Pending agents still running --------------------------------
        if pending:
            return SupervisorDecision(
                phase=phase,
                agents_to_dispatch=[],
                reasoning=f"Waiting for pending agents: {pending}.",
                should_continue=True,
            )

        # ---- Compute next agents ----------------------------------------
        next_agents = self._select_next_agents(state)

        if not next_agents:
            # No more agents to run -- check if we have enough evidence
            if self._has_sufficient_evidence(state):
                return self._terminate(
                    phase, TerminationReason.SUFFICIENT_EVIDENCE,
                    "All available agents executed; sufficient evidence collected."
                )
            # Try reflection to see if replanning is needed
            return SupervisorDecision(
                phase=InvestigationPhase.REFLECTION,
                agents_to_dispatch=["reflection_agent"],
                reasoning="No direct agents available; invoking reflection.",
                should_continue=True,
            )

        # ---- Determine phase transition ----------------------------------
        new_phase = self._determine_phase(next_agents, phase)

        # ---- Check for parallel execution --------------------------------
        parallel = self._can_run_parallel(next_agents)

        return SupervisorDecision(
            phase=new_phase,
            agents_to_dispatch=next_agents,
            parallel=parallel,
            reasoning=self._build_reasoning(next_agents, state),
            should_continue=True,
        )

    # ------------------------------------------------------------------
    # Agent selection
    # ------------------------------------------------------------------

    def _select_next_agents(self, state: dict[str, Any]) -> list[str]:
        completed = state.get("completed_agents", [])
        pending = state.get("pending_agents", [])

        executable = self.agent_registry.get_executable_agents(completed, pending)
        if not executable:
            return []

        # Filter out reflection and supervisor (they're invoked separately)
        dispatchable = [
            reg for reg in executable
            if reg.role not in (AgentRole.SUPERVISOR, AgentRole.HUMAN_APPROVAL)
        ]

        if not dispatchable:
            return []

        # Priority: verification agents first, then analysis, then composition
        priority_order = [
            AgentRole.RETRIEVAL,
            AgentRole.ANALYSIS,
            AgentRole.VERIFICATION,
            AgentRole.COMPOSITION,
            AgentRole.GENERIC,
        ]

        dispatchable.sort(key=lambda r: (
            priority_order.index(r.role) if r.role in priority_order else 99
        ))

        return [reg.name for reg in dispatchable]

    def _can_run_parallel(self, agent_names: list[str]) -> bool:
        if len(agent_names) < 2:
            return False
        for name in agent_names:
            reg = self.agent_registry.get(name)
            if reg is None or not reg.can_run_in_parallel:
                return False
        return True

    # ------------------------------------------------------------------
    # Phase management
    # ------------------------------------------------------------------

    def _determine_phase(
        self, next_agents: list[str], current_phase: InvestigationPhase
    ) -> InvestigationPhase:
        if current_phase == InvestigationPhase.INITIALIZATION:
            return InvestigationPhase.PLANNING

        roles = set()
        for name in next_agents:
            reg = self.agent_registry.get(name)
            if reg:
                roles.add(reg.role)

        if AgentRole.RETRIEVAL in roles:
            return InvestigationPhase.EVIDENCE_GATHERING
        if AgentRole.ANALYSIS in roles:
            return InvestigationPhase.ANALYSIS
        if AgentRole.VERIFICATION in roles:
            return InvestigationPhase.VERIFICATION
        if AgentRole.COMPOSITION in roles:
            return InvestigationPhase.SYNTHESIS
        return current_phase

    # ------------------------------------------------------------------
    # Evidence assessment
    # ------------------------------------------------------------------

    def _has_sufficient_evidence(self, state: dict[str, Any]) -> bool:
        evidence = state.get("evidence", [])
        claims = state.get("claims", [])
        agent_outputs = state.get("agent_outputs", {})

        if not evidence and not claims:
            return False

        if len(evidence) == 0 and len(claims) == 0:
            return False

        # Check average confidence across agent outputs
        confidences = []
        for output in agent_outputs.values():
            if isinstance(output, dict) and "confidence" in output:
                confidences.append(output["confidence"])

        if confidences:
            avg_confidence = sum(confidences) / len(confidences)
            return avg_confidence >= self.evidence_confidence_threshold

        return len(evidence) > 0 or len(claims) > 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _terminate(
        self,
        phase: InvestigationPhase,
        reason: TerminationReason,
        description: str,
    ) -> SupervisorDecision:
        logger.info(f"Supervisor terminating: {reason} -- {description}")
        return SupervisorDecision(
            phase=phase,
            agents_to_dispatch=[],
            reasoning=description,
            should_continue=False,
            termination_reason=reason,
        )

    def _all_agents_failed(self, errors: list[str]) -> bool:
        if not errors:
            return False
        return all("INTERNAL_ERROR" in e or "AGENT_FAILED" in e for e in errors)

    def _build_reasoning(
        self, next_agents: list[str], state: dict[str, Any]
    ) -> str:
        completed = state.get("completed_agents", [])
        iteration = state.get("iteration", 0)
        return (
            f"Iteration {iteration + 1}: dispatching {next_agents} "
            f"after {len(completed)} completed agents."
        )
