"""Shared base class for retrieval intelligence agents.

Provides common dependency injection (DB session, LLM, guardrails)
and the adapter pattern that bridges the legacy ``AgentState`` with
the new runtime ``InvestigationState``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.agents.interfaces import CollaborativeAgent
from mnemos.agentic.deps import get_llm_service, get_prompt_manager
from mnemos.agentic.runtime.types import AgentRegistration, AgentRole
from mnemos.agentic.schemas.state import AgentState
from mnemos.agentic.utils.guardrails import MnemosGuardrails


class _BaseRetrievalAgent(CollaborativeAgent, ABC):
    """Abstract base for all retrieval intelligence agents.

    Provides:
    - Dependency injection for ``db``, ``llm``, ``prompt_manager``, ``guardrails``
    - Shared ``as_function()`` adapter for the runtime workflow
    - Abstract ``execute()`` for concrete agent logic
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.llm = get_llm_service()
        self.prompt_manager = get_prompt_manager()
        self.guardrails = MnemosGuardrails()

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
