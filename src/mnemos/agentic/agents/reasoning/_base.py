"""Shared base class for reasoning intelligence agents.

Provides common dependency injection, state management, and the
adapter pattern that bridges ``AgentState`` with the runtime.

All reasoning agents:
1. Read verified evidence from ``context["evidence_bundle"]``
2. Produce a ``ReasoningOutput`` stored in ``context["reasoning_output"]``
3. Never hallucinate facts — every claim must trace to verified evidence
4. Can request collaboration from other agents via ``next_recommended_agents``
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.agents.interfaces import CollaborativeAgent
from mnemos.agentic.deps import get_llm_service, get_prompt_manager
from mnemos.agentic.runtime.types import AgentRegistration, AgentRole
from mnemos.agentic.schemas.base import EvidenceBundle, ReasoningOutput
from mnemos.agentic.schemas.state import AgentState
from mnemos.agentic.utils.guardrails import MnemosGuardrails
from mnemos.agentic.utils.logging import StructuredLogger


class _BaseReasoningAgent(CollaborativeAgent, ABC):
    """Abstract base for all reasoning intelligence agents.

    Provides:
    - Dependency injection for ``db``, ``llm``, ``prompt_manager``, ``guardrails``
    - Shared ``as_function()`` adapter for the runtime workflow
    - Abstract ``execute()`` for concrete agent logic
    - Common evidence extraction and output storage
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.llm = get_llm_service()
        self.prompt_manager = get_prompt_manager()
        self.guardrails = MnemosGuardrails()
        self.logger = StructuredLogger(f"agents.reasoning.{self.name}")

    # ------------------------------------------------------------------
    # BaseAgent abstract property satisfies
    # ------------------------------------------------------------------

    @property
    def registration(self) -> AgentRegistration:
        return self.to_registration()

    # ------------------------------------------------------------------
    # CollaborativeAgent overrides
    # ------------------------------------------------------------------

    def to_registration(self) -> AgentRegistration:
        return AgentRegistration(
            name=self.name,
            role=self.role,
            description=self.description,
            capabilities=self._capabilities(),
            max_retries=self.max_retries,
            timeout_seconds=self.timeout_seconds,
            dependencies=self.required_dependencies,
        )

    # ------------------------------------------------------------------
    # BaseAgent protocol
    # ------------------------------------------------------------------

    async def run(self, state: AgentState) -> AgentState:
        try:
            updated = await self.execute(state)
            steps = list(updated.get("steps_completed", []))
            steps.append(self.name)
            updated["steps_completed"] = steps
            return updated
        except Exception as exc:
            errors = list(state.get("errors", []))
            errors.append(f"AGENT_ERROR:{self.name}: {exc}")
            state["errors"] = errors
            return state

    async def as_function(self, state: dict[str, Any]) -> dict[str, Any]:
        result_state = await self.run(state)
        return dict(result_state)

    # ------------------------------------------------------------------
    # Evidence helpers
    # ------------------------------------------------------------------

    def _get_evidence_bundle(self, state: AgentState) -> EvidenceBundle | None:
        """Extract the verified evidence bundle from state."""
        ctx = state.get("context", {})
        return ctx.get("evidence_bundle")

    def _get_previous_reasoning(
        self, state: AgentState, agent_name: str | None = None
    ) -> list[ReasoningOutput]:
        """Extract previous reasoning outputs from state.

        If ``agent_name`` is given, filter to that agent only.
        """
        ctx = state.get("context", {})
        all_reasoning: list[ReasoningOutput] = ctx.get("reasoning_outputs", [])
        if agent_name:
            return [r for r in all_reasoning if r.agent_name == agent_name]
        return all_reasoning

    def _store_reasoning_output(
        self, state: AgentState, output: ReasoningOutput
    ) -> AgentState:
        """Store a reasoning output in state context."""
        ctx = dict(state.get("context", {}))
        outputs: list[ReasoningOutput] = ctx.get("reasoning_outputs", [])
        outputs.append(output)
        ctx["reasoning_outputs"] = outputs
        ctx["reasoning_output"] = output
        state["context"] = ctx
        return state

    def _validate_evidence_exists(
        self, state: AgentState
    ) -> EvidenceBundle | None:
        """Get evidence bundle or set abstain if missing."""
        bundle = self._get_evidence_bundle(state)
        if bundle is None:
            output = ReasoningOutput(
                agent_name=self.name,
                reasoning_decision="abstain",
                reasoning_summary="No evidence bundle available for reasoning",
            )
            self._store_reasoning_output(state, output)
        return bundle

    # ------------------------------------------------------------------
    # Subclass hooks
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def role(self) -> AgentRole: ...

    @property
    def description(self) -> str:
        return ""

    @property
    def max_retries(self) -> int:
        return 2

    @property
    def timeout_seconds(self) -> float:
        return 120.0

    @property
    def required_dependencies(self) -> list[str]:
        return []

    @abstractmethod
    def _capabilities(self) -> list[Any]:
        return []

    @abstractmethod
    async def execute(self, state: AgentState) -> AgentState: ...
